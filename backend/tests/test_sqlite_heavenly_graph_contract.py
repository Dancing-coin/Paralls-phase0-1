import json
import sqlite3
from pathlib import Path
from threading import Event, Thread

from heavenly_graph_contract import (
    HeavenlyGraphContract,
    graph_node,
    graph_relation,
    graph_scope,
)

from app.models.siming_heavenly_graph import (
    GraphCorrectionRequest,
    GraphSemanticMetadata,
    HeavenlyGraphWriteBatch,
    HeavenlyNodeQuery,
)
from app.services.siming_heavenly_graph_port import HeavenlyGraphPort
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter


class TestSQLiteHeavenlyGraphContract(HeavenlyGraphContract):
    def make_graph(self) -> HeavenlyGraphPort:
        return SQLiteHeavenlyGraphAdapter(":memory:")


def test_sqlite_restart_restores_node_revision(tmp_path: Path) -> None:
    path = tmp_path / "heavenly.sqlite3"
    scope = graph_scope()
    first = SQLiteHeavenlyGraphAdapter(path)
    first.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id="graph_tx:restart",
            idempotency_key="authority:event:restart",
            scope=scope,
            nodes=[graph_node(node_id="fact:letter")],
        )
    )
    first.close()

    reopened = SQLiteHeavenlyGraphAdapter(path)
    node = reopened.get_node(node_id="fact:letter", scope=scope, valid_at=20)
    reopened.close()

    assert node is not None
    assert node.revision == 1


def test_sqlite_restart_restores_checkpoint_replay_metadata(tmp_path: Path) -> None:
    path = tmp_path / "heavenly-checkpoint.sqlite3"
    scope = graph_scope()
    first = SQLiteHeavenlyGraphAdapter(path)
    first.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id="graph_tx:restart:checkpoint",
            idempotency_key="authority:event:restart:checkpoint",
            scope=scope,
            nodes=[graph_node(node_id="fact:checkpoint")],
        )
    )
    checkpoint = first.create_checkpoint(
        checkpoint_id="checkpoint:restart",
        scope=scope,
        valid_at=20,
        recorded_at=20,
    )
    expected = first.read_checkpoint(checkpoint.checkpoint_ref)
    first.close()

    reopened = SQLiteHeavenlyGraphAdapter(path)
    restored = reopened.read_checkpoint(checkpoint.checkpoint_ref)
    reopened.close()

    assert restored.checkpoint == expected.checkpoint
    assert restored.nodes == expected.nodes
    assert restored.replay_nodes == expected.replay_nodes
    assert restored.replay_relations == expected.replay_relations


def _remove_replay_frontier(path: Path, checkpoint_ref: str) -> None:
    """Simulate a pre-frontier checkpoint payload without changing source rows."""

    connection = sqlite3.connect(path)
    try:
        row = connection.execute(
            "SELECT snapshot_json FROM graph_checkpoints WHERE checkpoint_ref = ?",
            (checkpoint_ref,),
        ).fetchone()
        assert row is not None
        payload = json.loads(row[0])
        payload.pop("replay_nodes", None)
        payload.pop("replay_relations", None)
        connection.execute(
            "UPDATE graph_checkpoints SET snapshot_json = ? WHERE checkpoint_ref = ?",
            (json.dumps(payload, sort_keys=True, separators=(",", ":")), checkpoint_ref),
        )
        connection.commit()
    finally:
        connection.close()


def _checkpoint_payload(path: Path, checkpoint_ref: str) -> dict[str, object]:
    connection = sqlite3.connect(path)
    try:
        row = connection.execute(
            "SELECT snapshot_json FROM graph_checkpoints WHERE checkpoint_ref = ?",
            (checkpoint_ref,),
        ).fetchone()
        assert row is not None
        return json.loads(row[0])
    finally:
        connection.close()


