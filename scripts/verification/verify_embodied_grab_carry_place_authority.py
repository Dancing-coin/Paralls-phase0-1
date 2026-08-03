from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from fastapi.testclient import TestClient

import app.main as backend_main
from app.main import app, reset_runtime_state
from common import ensure_backend, repo_root, resolve_godot_exe, resolve_python_exe, run_command, stop_backend, verification_dir, write_json, write_markdown


TEST_FILES = [
    "backend/tests/test_embodied_grab_carry_place_authority.py",
    "backend/tests/test_embodied_grab_carry_place_godot_static.py",
    "backend/tests/test_embodied_custody_inventory_authority.py",
    "backend/tests/test_default_scene_pickup_authority.py",
]
GODOT_PROBE_SCENE = "res://scenes/phase0/EmbodiedCarryPlaceProbe.tscn"


def _result(check_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": check_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def _websocket_trace(log_dir: Path) -> Path:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "embodied_grab_carry_place_probe",
                "payload": {
                    "session_id": "session:carry-place:verify:1",
                    "asset_ref": "item:crate_01",
                    "actor_ref": "character:siming",
                    "source_holder_ref": "world:anchor:table_01",
                    "drop_target_ref": "world:anchor:floor_slot_01",
                },
            }
        )
        messages = [websocket.receive_json() for _ in range(2)]

    trace_path = log_dir / "embodied-carry-place-websocket-trace.json"
    carry_place_events = [message for message in messages if message.get("message_type") == "embodied_carry_place_event"]
    carry_place_payloads = [message.get("payload", {}) for message in carry_place_events]
    transaction = backend_main.gameplay_event_store.read_transactions()[-1]
    write_json(
        trace_path,
        {
            "messages": messages,
            "carry_place_event_count": len(carry_place_events),
            "carry_place_payloads": carry_place_payloads,
            "transaction_event_types": [event.event_type for event in transaction.events],
            "transaction_ids": sorted({event.transaction_id for event in transaction.events}),
            "possession_projection": backend_main.embodied_carry_place_authority_service.possession_projection("item:crate_01"),
            "drop_target_projection": backend_main.embodied_carry_place_authority_service.drop_target_projection("world:anchor:floor_slot_01"),
            "privacy_scan": {
                "contains_world_truth_claim": "world_truth_claim" in str(carry_place_payloads),
                "contains_character_actor_status": "character_actor_status" in str(carry_place_payloads),
                "contains_private_terms": "participant_private_terms" in str(carry_place_payloads),
            },
        },
    )
    return trace_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    godot_exe = resolve_godot_exe(args.godot_exe)
    pytest_log = log_dir / "embodied-carry-place-pytest.log"
    pytest_result = run_command([python_exe, "-m", "pytest", "-q", *TEST_FILES], project_root, pytest_log)
    websocket_trace_path = _websocket_trace(log_dir)
    websocket_trace = json.loads(websocket_trace_path.read_text(encoding="utf-8"))

    godot_log = log_dir / "embodied-carry-place-godot.log"
    godot_report_path = log_dir / "embodied-carry-place-godot-runtime.json"
    if godot_report_path.exists():
        godot_report_path.unlink()
    backend_process = None
    try:
        _health, backend_process = ensure_backend(project_root, python_exe, prefer_fresh_backend=True)
        godot_result = run_command(
            [
                str(godot_exe),
                "--path",
                str(project_root),
                "--scene",
                GODOT_PROBE_SCENE,
                "--quit-after",
                "120",
                "--headless",
                "--render-thread",
                "safe",
            ],
            project_root,
            godot_log,
            env={
                "EMBODIED_CARRY_PLACE_BACKEND_URL": "ws://127.0.0.1:8000/ws",
                "PHASE0_AUTOTEST": "1",
            },
        )
    finally:
        stop_backend(backend_process)
    godot_report = json.loads(godot_report_path.read_text(encoding="utf-8")) if godot_report_path.exists() else {}

    expected_event_types = [
        "embodied.interaction_session.participant_observed",
        "embodied.interaction_session.participant_observed",
        "inventory.custody_changed",
        "embodied.carry.started",
        "scene.occupancy.changed",
        "embodied.place.settled",
        "embodied.interaction_session.committed",
    ]
    results = [
        _result(
            "focused-pytest-pass",
            "Embodied grab-carry-place backend and Godot static pytest suite passes",
            pytest_result.returncode == 0,
            [str(pytest_log)],
        ),
        _result(
            "atomic-carry-place-batch",
            "Carry-place settles session, custody, occupancy, and mirror directive in one Gameplay transaction",
            websocket_trace["transaction_event_types"] == expected_event_types
            and len(websocket_trace["transaction_ids"]) == 1
            and websocket_trace["possession_projection"]["custody_holder_ref"] == "world:anchor:floor_slot_01"
            and websocket_trace["drop_target_projection"]["occupied_by_ref"] == "item:crate_01",
            [str(websocket_trace_path)],
        ),
        _result(
            "websocket-carry-place-delivery",
            "Committed carry-place event is projected to a Godot websocket envelope without world-truth or private fields",
            websocket_trace["carry_place_event_count"] == 1
            and websocket_trace["carry_place_payloads"][0]["placement_directive"]["authority_only"] is True
            and websocket_trace["privacy_scan"]
            == {
                "contains_world_truth_claim": False,
                "contains_character_actor_status": False,
                "contains_private_terms": False,
            },
            [str(websocket_trace_path)],
        ),
        _result(
            "godot-runtime-carry-place-mirror",
            "Godot live runtime consumes backend-authority carry-place mirror directive without claiming custody",
            godot_result.returncode == 0
            and godot_report.get("status") == "godot-runtime-carry-place-verified"
            and isinstance(godot_report.get("live_backend"), dict)
            and godot_report.get("live_backend", {}).get("accepted") is True,
            [str(godot_log), str(godot_report_path)],
            f"exit_code={godot_result.returncode}",
        ),
    ]
    overall = all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_embodied_grab_carry_place_authority_passed": overall,
        "scope": "Phase 7 grab-carry-place authority proof over Gameplay append_batch/outbox/bus plus Godot BackendBridge mirror consumption",
        "results": results,
        "artifacts": {
            "pytest_log": str(pytest_log),
            "websocket_trace": str(websocket_trace_path),
            "godot_log": str(godot_log),
            "godot_runtime": str(godot_report_path),
        },
    }
    json_path = log_dir / "embodied-grab-carry-place-authority-report.json"
    md_path = log_dir / "embodied-grab-carry-place-authority-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Embodied Grab Carry Place Authority Verification Report", report, "overall_embodied_grab_carry_place_authority_passed")
    print(f"embodied_grab_carry_place_authority_report_json={json_path}")
    print(f"embodied_grab_carry_place_authority_report_md={md_path}")
    print(f"overall_embodied_grab_carry_place_authority_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
