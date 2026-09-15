from pathlib import Path

from heavenly_graph_contract import graph_node, graph_scope
from app.models.siming_heavenly_graph import HeavenlyGraphWriteBatch
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