def test_sqlite_restart_replays_future_valid_predecessor_chain(tmp_path: Path) -> None:
    path = tmp_path / "heavenly-replay-future.sqlite3"
    scope = graph_scope()
    first = SQLiteHeavenlyGraphAdapter(path)
    seed = graph_node(node_id="fact:future-chain", state="old", valid_from=0, recorded_at=10)
    anchor = graph_node(node_id="fact:future-anchor", valid_from=0, recorded_at=10)
    relation = graph_relation(
        relation_id="relation:future-chain",
        source_node_id=anchor.node_id,
        target_node_id=seed.node_id,
        valid_from=0,
        recorded_at=10,
    )
    first.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id="graph_tx:sqlite-restart:future:seed",
            idempotency_key="authority:event:sqlite-restart:future:seed",
            scope=scope,
            nodes=[seed, anchor],
            relations=[relation],
        )
    )
    future = graph_node(
        node_id=seed.node_id,
        state="scheduled",
        valid_from=50,
        recorded_at=15,
        revision=2,
        supersedes_revision=1,
        source_ref="authority:event:sqlite-restart:future:2",
    )
    first.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id="graph_tx:sqlite-restart:future:second",
            idempotency_key="authority:event:sqlite-restart:future:second",
            scope=scope,
            nodes=[future],
        )
    )
    checkpoint = first.create_checkpoint(
        checkpoint_id="checkpoint:sqlite-restart:future",
        scope=scope,
        valid_at=20,
        recorded_at=20,
    )
    first.close()

    # The payload mutation models a checkpoint written before replay frontier
    # fields existed. SQLite must recover the frontier from durable source rows.
    _remove_replay_frontier(path, checkpoint.checkpoint_ref)
    reopened = SQLiteHeavenlyGraphAdapter(path)
    restored = reopened.read_checkpoint(checkpoint.checkpoint_ref)
    assert [node.revision for node in restored.replay_nodes if node.node_id == seed.node_id] == [1, 2]
    assert [relation.revision for relation in restored.replay_relations] == [1]

    tail = graph_node(
        node_id=seed.node_id,
        state="settled",
        valid_from=0,
        recorded_at=30,
        revision=3,
        supersedes_revision=2,
        source_ref="authority:event:sqlite-restart:future:3",
    )
    tail_batch = HeavenlyGraphWriteBatch(
        transaction_id="graph_tx:sqlite-restart:future:tail",
        idempotency_key="authority:event:sqlite-restart:future:tail",
        scope=scope,
        nodes=[tail],
    )
    reopened.write_batch(tail_batch)
    full_ref = reopened.create_checkpoint(
        checkpoint_id="checkpoint:sqlite-restart:future:full",
        scope=scope,
        valid_at=20,
        recorded_at=40,
    )
    full = reopened.read_checkpoint(full_ref.checkpoint_ref)
    checkpoint_before_replay = reopened.read_checkpoint(checkpoint.checkpoint_ref)
    source_before_replay = reopened.get_node(
        node_id=seed.node_id, scope=scope, valid_at=20, recorded_at=40
    )
    replayed = reopened.replay_from_checkpoint(checkpoint.checkpoint_ref, [tail_batch])
    assert replayed.nodes == full.nodes
    assert replayed.relations == full.relations
    assert replayed.checkpoint.replay_digest == full.checkpoint.replay_digest
    assert reopened.read_checkpoint(checkpoint.checkpoint_ref) == checkpoint_before_replay
    assert reopened.get_node(
        node_id=seed.node_id, scope=scope, valid_at=20, recorded_at=40
    ) == source_before_replay
    reopened.close()


