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
    "backend/tests/test_embodied_handoff_authority.py",
    "backend/tests/test_embodied_handoff_godot_static.py",
]
GODOT_PROBE_SCENE = "res://scenes/phase0/EmbodiedHandoffProbe.tscn"


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
                "message_type": "embodied_handoff_probe",
                "payload": {
                    "session_id": "session:handoff:verify:1",
                    "asset_ref": "item:letter_01",
                    "from_actor_ref": "character:siming",
                    "to_actor_ref": "character:maya",
                },
            }
        )
        messages = [websocket.receive_json() for _ in range(2)]

    trace_path = log_dir / "embodied-handoff-websocket-trace.json"
    handoff_events = [message for message in messages if message.get("message_type") == "embodied_handoff_event"]
    handoff_payloads = [message.get("payload", {}) for message in handoff_events]
    transaction = backend_main.gameplay_event_store.read_transactions()[-1]
    write_json(
        trace_path,
        {
            "messages": messages,
            "handoff_event_count": len(handoff_events),
            "handoff_payloads": handoff_payloads,
            "transaction_event_types": [event.event_type for event in transaction.events],
            "transaction_ids": sorted({event.transaction_id for event in transaction.events}),
            "projection": backend_main.embodied_handoff_authority_service.possession_projection("item:letter_01"),
            "privacy_scan": {
                "contains_world_truth_claim": "world_truth_claim" in str(handoff_payloads),
                "contains_character_actor_status": "character_actor_status" in str(handoff_payloads),
                "contains_private_terms": "participant_private_terms" in str(handoff_payloads),
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
    pytest_log = log_dir / "embodied-handoff-pytest.log"
    pytest_result = run_command([python_exe, "-m", "pytest", "-q", *TEST_FILES], project_root, pytest_log)
    websocket_trace_path = _websocket_trace(log_dir)
    websocket_trace = json.loads(websocket_trace_path.read_text(encoding="utf-8"))

    godot_log = log_dir / "embodied-handoff-godot.log"
    godot_report_path = log_dir / "embodied-handoff-godot-runtime.json"
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
                "EMBODIED_HANDOFF_BACKEND_URL": "ws://127.0.0.1:8000/ws",
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
        "ownership.right_transferred",
        "embodied.handoff.settled",
        "embodied.interaction_session.committed",
    ]
    results = [
        _result(
            "focused-pytest-pass",
            "Embodied handoff backend and Godot static pytest suite passes",
            pytest_result.returncode == 0,
            [str(pytest_log)],
        ),
        _result(
            "atomic-handoff-batch",
            "Handoff settles session, custody, ownership, and mirror directive in one Gameplay transaction",
            websocket_trace["transaction_event_types"] == expected_event_types
            and len(websocket_trace["transaction_ids"]) == 1
            and websocket_trace["projection"]["custody_holder_ref"] == "character:maya"
            and websocket_trace["projection"]["owner_ref"] == "character:maya",
            [str(websocket_trace_path)],
        ),
        _result(
            "websocket-handoff-delivery",
            "Committed handoff event is projected to a Godot websocket envelope without world-truth or private fields",
            websocket_trace["handoff_event_count"] == 1
            and websocket_trace["handoff_payloads"][0]["attachment_directive"]["authority_only"] is True
            and websocket_trace["privacy_scan"]
            == {
                "contains_world_truth_claim": False,
                "contains_character_actor_status": False,
                "contains_private_terms": False,
            },
            [str(websocket_trace_path)],
        ),
        _result(
            "godot-runtime-handoff-mirror",
            "Godot live runtime consumes backend-authority handoff mirror directive without claiming ownership",
            godot_result.returncode == 0
            and godot_report.get("status") == "godot-runtime-handoff-verified"
            and isinstance(godot_report.get("live_backend"), dict)
            and godot_report.get("live_backend", {}).get("accepted") is True,
            [str(godot_log), str(godot_report_path)],
            f"exit_code={godot_result.returncode}",
        ),
    ]
    overall = all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_embodied_handoff_authority_passed": overall,
        "scope": "Phase 7 narrow handoff authority slice over Gameplay append_batch/outbox/bus plus Godot BackendBridge mirror consumption",
        "results": results,
        "artifacts": {
            "pytest_log": str(pytest_log),
            "websocket_trace": str(websocket_trace_path),
            "godot_log": str(godot_log),
            "godot_runtime": str(godot_report_path),
        },
    }
    json_path = log_dir / "embodied-handoff-authority-report.json"
    md_path = log_dir / "embodied-handoff-authority-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Embodied Handoff Authority Verification Report", report, "overall_embodied_handoff_authority_passed")
    print(f"embodied_handoff_authority_report_json={json_path}")
    print(f"embodied_handoff_authority_report_md={md_path}")
    print(f"overall_embodied_handoff_authority_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
