from __future__ import annotations

import json
import os
import subprocess
import sys
import platform
import tempfile
import tracemalloc
from statistics import median
from time import perf_counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend" / "tests"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.verification.population_benchmark_metrics import peak_rss_bytes, percentile

from app.character_agent.models.simulation_seed import CharacterContinuityCommand
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.storage.graph_continuity_store import CharacterGraphContinuityStore
from app.character_agent.storage.session_store import CharacterAgentSessionStore
from app.models.siming_heavenly_graph import HeavenlyGraphScope
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
    directory = root() / ".harness" / "verification"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "population-data-oriented-probe.sqlite3"
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


def measure_scale(population: int, repeats: int = 30) -> dict[str, object]:
    """固定修改一个节点，直接计量 undo 项、SQL 行与编码字节。"""
    with tempfile.TemporaryDirectory(prefix="population-graph-") as directory:
        path = Path(directory) / "graph.sqlite3"
        graph = SQLiteHeavenlyGraphAdapter(path)
        graph.write_batch(HeavenlyGraphWriteBatch(
            transaction_id="graph_tx:scale:init", idempotency_key="scale:init", scope=graph_scope(),
            nodes=[graph_node(node_id=f"population:probe:{index}") for index in range(population)],
        ))
        touched = []
        encoded = []
        deletes = []
        capture = graph._capture_write_batch_state
        encode = graph._payload_json

        def capture_count(batch):
            result = capture(batch)
            touched.append(len(result["nodes"]) + len(result["relations"]))
            return result

        def encode_count(value):
            result = encode(value)
            encoded.append(len(result.encode("utf-8")))
            return result

        def forbid_snapshot():
            raise AssertionError("whole_graph_snapshot_in_hot_path")

        graph._capture_write_batch_state = capture_count
        graph._payload_json = encode_count
        graph._snapshot_mutable_state = forbid_snapshot
        graph._connection.set_trace_callback(
            lambda statement: deletes.append(statement) if statement.lstrip().upper().startswith("DELETE") else None
        )
        timings, rows, bytes_per_write = [], [], []
        tracemalloc.start()
        try:
            for revision in range(2, repeats + 2):
                before_rows = graph._connection.total_changes
                before_bytes = len(encoded)
                started = perf_counter()
                _write_revision(graph, revision, "working")
                timings.append((perf_counter() - started) * 1000)
                rows.append(graph._connection.total_changes - before_rows)
                bytes_per_write.append(sum(encoded[before_bytes:]))
            _, peak_allocated = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
            graph.close()
        reopened = SQLiteHeavenlyGraphAdapter(path)
        try:
            restored = reopened._connection.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()[0]
            last = reopened.get_node(node_id="population:probe:1", scope=graph_scope(), valid_at=2**63 - 1)
        finally:
            reopened.close()
    return {
        "population": population, "samples": repeats,
        "p50_ms": median(timings), "p95_ms": percentile(timings),
        "process_peak_rss_bytes": peak_rss_bytes(),
        "python_peak_allocated_bytes": peak_allocated, "timings_ms": timings,
        "undo_entries": touched, "sql_changed_rows": rows, "serialized_bytes": bytes_per_write,
        "whole_graph_snapshot_calls": 0, "delete_count": len(deletes),
        "reopened_node_versions": restored,
        "passed": not deletes and set(touched) == {1} and set(rows) == {3}
                  and restored == population + repeats and last.revision == repeats + 1,
    }


def _legacy_session_event(index: int) -> dict[str, object]:
    return {
        "event_id": f"legacy:char_a:{index}",
        "event_index": index + 1,
        "actor_id": "char_a",
        "event_type": "population_persistence_probe",
        "producer_ts": index,
        "payload": {"probe_kind": "fixed", "probe_value": "x" * 32},
    }


def _actor_scope(actor_id: str) -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:population-persistence-probe",
        session_id="session:population-persistence-probe",
        story_branch_id="branch:main",
        graph_namespace="actor_private",
        owner_actor_id=actor_id,
    )


