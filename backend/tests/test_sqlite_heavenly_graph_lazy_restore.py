from pathlib import Path
import json
import sqlite3

import pytest

from heavenly_graph_contract import graph_node, graph_relation, graph_scope

from app.models.siming_heavenly_graph import (
    GraphReaderContext, GraphSemanticMetadata, HeavenlyGraphNode, HeavenlyGraphWriteBatch,
    HeavenlyNodeQuery, HeavenlyRelationQuery, NodeLookupQuery, RelationLookupQuery,
)
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter


def test_runtime_connection_bounds_wal_checkpoint_work_and_uses_direct_model_json(tmp_path: Path):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / "bounded-wal.db")
    try:
        node = graph_node(node_id="fact:direct-json")
        assert graph._connection.execute("PRAGMA wal_autocheckpoint").fetchone() == (
            SQLiteHeavenlyGraphAdapter._WAL_AUTOCHECKPOINT_PAGES,
        )
        assert json.loads(graph._payload_json(node)) == node.model_dump(mode="json")
    finally:
        graph.close()


def test_reopen_and_point_access_do_not_decode_graph_history(tmp_path: Path, monkeypatch):
    path = tmp_path / "graph.db"
    scope = graph_scope()
    graph = SQLiteHeavenlyGraphAdapter(path)
    batches = []
    for revision in range(1, 101):
        node = graph_node(node_id="fact:history").model_copy(update={
            "revision": revision, "supersedes_revision": revision - 1 if revision > 1 else None,
            "recorded_at": 20 + revision,
        })
        batch = HeavenlyGraphWriteBatch(transaction_id=f"tx:{revision}", idempotency_key=f"key:{revision}", scope=scope, nodes=[node])
        graph.write_batch(batch)
        batches.append(batch)
    graph.close()
    decodes = []
    original = HeavenlyGraphNode.model_validate_json

    def decode(value, **kwargs):
        decodes.append(value)
        return original(value, **kwargs)

    monkeypatch.setattr(HeavenlyGraphNode, "model_validate_json", decode)
    reopened = SQLiteHeavenlyGraphAdapter(path)
    try:
        assert decodes == []
        assert not reopened._nodes and not reopened._idempotency
        assert reopened.get_node(node_id="fact:history", scope=scope, valid_at=1000).revision == 100
        assert len(decodes) == 1
        assert reopened.write_batch(batches[0]).replayed
        assert not reopened._nodes and not reopened._idempotency
        new_node = batches[-1].nodes[0].model_copy(update={"revision": 101, "supersedes_revision": 100, "recorded_at": 121})
        reopened.write_batch(HeavenlyGraphWriteBatch(transaction_id="tx:101", idempotency_key="key:101", scope=scope, nodes=[new_node]))
        assert len(decodes) <= 3
        assert reopened.get_node(node_id="fact:history", scope=scope, valid_at=1000).revision == 101
        assert not reopened._nodes and not reopened._idempotency
    finally:
        reopened.close()


def test_schema_one_upgrade_is_atomic_and_reconstructs_missing_stream_counters(tmp_path: Path):
    path = tmp_path / "legacy.db"
    scope = graph_scope()
    graph = SQLiteHeavenlyGraphAdapter(path)
    graph.write_batch(HeavenlyGraphWriteBatch(transaction_id="tx:legacy", idempotency_key="key:legacy", scope=scope,
                                            nodes=[graph_node(node_id="fact:legacy")]))
    graph.close()
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE schema_version SET version=1")
        connection.execute("DELETE FROM graph_stream_revisions")
        connection.execute("DROP INDEX graph_nodes_effective")
        connection.execute("DROP INDEX graph_relations_effective")
        connection.execute(f"CREATE TRIGGER fail_upgrade BEFORE INSERT ON schema_version WHEN NEW.version={SQLiteHeavenlyGraphAdapter.SCHEMA_VERSION} BEGIN SELECT RAISE(ABORT,'upgrade blocked'); END")
    with pytest.raises(sqlite3.IntegrityError, match="upgrade blocked"):
        SQLiteHeavenlyGraphAdapter(path)
    with sqlite3.connect(path) as connection:
        # 失败实例已释放连接；迁移的索引、计数和版本都不能提前提交。
        connection.execute("BEGIN IMMEDIATE")
        assert connection.execute("SELECT version FROM schema_version").fetchall() == [(1,)]
        assert connection.execute("SELECT COUNT(*) FROM graph_stream_revisions").fetchone() == (0,)
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='graph_nodes_effective'").fetchall() == []
        connection.execute("DROP TRIGGER fail_upgrade")
    restored = SQLiteHeavenlyGraphAdapter(path)
    try:
        assert restored.scope_revision_vector(scope).node_revision == 1
        assert restored.get_node(node_id="fact:legacy", scope=scope, valid_at=20) is not None
        assert not restored._nodes
    finally:
        restored.close()


