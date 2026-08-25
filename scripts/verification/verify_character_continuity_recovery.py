from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app import config as config_module
from app import main
from app.models.character_perceived import CharacterPerceivedEvent
from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = ["backend/tests/test_character_graph_continuity_store.py"]


def _event(ts: int, summary: str) -> CharacterPerceivedEvent:
    return CharacterPerceivedEvent(
        actor_id="char_b",
        percept_channel="visual",
        producer_ts=ts,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary=summary,
        source_candidate_event_id=f"continuity:{ts}",
    )


def _result(result_id: str, title: str, proved: bool, evidence: list[str]) -> dict[str, object]:
    return {"id": result_id, "title": title, "status": "proved" if proved else "missing", "evidence": evidence if proved else []}


def main_verify(python_exe: str | None) -> int:
    project_root = repo_root()
    log_dir = verification_dir(project_root)
    pytest_log = log_dir / "character-continuity-recovery-pytest.log"
    pytest_result = run_command(
        [resolve_python_exe(python_exe), "-m", "pytest", "-q", *TEST_FILES],
        project_root,
        pytest_log,
    )
    previous_override = os.environ.get("CHARACTER_MODEL_ROUTE_OVERRIDE")
    os.environ["CHARACTER_MODEL_ROUTE_OVERRIDE"] = "local_only"
    try:
        with tempfile.TemporaryDirectory(dir=log_dir) as temp_dir:
            graph_path = Path(temp_dir) / "character-continuity.sqlite3"
            settings = config_module.Settings(
                heavenly_graph_path=str(graph_path),
                siming_heavenly_mode="off",
            )
            first = main.build_runtime_state(settings)
            first.character_agent_runtime.ingest_character_perceived_event(_event(300, "letter visible"))
            first.character_agent_runtime.record_settlement_result(
                actor_id="char_b",
                producer_ts=301,
                payload={
                    "result_id": "continuity:result:301",
                    "result_type": "constraint_state_result",
                    "settlement_status": "rejected",
                    "constraint_summary": "too far",
                    "causation_id": "continuity:cause:301",
                    "correlation_id": "continuity:corr:301",
                },
            )
            before = {
                "dynamic": first.character_agent_runtime.get_dynamic_state("char_b"),
                "need": first.character_agent_runtime.get_need_tension_state("char_b"),
                "goal": first.character_agent_runtime.get_goal_state("char_b"),
                "continuity": first.character_agent_runtime.get_runtime_continuity_state("char_b"),
                "working_memory": first.character_agent_runtime.get_working_memory_state("char_b"),
            }
            first.close()
            session_file = graph_path.parent / f"{graph_path.name}.character-agent" / "character_agent_session_store.json"
            if session_file.exists():
                session_file.unlink()

            second = main.build_runtime_state(settings)
            after = {
                "dynamic": second.character_agent_runtime.get_dynamic_state("char_b"),
                "need": second.character_agent_runtime.get_need_tension_state("char_b"),
                "goal": second.character_agent_runtime.get_goal_state("char_b"),
                "continuity": second.character_agent_runtime.get_runtime_continuity_state("char_b"),
                "working_memory": second.character_agent_runtime.get_working_memory_state("char_b"),
            }
            second.character_agent_runtime.ingest_character_perceived_event(_event(302, "letter remains visible"))
            next_timeline = second.character_agent_runtime.get_session_timeline("char_b")
            second.close()
            trace = {
                "before": before,
                "after": after,
                "next_timeline_event_count": len(next_timeline),
                "session_file_absent": not session_file.exists(),
            }
    finally:
        if previous_override is None:
            os.environ.pop("CHARACTER_MODEL_ROUTE_OVERRIDE", None)
        else:
            os.environ["CHARACTER_MODEL_ROUTE_OVERRIDE"] = previous_override

    trace_path = log_dir / "character-continuity-recovery-trace.json"
    write_json(trace_path, trace)
    results = [
        _result("focused_pytest_pass", "Continuity focused tests pass", pytest_result.returncode == 0, [str(pytest_log)]),
        _result("dynamic_state_recovered", "Dynamic state rebuilds from graph", trace["before"]["dynamic"] == trace["after"]["dynamic"], [str(trace_path)]),
        _result("need_tension_recovered", "Need/tension rebuilds from graph", trace["before"]["need"] == trace["after"]["need"], [str(trace_path)]),
        _result("goal_and_continuity_recovered", "Goal and continuity rebuild from graph", trace["before"]["goal"] == trace["after"]["goal"] and trace["before"]["continuity"] == trace["after"]["continuity"], [str(trace_path)]),
        _result("working_memory_recovered", "Working memory and next input remain available", bool(trace["after"]["working_memory"]) and trace["next_timeline_event_count"] > 0, [str(trace_path)]),
        _result("session_json_not_required", "Graph continuity does not require session JSON", trace.get("session_file_absent", False), [str(trace_path)]),
    ]
    overall = all(item["status"] == "proved" for item in results)
    report = {
        "overall_character_continuity_recovery_passed": overall,
        "scope": "graph-backed character continuity; no Siming, six-domain Authority, online LLM, or Godot claim",
        "results": results,
        "artifacts": {"pytest_log": str(pytest_log), "trace": str(trace_path)},
    }
    json_path = log_dir / "character-continuity-recovery-report.json"
    markdown_path = log_dir / "character-continuity-recovery-report.md"
    write_json(json_path, report)
    write_markdown(markdown_path, "Character Continuity Recovery Verification Report", report, "overall_character_continuity_recovery_passed")
    print(f"character_continuity_recovery_report_json={json_path}")
    print(f"overall_character_continuity_recovery_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    raise SystemExit(main_verify(args.python_exe))
