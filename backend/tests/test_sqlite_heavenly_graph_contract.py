from pathlib import Path

from heavenly_graph_contract import HeavenlyGraphContract, graph_node, graph_scope

from app.models.siming_heavenly_graph import HeavenlyGraphWriteBatch
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
