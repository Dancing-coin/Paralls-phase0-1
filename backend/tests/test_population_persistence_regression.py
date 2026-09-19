from pathlib import Path

import pytest

from heavenly_graph_contract import graph_node, graph_scope
from app.models.siming_heavenly_graph import HeavenlyGraphWriteBatch, HeavenlyNodeQuery
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter


def _write_node(
    graph: SQLiteHeavenlyGraphAdapter,
    *,
    node_id: str,
    revision: int,
    supersedes_revision: int | None,
    state: str,
) -> None:
    scope = graph_scope()
    graph.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id=f"graph_tx:population:{node_id}:{revision}",
            idempotency_key=f"authority:event:population:{node_id}:{revision}",
            scope=scope,
            nodes=[
                graph_node(
                    node_id=node_id,
                    revision=revision,
                    supersedes_revision=supersedes_revision,
                    state=state,
                    recorded_at=10 + revision,
                )
            ],
        )
    )


def test_single_node_revision_persists_as_delta(tmp_path: Path) -> None:
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / "population.sqlite3")
    try:
        _write_node(
            graph,
            node_id="population:actor:1",
            revision=1,
            supersedes_revision=None,
            state="idle",
        )
        statements: list[str] = []
        graph._connection.set_trace_callback(statements.append)

        _write_node(
            graph,
            node_id="population:actor:1",
            revision=2,
            supersedes_revision=1,
            state="working",
        )
    finally:
        graph.close()

    normalized = [statement.strip().upper() for statement in statements]
    assert not any(statement.startswith("DELETE FROM GRAPH_") for statement in normalized)
    assert sum(statement.startswith("INSERT INTO GRAPH_NODES") for statement in normalized) == 1


def test_write_batch_does_not_snapshot_the_entire_graph(
    tmp_path: Path, monkeypatch
) -> None:
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / "population.sqlite3")
    try:
        _write_node(
            graph,
            node_id="population:actor:1",
            revision=1,
            supersedes_revision=None,
            state="idle",
        )

        def fail_if_called() -> tuple[object, ...]:
            raise AssertionError("ordinary write_batch must not copy the full graph")

        monkeypatch.setattr(graph, "_snapshot_mutable_state", fail_if_called)
        _write_node(
            graph,
            node_id="population:actor:1",
            revision=2,
            supersedes_revision=1,
            state="working",
        )
    finally:
        graph.close()


def test_write_batch_failure_restores_only_the_touched_state(
    tmp_path: Path, monkeypatch
) -> None:
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / "population.sqlite3")
    try:
        _write_node(
            graph,
            node_id="population:actor:1",
            revision=1,
            supersedes_revision=None,
            state="idle",
        )
        query = HeavenlyNodeQuery(scope=graph_scope(), node_ids=["population:actor:1"], valid_at=100)
        before_history = graph.query_node_history(query)

        def fail_persistence(_: object) -> None:
            raise RuntimeError("injected_commit_failure")

        monkeypatch.setattr(graph, "_persist_write_batch_delta", fail_persistence)
        with pytest.raises(RuntimeError, match="injected_commit_failure"):
            _write_node(
                graph,
                node_id="population:actor:1",
                revision=2,
                supersedes_revision=1,
                state="working",
            )

        after_history = graph.query_node_history(query)
        assert after_history == before_history
        assert not graph._nodes
        assert graph._scope_stream_revisions[graph._scope_key(graph_scope())] == (1, 0)
    finally:
        graph.close()


def test_sql_commit_failure_rolls_back_database_and_memory(tmp_path, monkeypatch):
    import sqlite3

    path = tmp_path / "commit-failure.sqlite3"
    graph = SQLiteHeavenlyGraphAdapter(path)
    _write_node(graph, node_id="population:actor:1", revision=1,
                supersedes_revision=None, state="idle")
    connection = graph._connection

    class FailingCommit:
        def __getattr__(self, name):
            return getattr(connection, name)

        def commit(self):
            raise sqlite3.OperationalError("injected_commit_failure")

    monkeypatch.setattr(graph, "_connection", FailingCommit())
    with pytest.raises(sqlite3.OperationalError, match="injected_commit_failure"):
        _write_node(graph, node_id="population:actor:1", revision=2,
                    supersedes_revision=1, state="working")
    assert graph.get_node(node_id="population:actor:1", scope=graph_scope(), valid_at=100).revision == 1
    graph.close()
    reopened = SQLiteHeavenlyGraphAdapter(path)
    try:
        assert reopened._connection.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0] == 1
        assert reopened._connection.execute("SELECT COUNT(*) FROM graph_idempotency").fetchone()[0] == 1
        assert reopened.get_node(node_id="population:actor:1", scope=graph_scope(), valid_at=100).revision == 1
        _write_node(reopened, node_id="population:actor:1", revision=2,
                    supersedes_revision=1, state="working")
    finally:
        reopened.close()


def test_scale_probe_accounts_for_revision_summary_and_current_time_writes():
    from scripts.verification.verify_population_data_oriented_persistence import measure_scale
    result = measure_scale(100, repeats=2)
    assert result['passed'] is True
    assert result['sql_changed_rows'] == [5, 5]
    assert result['sql_write_tables'] == {
        'graph_nodes': 2, 'graph_stream_revisions': 2,
        'graph_idempotency': 2, 'graph_revision_summaries': 2, 'graph_current_times': 2,
    }
