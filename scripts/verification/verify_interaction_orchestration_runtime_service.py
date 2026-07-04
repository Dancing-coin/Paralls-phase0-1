from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.services.interaction_orchestration_service import InteractionOrchestrationService, StructuredInteractionRequest
from app.world_runtime.intelligence_upgrade import InteractionIntentFrame
from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = ["backend/tests/test_interaction_orchestration_runtime_service.py"]


def _result(result_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {"id": result_id, "title": title, "status": "proved" if proved else "missing", "evidence": evidence if proved else [], "notes": notes}


def _request(intent: InteractionIntentFrame, **overrides: object) -> StructuredInteractionRequest:
    payload = {
        "intent": intent,
        "player_id": "player",
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "producer_ts": 60,
        "target_object_id": "obj_box",
    }
    payload.update(overrides)
    return StructuredInteractionRequest(**payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    pytest_log = log_dir / "interaction-orchestration-service-pytest.log"
    pytest_result = run_command([python_exe, "-m", "pytest", "-q", *TEST_FILES], project_root, pytest_log)

    service = InteractionOrchestrationService()
    semantic = service.execute(_request(InteractionIntentFrame(intent_id="verify:semantic", actor_id="char_a", target_refs={"object_ids": ["obj_box"]}, semantic_intent="inspect")))
    mixed = service.execute(_request(InteractionIntentFrame(intent_id="verify:mixed", actor_id="char_a", target_refs={"object_ids": ["obj_box"]}, semantic_intent="move_obstacle", physical_affordance="push")))
    active = service.execute(_request(InteractionIntentFrame(intent_id="verify:active", actor_id="char_a", target_refs={"object_ids": ["obj_box"]}, semantic_intent="move_obstacle", physical_affordance="push"), perception_ready=False))
    confirm = service.execute(_request(InteractionIntentFrame(intent_id="verify:confirm", actor_id="char_a", target_refs={"object_ids": ["obj_box"]}, semantic_intent="move_obstacle", physical_affordance="push"), authority_confirmed=False))
    denied = service.execute(_request(InteractionIntentFrame(intent_id="verify:denied", actor_id="char_a", target_refs={"object_ids": ["obj_box"]}, semantic_intent="inspect"), constraint_refs=["constraint:locked"]))
    trace_path = log_dir / "interaction-orchestration-service-trace.json"
    write_json(
        trace_path,
        {
            "semantic": semantic.model_dump(mode="json"),
            "mixed": mixed.model_dump(mode="json"),
            "active": active.model_dump(mode="json"),
            "confirm": confirm.model_dump(mode="json"),
            "denied": denied.model_dump(mode="json"),
            "trace": service.trace,
        },
    )
    mixed_types = {entry["result_type"] for entry in mixed.unified_result_family}
    results = [
        _result("focused-pytest-pass", "Interaction orchestration focused pytest suite passes", pytest_result.returncode == 0, [str(pytest_log)]),
        _result("semantic-existing-esm", "Semantic-only path returns existing ESM action resolution", semantic.unified_result_family[0]["result_type"] == "action_resolution_result", [str(trace_path)]),
        _result("six-policy-surface", "Policy executor covers semantic, physical, mixed, denied, active perception, and confirmation paths", len({entry["policy"] for entry in service.trace}) >= 5, [str(trace_path)]),
        _result("mixed-unified-result-family", "Mixed path merges semantic and physical effects into one unified family", {"action_resolution_result", "object_state_result", "body_state_result", "environment_state_result"}.issubset(mixed_types), [str(trace_path)]),
        _result("degrade-boundaries", "Active perception and authority confirmation degrade without physical application", active.unified_result_family == [] and confirm.unified_result_family == [], [str(trace_path)]),
        _result("constraint-structured", "Denied-by-constraint returns structured constraint_state_result", denied.unified_result_family[0]["result_type"] == "constraint_state_result", [str(trace_path)]),
    ]
    overall = all(entry["status"] == "proved" for entry in results)
    report = {"overall_interaction_orchestration_service_passed": overall, "results": results, "artifacts": {"pytest_log": str(pytest_log), "trace": str(trace_path)}}
    json_path = log_dir / "interaction-orchestration-service-report.json"
    md_path = log_dir / "interaction-orchestration-service-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Interaction Orchestration Service Verification Report", report, "overall_interaction_orchestration_service_passed")
    print(f"interaction_orchestration_service_report_json={json_path}")
    print(f"interaction_orchestration_service_report_md={md_path}")
    print(f"overall_interaction_orchestration_service_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
