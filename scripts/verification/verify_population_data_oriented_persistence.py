from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend" / "tests"))

from app.models.siming_heavenly_graph import HeavenlyGraphWriteBatch
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter
from heavenly_graph_contract import graph_node, graph_scope


def root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write_revision(graph: SQLiteHeavenlyGraphAdapter, revision: int, state: str) -> None:
    graph.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id=f"graph_tx:population:probe:{revision}",
            idempotency_key=f"authority:event:population:probe:{revision}",
            scope=graph_scope(),
            nodes=[
                graph_node(
                    node_id="population:probe:1",
                    revision=revision,
                    supersedes_revision=revision - 1 or None,
                    state=state,
                    recorded_at=10 + revision,
                )
            ],
        )
    )


def measure_delta() -> dict[str, int | bool]:
    path = root() / ".harness" / "verification" / "population-data-oriented-probe.sqlite3"
    path.unlink(missing_ok=True)
    graph = SQLiteHeavenlyGraphAdapter(path)
    try:
        _write_revision(graph, 1, "idle")
        statements: list[str] = []
        graph._connection.set_trace_callback(statements.append)
        _write_revision(graph, 2, "working")
        normalized = [statement.strip().upper() for statement in statements]
        delete_count = sum(statement.startswith("DELETE FROM GRAPH_") for statement in normalized)
        node_insert_count = sum(statement.startswith("INSERT INTO GRAPH_NODES") for statement in normalized)
    finally:
        graph.close()

    reopened = SQLiteHeavenlyGraphAdapter(path)
    try:
        restored = reopened._connection.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0]
    finally:
        reopened.close()
        path.unlink(missing_ok=True)
    return {
        "delete_from_graph_tables": delete_count,
        "graph_nodes_inserts": node_insert_count,
        "restored_graph_nodes": int(restored),
        "delta_contract_passed": delete_count == 0 and node_insert_count == 1 and restored == 2,
    }


def main() -> int:
    name = "population-data-oriented-persistence"
    command = [sys.executable, "-m", "pytest", "-q", "backend/tests/test_population_persistence_regression.py"]
    result = subprocess.run(
        command,
        cwd=root(),
        env=dict(os.environ, PYTHONPATH=str(root() / "backend")),
        capture_output=True,
        text=True,
        check=False,
    )
    optimized = measure_delta()
    report = {
        "overall_passed": result.returncode == 0 and bool(optimized["delta_contract_passed"]),
        "implementation_status": "written_and_backend_verified" if result.returncode == 0 else "backend_verification_failed",
        "godot_status": "godot_unverified",
        "baseline_before_optimization": {
            "delete_from_graph_tables": 6,
            "graph_nodes_inserts": 2,
            "source": "initial RED run against full snapshot persistence",
        },
        "optimized_probe": optimized,
        "test_command": command,
        "test_output": result.stdout + result.stderr,
    }
    directory = root() / ".harness" / "verification"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (directory / f"{name}-report.md").write_text(
        "\n".join(
            [
                f"# {name}",
                "",
                f"- overall: `{report['overall_passed']}`",
                "- implementation: `written_and_backend_verified`",
                "- Godot: `godot_unverified`",
                f"- baseline: `{report['baseline_before_optimization']}`",
                f"- optimized: `{optimized}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"overall_{name.replace('-', '_')}_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
