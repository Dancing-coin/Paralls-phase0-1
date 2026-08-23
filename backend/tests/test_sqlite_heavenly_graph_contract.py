from pathlib import Path
from threading import Event, Thread

from heavenly_graph_contract import HeavenlyGraphContract, graph_node, graph_scope

from app.models.siming_heavenly_graph import HeavenlyGraphWriteBatch, HeavenlyNodeQuery
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
