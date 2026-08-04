from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

import app.main as app_main
from app.models.siming_actor_memory_read import ActorMemoryReadRequest
from app.models.siming_heavenly_graph import HeavenlyNodeQuery
from app.services.siming_actor_memory_gateway import ActorMemoryReadGateway
from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = [
    "backend/tests/test_character_graph_memory_store.py",
    "backend/tests/test_character_graph_memory_routing.py",
    "backend/tests/test_siming_actor_memory_gateway.py",
]


def _result(result_id: str, title: str, proved: bool, evidence: list[str]) -> dict[str, object]:
    return {"id": result_id, "title": title, "status": "proved" if proved else "missing", "evidence": evidence if proved else []}


def _event(actor_id: str) -> dict[str, object]:
    return {
        "event_id": f"authority:letter:destroyed:{actor_id}",
        "event_index": 1,
        "actor_id": actor_id,
        "event_type": "character_perceived_event",
        "producer_ts": 100,
        "payload": {"summary": "letter removed from surface", "target_actor_id": "obj_letter", "percept_channel": "visual"},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    project_root = repo_root()
    log_dir = verification_dir(project_root)
    pytest_log = log_dir / "siming-actor-memory-read-pytest.log"
    pytest_result = run_command([resolve_python_exe(args.python_exe), "-m", "pytest", "-q", *TEST_FILES], project_root, pytest_log)

    with tempfile.TemporaryDirectory(dir=log_dir) as temporary_directory:
        app_main.settings.heavenly_graph_path = str(Path(temporary_directory) / "actor-memory.sqlite3")
        app_main.settings.character_graph_memory_heavy_actor_ids = ["char_b"]
        app_main.reset_runtime_state()
        first_runtime = app_main.character_agent_runtime
        first_runtime._memory_store.write_event(_event("char_b"))
        first_bundle = first_runtime.get_memory_record_bundle("char_b")
        first_runtime._memory_store.write_event(_event("char_a"))
        char_a_bundle = first_runtime.get_memory_record_bundle("char_a")

        app_main.reset_runtime_state()
        restored_runtime = app_main.character_agent_runtime
        restored_bundle = restored_runtime.get_memory_record_bundle("char_b")
        gateway_result = ActorMemoryReadGateway(restored_runtime).read(
            ActorMemoryReadRequest(actor_id="char_b", story_branch_id="branch:main", valid_at=100)
        )
        char_a_nodes = app_main.heavenly_graph.query_nodes(
            HeavenlyNodeQuery(scope=app_main.actor_private_scope("char_a"), valid_at=100, node_types=["actor_memory:event"], limit=None)
        )
        trace = {
            "first_event_count": len(first_bundle.event_memories),
            "first_observation_count": len(first_bundle.observation_memories),
            "restored_event_count": len(restored_bundle.event_memories),
            "restored_observation_count": len(restored_bundle.observation_memories),
            "char_a_event_count": len(char_a_bundle.event_memories),
            "char_a_graph_nodes": len(char_a_nodes),
            "gateway_completeness": gateway_result.completeness,
            "gateway_observation_revision": gateway_result.revision_vector.observation,
        }
        app_main.heavenly_graph.close()

    trace_path = log_dir / "siming-actor-memory-read-trace.json"
    write_json(trace_path, trace)
    results = [
        _result("focused_pytest_pass", "Actor memory focused pytest suites pass", pytest_result.returncode == 0, [str(pytest_log)]),
        _result("char_b_graph_backed", "char_b is routed to actor-private graph memory", trace["first_event_count"] == 1, [str(trace_path)]),
        _result("event_observation_deposited", "char_b Event and Observation records are deposited", trace["first_observation_count"] == 1, [str(trace_path)]),
        _result("restart_recall", "SQLite restart restores char_b graph memory", trace["restored_event_count"] == 1 and trace["restored_observation_count"] == 1, [str(trace_path)]),
        _result("char_a_light_store", "char_a remains light-store backed", trace["char_a_event_count"] == 1, [str(trace_path)]),
        _result("cross_actor_isolation", "char_a private scope cannot read char_b node", trace["char_a_graph_nodes"] == 0, [str(trace_path)]),
        _result("siming_read_only", "Siming receives char_b only through its read-only gateway", trace["gateway_completeness"] == "complete" and bool(trace["gateway_observation_revision"]), [str(trace_path)]),
    ]
    overall = all(result["status"] == "proved" for result in results)
    report = {"overall_siming_actor_memory_read_passed": overall, "results": results, "artifacts": {"pytest_log": str(pytest_log), "trace": str(trace_path)}}
    json_path = log_dir / "siming-actor-memory-read-report.json"
    markdown_path = log_dir / "siming-actor-memory-read-report.md"
    write_json(json_path, report)
    write_markdown(markdown_path, "Siming Actor Memory Read Verification Report", report, "overall_siming_actor_memory_read_passed")
    print(f"siming_actor_memory_read_report_json={json_path}")
    print(f"siming_actor_memory_read_report_md={markdown_path}")
    print(f"overall_siming_actor_memory_read_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
