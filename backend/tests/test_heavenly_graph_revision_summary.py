import sqlite3

import pytest

from heavenly_graph_contract import graph_node, graph_scope
from app.models.siming_heavenly_graph import GraphRevisionVector, HeavenlyGraphWriteBatch
from app.services.siming_heavenly_graph_port import HeavenlyGraphError
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter


def _batch(index, count=1):
    nodes = []
    for offset in range(count):
        node = graph_node(node_id=f"fact:{index}:{offset}", valid_from=index, recorded_at=index + 1)
        node = node.model_copy(update={"semantic_metadata": node.semantic_metadata.model_copy(update={
            "source_revision_vector": GraphRevisionVector(source_revision=index, policy_revision=index // 2, branch_revision=index // 3),
        })})
        nodes.append(node)
    return HeavenlyGraphWriteBatch(transaction_id=f"tx:{index}", idempotency_key=f"key:{index}", scope=graph_scope(), nodes=nodes)


def test_current_revision_vector_does_not_scan_history_and_preserves_temporal_filter(tmp_path):
    path = tmp_path / "graph.sqlite"
    graph = SQLiteHeavenlyGraphAdapter(path)
    graph.write_batch(_batch(10, count=1000))
    graph.write_batch(_batch(20))
    graph.close()
    graph = SQLiteHeavenlyGraphAdapter(path)
    try:
        steps = 0

        def count_vm():
            nonlocal steps
            steps += 100
            return 0

        graph._connection.set_progress_handler(count_vm, 100)
        current = graph._scope_revision_vector(graph_scope(), valid_at=2**63 - 1)
        assert current == GraphRevisionVector(node_revision=1001, source_revision=20, policy_revision=10, branch_revision=6)
        assert steps < 1000
        graph._connection.set_progress_handler(None, 0)
        for recorded_at, valid_at in ((None, 15), (15, 25), (None, None), (30, 25)):
            actual = graph._scope_revision_vector(graph_scope(), recorded_at=recorded_at, valid_at=valid_at)
            with graph.historical_read():
                expected = graph._scope_revision_vector(graph_scope(), recorded_at=recorded_at, valid_at=valid_at)
            assert actual == expected
    finally:
        graph.close()


def test_summary_and_graph_write_roll_back_together(tmp_path):
    path = tmp_path / "graph.sqlite"
    graph = SQLiteHeavenlyGraphAdapter(path)
    try:
        graph.write_batch(_batch(1))
        before = graph.scope_revision_vector(graph_scope())
        with sqlite3.connect(path) as db:
            db.execute("CREATE TRIGGER summary_failure BEFORE UPDATE ON graph_revision_summaries BEGIN SELECT RAISE(ABORT,'summary failed'); END")
        with pytest.raises(sqlite3.IntegrityError, match="summary failed"):
            graph.write_batch(_batch(2))
        assert graph.scope_revision_vector(graph_scope()) == before
        assert graph.get_node(node_id="fact:2:0", scope=graph_scope(), valid_at=10) is None
        assert not graph.has_idempotency_key(scope=graph_scope(), idempotency_key="key:2")
        with sqlite3.connect(path) as db:
            db.execute("DROP TRIGGER summary_failure")
        graph.write_batch(_batch(2))
        assert graph.scope_revision_vector(graph_scope()).source_revision == 2
    finally:
        graph.close()


@pytest.mark.parametrize("reopen", [False, True])
def test_missing_summary_rejects_append_before_any_authority_write(tmp_path, reopen):
    path = tmp_path / "missing.sqlite"
    graph = SQLiteHeavenlyGraphAdapter(path)
    try:
        graph.write_batch(_batch(100))
        expected = graph.scope_revision_vector(graph_scope())
        graph._connection.execute("DELETE FROM graph_revision_summaries")
        graph._connection.commit()
        if reopen:
            graph.close()
            graph = SQLiteHeavenlyGraphAdapter(path)
        tables = ("graph_nodes", "graph_relations", "graph_stream_revisions", "graph_idempotency", "graph_revision_summaries")
        before = {table: graph._connection.execute(f"SELECT * FROM {table}").fetchall() for table in tables}
        before_counters = dict(graph._scope_stream_revisions)
        with pytest.raises(HeavenlyGraphError, match="graph_revision_summary_missing"):
            graph.scope_revision_vector(graph_scope())
        statements = []
        graph._connection.set_trace_callback(statements.append)
        try:
            with pytest.raises(HeavenlyGraphError, match="graph_revision_summary_missing"):
                graph.write_batch(_batch(1))
        finally:
            graph._connection.set_trace_callback(None)
        assert not any(sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for sql in statements)
        assert not graph._connection.in_transaction
        assert graph._scope_stream_revisions == before_counters
        assert {table: graph._connection.execute(f"SELECT * FROM {table}").fetchall() for table in tables} == before
        assert not graph.has_idempotency_key(scope=graph_scope(), idempotency_key="key:1")
        assert graph.get_node(node_id="fact:1:0", scope=graph_scope(), valid_at=100) is None
        with pytest.raises(HeavenlyGraphError, match="graph_revision_summary_missing"):
            graph.scope_revision_vector(graph_scope())
        # 只有显式维护才能重新汇总历史；其后普通追加继续保留历史最大版本。
        with graph._connection:
            graph._rebuild_revision_summaries()
        assert graph.write_batch(_batch(1)).applied
        actual = graph.scope_revision_vector(graph_scope())
        assert actual == expected.model_copy(update={"node_revision": 2})
        with graph.historical_read():
            assert graph.scope_revision_vector(graph_scope()) == actual
    finally:
        graph.close()


def test_empty_scope_can_create_summary_and_append_or_replay_normally(tmp_path):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / "empty.sqlite")
    try:
        assert graph.scope_revision_vector(graph_scope()) == GraphRevisionVector()
        assert graph.write_batch(_batch(100)).applied
        assert graph.write_batch(_batch(1)).applied
        assert graph.write_batch(_batch(1)).replayed
        assert not graph._connection.in_transaction
        actual = graph.scope_revision_vector(graph_scope())
        assert actual == GraphRevisionVector(node_revision=2, source_revision=100, policy_revision=50, branch_revision=33)
        with graph.historical_read():
            assert graph.scope_revision_vector(graph_scope()) == actual
    finally:
        graph.close()