def test_sqlite_restart_replays_retracted_predecessor_chain(tmp_path: Path) -> None:
    path = tmp_path / "heavenly-replay-retracted.sqlite3"
    scope = graph_scope()
    first = SQLiteHeavenlyGraphAdapter(path)
    seed = graph_node(
        node_id="fact:retracted-chain",
        state="old",
        valid_from=0,
        recorded_at=10,
        source_ref="authority:event:sqlite-restart:retracted:1",
    ).model_copy(
        update={
            "semantic_metadata": GraphSemanticMetadata(
                source_event_refs=("authority:event:sqlite-restart:retracted:1",),
                policy_revision="policy:legacy",
                scope_digest="scope:legacy",
            )
        },
        deep=True,
    )
    anchor = graph_node(node_id="fact:retracted-anchor", valid_from=0, recorded_at=10)
    relation = graph_relation(
        relation_id="relation:retracted-chain",
        source_node_id=anchor.node_id,
        target_node_id=seed.node_id,
        valid_from=0,
        recorded_at=10,
    )
    first.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id="graph_tx:sqlite-restart:retracted:seed",
            idempotency_key="authority:event:sqlite-restart:retracted:seed",
            scope=scope,
            nodes=[seed, anchor],
            relations=[relation],
        )
    )
    first.correct(
        GraphCorrectionRequest(
            target_kind="node",
            target_id=seed.node_id,
            target_revision=1,
            correction_kind="retracted",
            source_refs=["authority:event:sqlite-restart:retracted:2"],
            semantic_metadata=GraphSemanticMetadata(
                source_event_refs=("authority:event:sqlite-restart:retracted:1",),
                policy_revision="policy:legacy",
                scope_digest="scope:legacy",
            ),
            scope=scope,
        )
    )
    checkpoint = first.create_checkpoint(
        checkpoint_id="checkpoint:sqlite-restart:retracted",
        scope=scope,
        valid_at=20,
        recorded_at=20,
    )
    first.close()

    _remove_replay_frontier(path, checkpoint.checkpoint_ref)
    reopened = SQLiteHeavenlyGraphAdapter(path)
    restored = reopened.read_checkpoint(checkpoint.checkpoint_ref)
    assert [node.node_id for node in restored.nodes] == [anchor.node_id]
    assert [node.revision for node in restored.replay_nodes if node.node_id == seed.node_id] == [1, 2]
    assert [relation.revision for relation in restored.replay_relations] == [1]

    tail = graph_node(
        node_id=seed.node_id,
        state="restated",
        valid_from=0,
        recorded_at=30,
        revision=3,
        supersedes_revision=2,
        source_ref="authority:event:sqlite-restart:retracted:3",
    )
    tail_batch = HeavenlyGraphWriteBatch(
        transaction_id="graph_tx:sqlite-restart:retracted:tail",
        idempotency_key="authority:event:sqlite-restart:retracted:tail",
        scope=scope,
        nodes=[tail],
    )
    reopened.write_batch(tail_batch)
    full_ref = reopened.create_checkpoint(
        checkpoint_id="checkpoint:sqlite-restart:retracted:full",
        scope=scope,
        valid_at=20,
        recorded_at=40,
    )
    full = reopened.read_checkpoint(full_ref.checkpoint_ref)
    checkpoint_before_replay = reopened.read_checkpoint(checkpoint.checkpoint_ref)
    source_before_replay = reopened.get_node(
        node_id=seed.node_id, scope=scope, valid_at=20, recorded_at=40
    )
    replayed = reopened.replay_from_checkpoint(checkpoint.checkpoint_ref, [tail_batch])
    assert replayed.nodes == full.nodes
    assert replayed.relations == full.relations
    assert replayed.checkpoint.replay_digest == full.checkpoint.replay_digest
    assert reopened.read_checkpoint(checkpoint.checkpoint_ref) == checkpoint_before_replay
    assert reopened.get_node(
        node_id=seed.node_id, scope=scope, valid_at=20, recorded_at=40
    ) == source_before_replay
    reopened.close()


def test_sqlite_query_holds_lock_against_concurrent_write(tmp_path: Path, monkeypatch) -> None:
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / "heavenly.sqlite3")
    scope = graph_scope()
    graph.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id="graph_tx:concurrent:initial",
            idempotency_key="authority:event:concurrent:initial",
            scope=scope,
            nodes=[graph_node(node_id="fact:first"), graph_node(node_id="fact:second")],
        )
    )

    query_entered = Event()
    continue_query = Event()
    writer_finished = Event()
    query_errors: list[Exception] = []
    query_results = []
    original_effective_entity = graph._effective_entity
    first_query = True

    def pause_first_query(*args, **kwargs):
        nonlocal first_query
        if first_query:
            first_query = False
            query_entered.set()
            assert continue_query.wait(1)
        return original_effective_entity(*args, **kwargs)

    monkeypatch.setattr(graph, "_effective_entity", pause_first_query)

    def read() -> None:
        try:
            query_results.extend(graph.query_nodes(HeavenlyNodeQuery(scope=scope, valid_at=20)))
        except Exception as error:
            query_errors.append(error)

    def write() -> None:
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="graph_tx:concurrent:writer",
                idempotency_key="authority:event:concurrent:writer",
                scope=scope,
                nodes=[graph_node(node_id="fact:third")],
            )
        )
        writer_finished.set()

    reader = Thread(target=read)
    writer = Thread(target=write)
    reader.start()
    assert query_entered.wait(1)
    writer.start()
    assert not writer_finished.wait(0.1)
    continue_query.set()
    reader.join(1)
    writer.join(1)
    graph.close()

    assert query_errors == []
    assert [node.node_id for node in query_results] == ["fact:first", "fact:second"]
    assert writer_finished.is_set()
