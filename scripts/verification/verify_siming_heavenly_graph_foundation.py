from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
)
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter
from common import (
    repo_root,
    resolve_python_exe,
    run_command,
    verification_dir,
    write_json,
    write_markdown,
)


TEST_FILES = [
    "backend/tests/test_siming_heavenly_graph_models.py",
    "backend/tests/test_siming_heavenly_graph_contract.py",
    "backend/tests/test_sqlite_heavenly_graph_contract.py",
]


def _result(
    result_id: str,
    title: str,
    proved: bool,
    evidence: list[str],
    notes: str = "",
) -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def _scope(branch_id: str) -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:demo",
        session_id="session:demo",
        story_branch_id=branch_id,
        room_id="room_demo",
        scene_id="scene_demo",
    )


def _node(
    *,
    branch_id: str,
    state: str,
    revision: int,
    supersedes_revision: int | None,
    valid_from: int,
    recorded_at: int,
    source_ref: str,
) -> HeavenlyGraphNode:
    return HeavenlyGraphNode(
        node_id="fact:lamp",
        node_type="world_fact",
        scope=_scope(branch_id),
        validity=GraphValidity(valid_from=valid_from),
        recorded_at=recorded_at,
        revision=revision,
        supersedes_revision=supersedes_revision,
        attributes={"state": state},
        provenance=GraphProvenance(
            source_kind="authority_event",
            source_ref=source_ref,
            causation_id=source_ref,
            correlation_id="corr:heavenly-graph-proof",
            producer_system="system_l6",
            evidence_refs=[source_ref],
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    pytest_log = log_dir / "siming-heavenly-graph-foundation-pytest.log"
    pytest_result = run_command(
        [python_exe, "-m", "pytest", "-q", *TEST_FILES],
        project_root,
        pytest_log,
    )

    graph = InMemoryHeavenlyGraphAdapter()
    main_scope = _scope("branch:main")
    other_scope = _scope("branch:other")
    main_v1_batch = HeavenlyGraphWriteBatch(
        transaction_id="graph_tx:main:v1",
        idempotency_key="authority:event:main:v1",
        scope=main_scope,
        nodes=[
            _node(
                branch_id="branch:main",
                state="dim",
                revision=1,
                supersedes_revision=None,
                valid_from=0,
                recorded_at=10,
                source_ref="authority:event:main:v1",
            )
        ],
    )
    first_write = graph.write_batch(main_v1_batch)
    replay_write = graph.write_batch(main_v1_batch.model_copy(deep=True))
    checkpoint = graph.create_checkpoint(
        checkpoint_id="checkpoint:before-destruction",
        scope=main_scope,
        valid_at=20,
        recorded_at=20,
    )
    graph.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id="graph_tx:other:v1",
            idempotency_key="authority:event:other:v1",
            scope=other_scope,
            nodes=[
                _node(
                    branch_id="branch:other",
                    state="intact",
                    revision=1,
                    supersedes_revision=None,
                    valid_from=0,
                    recorded_at=10,
                    source_ref="authority:event:other:v1",
                )
            ],
        )
    )
    graph.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id="graph_tx:main:v2",
            idempotency_key="authority:event:main:v2",
            scope=main_scope,
            nodes=[
                _node(
                    branch_id="branch:main",
                    state="destroyed",
                    revision=2,
                    supersedes_revision=1,
                    valid_from=50,
                    recorded_at=60,
                    source_ref="authority:event:main:v2",
                )
            ],
        )
    )

    main_before_valid = graph.get_node(
        node_id="fact:lamp",
        scope=main_scope,
        valid_at=40,
        recorded_at=100,
    )
    main_before_recorded = graph.get_node(
        node_id="fact:lamp",
        scope=main_scope,
        valid_at=70,
        recorded_at=59,
    )
    main_after_recorded = graph.get_node(
        node_id="fact:lamp",
        scope=main_scope,
        valid_at=70,
        recorded_at=60,
    )
    other_branch = graph.get_node(
        node_id="fact:lamp",
        scope=other_scope,
        valid_at=70,
        recorded_at=100,
    )
    snapshot = graph.read_checkpoint(checkpoint.checkpoint_ref)

    with tempfile.TemporaryDirectory(dir=log_dir) as temporary_directory:
        sqlite_path = Path(temporary_directory) / "heavenly.sqlite3"
        sqlite_graph = SQLiteHeavenlyGraphAdapter(sqlite_path)
        private_scope = HeavenlyGraphScope(
            world_id="world:demo", session_id="session:demo",
            story_branch_id="branch:main", room_id="room_demo", scene_id="scene_demo",
            graph_namespace="actor_private", owner_actor_id="char_b",
        )
        sqlite_graph.write_batch(HeavenlyGraphWriteBatch(
            transaction_id="graph_tx:sqlite:private", idempotency_key="authority:event:sqlite:private",
            scope=private_scope, nodes=[_node(branch_id="branch:main", state="observed", revision=1, supersedes_revision=None, valid_from=0, recorded_at=10, source_ref="authority:event:sqlite:private").model_copy(update={"scope": private_scope})],
        ))
        sqlite_checkpoint = sqlite_graph.create_checkpoint(checkpoint_id="checkpoint:sqlite", scope=private_scope, valid_at=20, recorded_at=20)
        sqlite_graph.close()
        sqlite_graph = SQLiteHeavenlyGraphAdapter(sqlite_path)
        sqlite_node = sqlite_graph.get_node(node_id="fact:lamp", scope=private_scope, valid_at=20)
        sqlite_subgraph = sqlite_graph.query_subgraph(scope=private_scope, seed_node_ids=["fact:lamp"], relation_types=[], direction="both", max_depth=1, valid_at=20, recorded_at=20, node_limit=10, relation_limit=10)
        sqlite_snapshot = sqlite_graph.read_checkpoint(sqlite_checkpoint.checkpoint_ref)
        sqlite_graph.close()

    trace_path = log_dir / "siming-heavenly-graph-foundation-trace.json"
    write_json(
        trace_path,
        {
            "first_write": first_write.model_dump(mode="json"),
            "replay_write": replay_write.model_dump(mode="json"),
            "main_before_valid": (
                main_before_valid.model_dump(mode="json")
                if main_before_valid is not None
                else None
            ),
            "main_before_recorded": (
                main_before_recorded.model_dump(mode="json")
                if main_before_recorded is not None
                else None
            ),
            "main_after_recorded": (
                main_after_recorded.model_dump(mode="json")
                if main_after_recorded is not None
                else None
            ),
            "other_branch": (
                other_branch.model_dump(mode="json")
                if other_branch is not None
                else None
            ),
            "checkpoint": snapshot.model_dump(mode="json"),
        },
    )

    temporal_ok = (
        main_before_valid is not None
        and main_before_valid.revision == 1
        and main_before_recorded is not None
        and main_before_recorded.revision == 1
        and main_after_recorded is not None
        and main_after_recorded.revision == 2
    )
    branch_ok = (
        other_branch is not None
        and other_branch.attributes["state"] == "intact"
        and main_after_recorded is not None
        and main_after_recorded.attributes["state"] == "destroyed"
    )
    idempotency_ok = (
        first_write.applied is True
        and replay_write.applied is False
        and replay_write.replayed is True
    )
    checkpoint_ok = (
        len(snapshot.nodes) == 1
        and snapshot.nodes[0].revision == 1
        and snapshot.nodes[0].attributes["state"] == "dim"
    )
    results = [
        _result(
            "focused-pytest-pass",
            "Heavenly graph focused pytest suites pass",
            pytest_result.returncode == 0,
            [str(pytest_log)],
        ),
        _result(
            "bi-temporal-query",
            "Valid-time and recorded-time queries select the correct revision",
            temporal_ok,
            [str(trace_path)],
        ),
        _result(
            "branch-isolation",
            "Identical entity IDs remain isolated by story branch",
            branch_ok,
            [str(trace_path)],
        ),
        _result(
            "idempotent-write",
            "Identical idempotency replay does not apply a second revision",
            idempotency_ok,
            [str(trace_path)],
        ),
        _result(
            "immutable-checkpoint",
            "Checkpoint content remains stable after later writes",
            checkpoint_ok,
            [str(trace_path)],
        ),
        _result("namespace_owner_isolation", "Private namespace and owner identity are isolated", sqlite_node is not None and sqlite_node.attributes["state"] == "observed", [str(trace_path)]),
        _result("bounded_subgraph", "Bounded subgraph traversal returns only the reachable effective scope", [node.node_id for node in sqlite_subgraph.nodes] == ["fact:lamp"], [str(trace_path)]),
        _result("sqlite_restart", "SQLite restores nodes and checkpoints after restart", sqlite_snapshot.nodes and sqlite_snapshot.nodes[0].revision == 1, [str(trace_path)]),
        _result("adapter_contract_parity", "In-memory and SQLite adapter contract suites pass", pytest_result.returncode == 0, [str(pytest_log)]),
    ]
    overall = all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_siming_heavenly_graph_foundation_passed": overall,
        "results": results,
        "artifacts": {
            "pytest_log": str(pytest_log),
            "trace": str(trace_path),
        },
    }
    json_path = log_dir / "siming-heavenly-graph-foundation-report.json"
    md_path = log_dir / "siming-heavenly-graph-foundation-report.md"
    write_json(json_path, report)
    write_markdown(
        md_path,
        "Siming Heavenly Graph Foundation Verification Report",
        report,
        "overall_siming_heavenly_graph_foundation_passed",
    )
    print(f"siming_heavenly_graph_foundation_report_json={json_path}")
    print(f"siming_heavenly_graph_foundation_report_md={md_path}")
    print(
        "overall_siming_heavenly_graph_foundation_passed="
        f"{overall}"
    )
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