@pytest.mark.parametrize("missing", ["semantic_metadata", "derivation_kind"])
def test_schema_one_metadata_defaults_match_historical_reads_after_upgrade(tmp_path: Path, missing):
    path = tmp_path / "legacy-payload.db"
    scope = graph_scope()
    graph = SQLiteHeavenlyGraphAdapter(path)
    first = graph_node(node_id="fact:legacy")
    second = graph_node(node_id="fact:other")
    relation = graph_relation(relation_id="link:legacy", source_node_id=first.node_id, target_node_id=second.node_id)
    graph.write_batch(HeavenlyGraphWriteBatch(transaction_id="tx:legacy", idempotency_key="key:legacy", scope=scope,
                                            nodes=[first, second], relations=[relation]))
    # 新版本须先参与双时间选优，再隐藏撤回/脱敏结果，不能复活旧版本。
    graph.write_batch(HeavenlyGraphWriteBatch(transaction_id="tx:hidden-link", idempotency_key="key:hidden-link", scope=scope,
        relations=[relation.model_copy(update={"revision": 2, "supersedes_revision": 1, "recorded_at": 30,
            "validity": relation.validity.model_copy(update={"valid_from": 20}),
            "semantic_metadata": GraphSemanticMetadata(derivation_kind="redaction")})]))
    graph.write_batch(HeavenlyGraphWriteBatch(transaction_id="tx:hidden-node", idempotency_key="key:hidden-node", scope=scope,
        nodes=[first.model_copy(update={"revision": 2, "supersedes_revision": 1, "recorded_at": 31,
            "validity": first.validity.model_copy(update={"valid_from": 20}),
            "semantic_metadata": GraphSemanticMetadata(derivation_kind="retraction")})]))
    graph.close()
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE schema_version SET version=1")
        connection.execute("DELETE FROM graph_stream_revisions")
        # 实际旧载荷缺字段，不能只把新模型生成的数据库版本号改成 1。
        for table in ("graph_nodes", "graph_relations"):
            for row_id, encoded in connection.execute(f"SELECT rowid,payload_json FROM {table} WHERE revision=1").fetchall():
                payload = json.loads(encoded)
                if missing == "semantic_metadata":
                    payload.pop("semantic_metadata")
                else:
                    payload["semantic_metadata"].pop("derivation_kind")
                connection.execute(f"UPDATE {table} SET payload_json=? WHERE rowid=?", (json.dumps(payload), row_id))

    def read_views(adapter, valid_at, recorded_at):
        context = GraphReaderContext(reader_principal="reader:legacy", allowed_visibility_scopes=("public",),
            world_id=scope.world_id, session_id=scope.session_id, story_branch_id=scope.story_branch_id,
            valid_at=valid_at, recorded_at=recorded_at, policy_revision="policy:legacy")
        return (
            adapter.get_node(node_id=first.node_id, scope=scope, valid_at=valid_at, recorded_at=recorded_at),
            adapter.get_relation(relation_id=relation.relation_id, scope=scope, valid_at=valid_at, recorded_at=recorded_at),
            adapter.query_nodes(HeavenlyNodeQuery(scope=scope, valid_at=valid_at, recorded_at=recorded_at)),
            adapter.query_relations(HeavenlyRelationQuery(scope=scope, valid_at=valid_at, recorded_at=recorded_at)),
            adapter.query_semantic(NodeLookupQuery(scope=scope, context=context)).nodes,
            adapter.query_semantic(RelationLookupQuery(scope=scope, context=context)).relations,
        )

    for _ in range(2):
        restored = SQLiteHeavenlyGraphAdapter(path)
        try:
            for valid_at, recorded_at, visible in [(15, 20, True), (25, 20, True), (15, 40, True), (25, 40, False)]:
                normal = read_views(restored, valid_at, recorded_at)
                with restored.historical_read():
                    historical = read_views(restored, valid_at, recorded_at)
                assert normal == historical
                assert (normal[0] is not None, normal[1] is not None) == (visible, visible)
                assert len(normal[2]) == len(normal[4]) == (2 if visible else 1)
                assert len(normal[3]) == len(normal[5]) == (1 if visible else 0)
                if visible:
                    assert normal[0].semantic_metadata.derivation_kind == "authority"
                    assert normal[1].semantic_metadata.derivation_kind == "authority"
            assert not restored._nodes and not restored._relations
        finally:
            restored.close()
        with sqlite3.connect(path) as connection:
            assert connection.execute("SELECT version FROM schema_version").fetchall() == [(SQLiteHeavenlyGraphAdapter.SCHEMA_VERSION,)]