def _continuity_command(index: int) -> CharacterContinuityCommand:
    tick = index + 1
    return CharacterContinuityCommand(
        command_id=f"continuity:population-probe:{index}",
        actor_ref="character:char_a",
        expected_character_revision=index,
        from_tick=index,
        to_tick=tick,
        simulation_tick_cursor=tick,
        source_revision_vector={"world:population-probe": tick},
        state_delta={"presentation_seed": {"task": "population_probe"}},
        policy_revision="policy:character-continuity:v1",
        idempotency_key=f"continuity:population-probe:{index}",
    )


def measure_session_and_checkpoint_scale(
    population: int, repeats: int = 30
) -> dict[str, object]:
    """从 legacy 历史真实恢复，计量增量 session 与 runtime checkpoint 写入。"""
    with tempfile.TemporaryDirectory(prefix="population-session-") as directory:
        storage_root = Path(directory)
        legacy_path = storage_root / "character_agent_session_store.json"
        legacy_path.write_text(
            json.dumps(
                {"char_a": [_legacy_session_event(index) for index in range(population)]},
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        session = CharacterAgentSessionStore(storage_root=storage_root)
        session.append_event(
            "char_a",
            "population_persistence_probe",
            population,
            {"probe_kind": "fixed", "probe_value": "x" * 32},
            expected_revision=population,
        )
        actor_path = session._actor_storage_path("char_a")
        migration_bytes = actor_path.stat().st_size
        append_bytes: list[int] = []
        for offset in range(repeats):
            before = actor_path.stat().st_size
            session.append_event(
                "char_a",
                "population_persistence_probe",
                population + offset + 1,
                {"probe_kind": "fixed", "probe_value": "x" * 32},
                expected_revision=population + offset + 1,
            )
            append_bytes.append(actor_path.stat().st_size - before)
        session_reopened_count = CharacterAgentSessionStore(
            storage_root=storage_root
        ).event_count("char_a")

        graph_path = storage_root / "continuity.sqlite3"
        graph = SQLiteHeavenlyGraphAdapter(graph_path)
        continuity_store = CharacterGraphContinuityStore(
            graph, scope_resolver=_actor_scope
        )
        checkpoint_bytes: list[int] = []
        checkpoint_event_indexes: list[int] = []
        current_state_bytes: list[int] = []
        original_snapshot_write = continuity_store.write_snapshot
        original_current_write = continuity_store.write_current_state

        def counted_snapshot_write(**kwargs: object) -> None:
            snapshot = kwargs["snapshot"]
            checkpoint_bytes.append(
                len(
                    json.dumps(
                        snapshot, ensure_ascii=False, separators=(",", ":")
                    ).encode("utf-8")
                )
            )
            checkpoint_event_indexes.append(int(snapshot["checkpoint_event_index"]))
            original_snapshot_write(**kwargs)

        def counted_current_write(**kwargs: object) -> None:
            snapshot = kwargs["snapshot"]
            current_state_bytes.append(
                len(
                    json.dumps(
                        snapshot, ensure_ascii=False, separators=(",", ":")
                    ).encode("utf-8")
                )
            )
            original_current_write(**kwargs)

        continuity_store.write_snapshot = counted_snapshot_write
        continuity_store.write_current_state = counted_current_write
        runtime = CharacterAgentRuntime(
            storage_root=storage_root, continuity_store=continuity_store
        )
        receipts = [
            runtime.apply_character_continuity_command(_continuity_command(index))
            for index in range(repeats)
        ]
        runtime_session_count = runtime._session_timeline_event_count("char_a")
        graph.close()

        reopened_graph = SQLiteHeavenlyGraphAdapter(graph_path)
        try:
            reopened_runtime = CharacterAgentRuntime(
                storage_root=storage_root,
                continuity_store=CharacterGraphContinuityStore(
                    reopened_graph, scope_resolver=_actor_scope
                ),
            )
            reopened_revision = reopened_runtime.get_continuity_revision("char_a")
            reopened_runtime_session_count = (
                reopened_runtime._session_timeline_event_count("char_a")
            )
        finally:
            reopened_graph.close()

    expected_session_count = population + repeats + 1
    expected_runtime_session_count = expected_session_count + repeats
    intervals = [
        right - left
        for left, right in zip(
            checkpoint_event_indexes, checkpoint_event_indexes[1:]
        )
    ]
    passed = (
        len(append_bytes) == repeats
        and min(append_bytes) > 0
        and max(append_bytes) - min(append_bytes) < 128
        and session_reopened_count == expected_session_count
        and all(receipt.status == "committed" for receipt in receipts)
        and runtime_session_count == expected_runtime_session_count
        and reopened_runtime_session_count == expected_runtime_session_count
        and reopened_revision == repeats
        and checkpoint_event_indexes
        and checkpoint_event_indexes[0] == expected_session_count + 1
        and all(interval <= 16 for interval in intervals)
        and len(current_state_bytes) == repeats
    )
    return {
        "population": population,
        "samples": repeats,
        "legacy_migration_bytes": migration_bytes,
        "session_append_bytes": append_bytes,
        "session_append_bytes_p50": median(append_bytes),
        "session_append_bytes_max": max(append_bytes),
        "session_reopened_event_count": session_reopened_count,
        "current_state_serialized_bytes": current_state_bytes,
        "current_state_serialized_bytes_max": max(current_state_bytes),
        "checkpoint_serialized_bytes": checkpoint_bytes,
        "checkpoint_event_indexes": checkpoint_event_indexes,
        "checkpoint_intervals": intervals,
        "checkpoint_count": len(checkpoint_event_indexes),
        "runtime_reopened_revision": reopened_revision,
        "runtime_reopened_event_count": reopened_runtime_session_count,
        "passed": passed,
    }


def main() -> int:
    name = "population-data-oriented-persistence"
    command = [sys.executable, "-m", "pytest", "-q",
               "backend/tests/test_population_persistence_regression.py",
               "backend/tests/test_sqlite_heavenly_graph_contract.py",
               "backend/tests/test_character_agent_session_store.py",
               "backend/tests/test_character_graph_continuity_store.py",
               "backend/tests/test_character_agent_seed_continuity.py",
               "backend/tests/test_character_agent_memory_writeback.py",
               "backend/tests/test_gameplay_event_store_persistence.py"]
    result = subprocess.run(
        command,
        cwd=root(),
        env=dict(os.environ, PYTHONPATH=os.pathsep.join((str(root()), str(root() / "backend")))),
        capture_output=True,
        text=True,
        check=False,
    )
    optimized = measure_delta()
    scales = [measure_scale(size) for size in (100, 1000, 10000)]
    session_checkpoint_scales = [
        measure_session_and_checkpoint_scale(size) for size in (100, 1000, 10000)
    ]
    report = {
        "overall_passed": result.returncode == 0 and bool(optimized["delta_contract_passed"]) and all(row["passed"] for row in scales) and all(row["passed"] for row in session_checkpoint_scales),
        "python": platform.python_version(),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root(), text=True).strip(),
        "scale_probes": scales,
        "session_checkpoint_probes": session_checkpoint_scales,
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
    report["implementation_status"] = "written_and_backend_verified" if report["overall_passed"] else "backend_verification_failed"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (directory / f"{name}-report.md").write_text(
        "\n".join(
            [
                f"# {name}",
                "",
                f"- overall: `{report['overall_passed']}`",
                f"- implementation: `{report['implementation_status']}`",
                "- Godot: `godot_unverified`",
                f"- baseline: `{report['baseline_before_optimization']}`",
                f"- optimized: `{optimized}`",
                f"- session/checkpoint probes: `{session_checkpoint_scales}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"overall_{name.replace('-', '_')}_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