def test_schema_two_summary_backfill_is_atomic_and_not_repeated(tmp_path):
    path = tmp_path / "old.sqlite"
    graph = SQLiteHeavenlyGraphAdapter(path)
    graph.write_batch(_batch(9, count=20))
    graph.close()
    with sqlite3.connect(path) as db:
        db.execute("DROP TABLE graph_revision_summaries")
        db.execute("UPDATE schema_version SET version=2")
        db.execute(f"CREATE TRIGGER fail_version BEFORE INSERT ON schema_version WHEN NEW.version={SQLiteHeavenlyGraphAdapter.SCHEMA_VERSION} BEGIN SELECT RAISE(ABORT,'version blocked'); END")
    with pytest.raises(sqlite3.IntegrityError, match="version blocked"):
        SQLiteHeavenlyGraphAdapter(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT version FROM schema_version").fetchall() == [(2,)]
        assert db.execute("SELECT name FROM sqlite_master WHERE name='graph_revision_summaries'").fetchall() == []
        db.execute("DROP TRIGGER fail_version")
    graph = SQLiteHeavenlyGraphAdapter(path)
    expected = graph.scope_revision_vector(graph_scope())
    assert expected.source_revision == 9 and expected.node_revision == 20
    graph.close()
    with sqlite3.connect(path) as db:
        db.execute("CREATE TRIGGER reject_backfill BEFORE DELETE ON graph_revision_summaries BEGIN SELECT RAISE(ABORT,'repeated migration'); END")
    reopened = SQLiteHeavenlyGraphAdapter(path)
    try:
        assert reopened.scope_revision_vector(graph_scope()) == expected
    finally:
        reopened.close()
