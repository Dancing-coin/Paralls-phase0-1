from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.services.interaction_orchestration_service import InteractionOrchestrationService, StructuredInteractionRequest
from app.services.physical_interaction_channel import PhysicalInteractionChannel, PhysicalInteractionRequest
from app.world_runtime.intelligence_upgrade import InteractionIntentFrame
from common import read_text, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = ["backend/tests/test_esm_physical_channel_runtime.py"]


def _result(result_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {"id": result_id, "title": title, "status": "proved" if proved else "missing", "evidence": evidence if proved else [], "notes": notes}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    pytest_log = log_dir / "esm-physical-channel-world-actuation-pytest.log"
    pytest_result = run_command([python_exe, "-m", "pytest", "-q", *TEST_FILES], project_root, pytest_log)
    godot_log = log_dir / "esm-physical-channel-world-actuation-godot.log"
    godot_runtime_artifact = log_dir / "esm-physical-channel-godot-runtime.json"
    godot_ok = False
    godot_status = "godot-runtime-unverified"
    if args.godot_exe:
        godot_result = run_command(
            [
                args.godot_exe,
                "--path",
                str(project_root),
                "--scene",
                "res://scenes/phase0/PhysicalInteractionRuntimeProbe.tscn",
                "--quit-after",
                "300",
                "--render-thread",
                "safe",
            ],
            project_root,
            godot_log,
        )
        godot_text = read_text(godot_log)
        godot_ok = (
            godot_result.returncode == 0
            and "physical_interaction_runtime_probe:structured_refs=true" in godot_text
            and godot_runtime_artifact.exists()
        )
        godot_status = "godot-runtime-physical-interaction-verified" if godot_ok else "godot-runtime-unverified"

    channel = PhysicalInteractionChannel()
    applied = channel.apply(
        PhysicalInteractionRequest(
            request_id="physical:verify:push",
            actor_id="char_a",
            room_id="room_demo",
            target_object_id="obj_box",
            effect_kind="push",
            semantic_approved=True,
            authority_ref="action_resolution:verify",
            producer_ts=70,
        )
    )
    blocked = channel.apply(
        PhysicalInteractionRequest(
            request_id="physical:verify:blocked",
            actor_id="char_a",
            room_id="room_demo",
            target_object_id="obj_box",
            effect_kind="push",
            semantic_approved=False,
            producer_ts=70,
        )
    )
    mixed = InteractionOrchestrationService().execute(
        StructuredInteractionRequest(
            intent=InteractionIntentFrame(
                intent_id="verify:physical:mixed",
                actor_id="char_a",
                target_refs={"object_ids": ["obj_box"]},
                semantic_intent="move_obstacle",
                physical_affordance="push",
            ),
            player_id="player",
            room_id="room_demo",
            target_object_id="obj_box",
            producer_ts=70,
        )
    )
    probe_text = read_text(project_root / "scripts" / "interaction" / "PhysicalInteractionProbe.gd")
    adapter_text = read_text(project_root / "scripts" / "interaction" / "PhysicalInteractionAdapter.gd")
    godot_static_ok = all(
        marker in (probe_text + adapter_text)
        for marker in [
            "sample_contact_ref",
            "semantic_success_decision_allowed := false",
            "raw_physics_stream_to_backend_allowed := false",
            "structured_refs_only := true",
            "bypass_semantic_authority_allowed := false",
            "second_world_result_protocol_allowed := false",
            "object_state_observation_refs",
            "environment_state_observation_refs",
            "body_state_observation_refs",
        ]
    )
    trace_path = log_dir / "esm-physical-channel-world-actuation-trace.json"
    try:
        godot_runtime_payload = json.loads(godot_runtime_artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        godot_runtime_payload = {}
    write_json(
        trace_path,
        {
            "applied": applied.model_dump(mode="json"),
            "blocked": blocked.model_dump(mode="json"),
            "mixed": mixed.model_dump(mode="json"),
            "godot_runtime_status": godot_status,
            "godot_runtime_artifact": godot_runtime_payload,
            "godot_static_adapter_probe": {
                "probe": "scripts/interaction/PhysicalInteractionProbe.gd",
                "adapter": "scripts/interaction/PhysicalInteractionAdapter.gd",
                "static_contract_ok": godot_static_ok,
            },
        },
    )
    applied_types = {entry["result_type"] for entry in applied.unified_results}
    mixed_types = {entry["result_type"] for entry in mixed.unified_result_family}
    results = [
        _result("focused-pytest-pass", "ESM physical channel focused pytest suite passes", pytest_result.returncode == 0, [str(pytest_log)]),
        _result("structured-physical-effect", "Physical effect has structured effect and observation refs", applied.effect_applied and bool(applied.structured_physical_effect_refs), [str(trace_path)]),
        _result("unified-result-family", "Physical effect returns existing unified result family entries", {"object_state_result", "body_state_result", "environment_state_result"}.issubset(applied_types), [str(trace_path)]),
        _result("constraint-prevents-application", "Constraint failure prevents physical application", not blocked.effect_applied and blocked.unified_results[0]["result_type"] == "constraint_state_result", [str(trace_path)]),
        _result("orchestration-merge", "Physical effect merges through Interaction Orchestration Service", {"action_resolution_result", "object_state_result", "body_state_result", "environment_state_result"}.issubset(mixed_types), [str(trace_path)]),
        _result("godot-adapter-probe-static-contract", "Godot adapter/probe emit structured refs only and forbid semantic/world-truth bypass", godot_static_ok, ["scripts/interaction/PhysicalInteractionProbe.gd", "scripts/interaction/PhysicalInteractionAdapter.gd"]),
        {
            "id": "godot-runtime-physical-probe",
            "title": "Godot runtime physical probe emits contact/body/object/environment refs",
            "status": "proved" if godot_ok else godot_status,
            "evidence": [str(godot_log), str(godot_runtime_artifact)] if args.godot_exe else [],
            "notes": "" if godot_ok else "Godot unavailable or physical runtime probe did not produce a structured artifact.",
        },
    ]
    overall = all(entry["status"] == "proved" for entry in results)
    overall = overall and godot_ok
    report = {
        "overall_esm_physical_channel_world_actuation_passed": overall,
        "godot_runtime_status": godot_status,
        "results": results,
        "artifacts": {"pytest_log": str(pytest_log), "godot_log": str(godot_log), "godot_runtime": str(godot_runtime_artifact), "trace": str(trace_path)},
    }
    json_path = log_dir / "esm-physical-channel-world-actuation-report.json"
    md_path = log_dir / "esm-physical-channel-world-actuation-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "ESM Physical Channel World Actuation Verification Report", report, "overall_esm_physical_channel_world_actuation_passed")
    print(f"esm_physical_channel_world_actuation_report_json={json_path}")
    print(f"esm_physical_channel_world_actuation_report_md={md_path}")
    print(f"overall_esm_physical_channel_world_actuation_passed={overall}")
    print(f"godot_runtime_status={godot_status}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
