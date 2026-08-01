from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from fastapi.testclient import TestClient

import app.main as backend_main
from app.main import app, reset_runtime_state
from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.event_store import GameplayEventStore
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.embodied_evidence_ledger import EmbodiedEvidenceLedger
from app.services.embodied_interaction_session_service import EmbodiedInteractionSessionService
from common import ensure_backend, repo_root, resolve_godot_exe, resolve_python_exe, run_command, stop_backend, verification_dir, write_json, write_markdown


TEST_FILES = [
    "backend/tests/test_embodied_interaction_session.py",
    "backend/tests/test_embodied_interaction_session_godot_static.py",
]
GODOT_PROBE_SCENE = "res://scenes/phase0/EmbodiedInteractionSessionProbe.tscn"


def _result(check_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": check_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def _trace(log_dir: Path) -> Path:
    store = GameplayEventStore()
    bus = InMemoryAuthorityEventBus()
    ledger = EmbodiedEvidenceLedger()
    service = EmbodiedInteractionSessionService(
        store=store,
        dispatcher=GameplayOutboxDispatcher(store=store, bus=bus),
        evidence_ledger=ledger,
    )
    service.propose(
        session_id="session:handshake:verify",
        semantic_action="handshake",
        initiator_ref="character:siming",
        participant_refs=["character:siming", "character:maya"],
        target_refs=["character:maya"],
        authority_preflight_ref="preflight:session:handshake:verify",
        policy_revision=3,
        scene_revision=11,
        causation_id="cmd:session:handshake:verify:propose",
        correlation_id="corr:session:handshake:verify",
        participant_private_terms={
            "character:siming": {"relationship_note": "private initiator memory"},
            "character:maya": {"consent_note": "private target context"},
        },
    )
    service.accept(
        session_id="session:handshake:verify",
        participant_ref="character:maya",
        causation_id="cmd:session:handshake:verify:accept",
        payload_digest="digest:accept:verify",
    )
    service.start_realizing(
        session_id="session:handshake:verify",
        causation_id="cmd:session:handshake:verify:realize",
    )
    service.record_terminal_observation(
        session_id="session:handshake:verify",
        participant_ref="character:siming",
        attempt_ref="attempt:handshake:verify:siming",
        terminal_status="completed",
        payload_digest="digest:terminal:verify:siming",
    )
    service.record_terminal_observation(
        session_id="session:handshake:verify",
        participant_ref="character:maya",
        attempt_ref="attempt:handshake:verify:maya",
        terminal_status="completed",
        payload_digest="digest:terminal:verify:maya",
    )
    events = store.read_stream("session:session:handshake:verify")
    bus_payloads = [event.payload for event in bus.list_events()]
    trace_path = log_dir / "embodied-interaction-session-trace.json"
    write_json(
        trace_path,
        {
            "event_types": [event.event_type for event in events],
            "global_sequences": [event.global_sequence for event in events],
            "bus_event_types": [event.event_type for event in bus.list_events()],
            "evidence_kinds": [event.event_kind for event in ledger.events_for_attempt("session:handshake:verify")],
            "public_projection": service.public_projection("session:handshake:verify"),
            "privacy_scan": {
                "store_contains_private_terms": "private target context" in str([event.payload for event in events]),
                "bus_contains_private_terms": "private target context" in str(bus_payloads),
            },
        },
    )
    return trace_path


def _websocket_trace(log_dir: Path) -> Path:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "embodied_interaction_session_probe",
                "payload": {
                    "session_id": "session:handshake:websocket-verify",
                    "semantic_action": "handshake",
                    "initiator_ref": "character:siming",
                    "participant_refs": ["character:siming", "character:maya"],
                    "target_refs": ["character:maya"],
                    "participant_private_terms": {
                        "character:siming": {"relationship_note": "private initiator memory"},
                        "character:maya": {"consent_note": "private target context"},
                    },
                },
            }
        )
        messages = [websocket.receive_json() for _ in range(5)]

    session_messages = [message for message in messages if message.get("message_type") == "embodied_interaction_session_event"]
    session_payloads = [message.get("payload", {}) for message in session_messages]
    bus_events = backend_main.authority_event_bus.list_events()
    store_events = backend_main.gameplay_event_store.read_stream("session:session:handshake:websocket-verify")
    trace_path = log_dir / "embodied-interaction-session-websocket-trace.json"
    write_json(
        trace_path,
        {
            "messages": messages,
            "session_event_types": [payload.get("event_type", "") for payload in session_payloads if isinstance(payload, dict)],
            "session_global_sequences": [payload.get("global_sequence", 0) for payload in session_payloads if isinstance(payload, dict)],
            "store_event_types": [event.event_type for event in store_events],
            "bus_event_types": [event.event_type for event in bus_events],
            "privacy_scan": {
                "websocket_contains_private_terms": "private target context" in str(session_payloads),
                "websocket_reuses_character_actor_status": "character_actor_status" in str(session_payloads),
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
    pytest_log = log_dir / "embodied-interaction-session-pytest.log"
    pytest_result = run_command([python_exe, "-m", "pytest", "-q", *TEST_FILES], project_root, pytest_log)
    godot_log = log_dir / "embodied-interaction-session-godot.log"
    godot_report_path = log_dir / "embodied-interaction-session-godot-runtime.json"
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
                "EMBODIED_INTERACTION_SESSION_BACKEND_URL": "ws://127.0.0.1:8000/ws",
                "PHASE0_AUTOTEST": "1",
            },
        )
    finally:
        stop_backend(backend_process)
    godot_report = json.loads(godot_report_path.read_text(encoding="utf-8")) if godot_report_path.exists() else {}
    trace_path = _trace(log_dir)
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    websocket_trace_path = _websocket_trace(log_dir)
    websocket_trace = json.loads(websocket_trace_path.read_text(encoding="utf-8"))
    expected_sequence = list(range(1, len(trace["global_sequences"]) + 1))
    results = [
        _result(
            "focused-pytest-pass",
            "InteractionSession backend and Godot static pytest suite passes",
            pytest_result.returncode == 0,
            [str(pytest_log)],
        ),
        _result(
            "gameplay-spine-lifecycle",
            "Handshake lifecycle commits through Gameplay append_batch with continuous global sequence",
            trace["event_types"] == [
                "embodied.interaction_session.proposed",
                "embodied.interaction_session.accepted",
                "embodied.interaction_session.authorized",
                "embodied.interaction_session.realizing",
                "embodied.interaction_session.participant_observed",
                "embodied.interaction_session.participant_observed",
                "embodied.interaction_session.committed",
            ]
            and trace["global_sequences"] == expected_sequence,
            [str(trace_path)],
        ),
        _result(
            "outbox-bus-delivery",
            "Committed session events are delivered through the existing authority event bus",
            trace["bus_event_types"] == trace["event_types"],
            [str(trace_path)],
        ),
        _result(
            "websocket-session-delivery",
            "Committed outbox/bus session events are projected to Godot websocket envelopes without private terms",
            websocket_trace["session_event_types"]
            == [
                "embodied.interaction_session.proposed",
                "embodied.interaction_session.accepted",
                "embodied.interaction_session.authorized",
                "embodied.interaction_session.realizing",
            ]
            and websocket_trace["session_global_sequences"] == [1, 2, 3, 4]
            and websocket_trace["store_event_types"] == websocket_trace["bus_event_types"]
            and websocket_trace["privacy_scan"]
            == {
                "websocket_contains_private_terms": False,
                "websocket_reuses_character_actor_status": False,
            },
            [str(websocket_trace_path)],
        ),
        _result(
            "same-evidence-ledger",
            "Session lifecycle and terminal participation observations use the embodied evidence ledger",
            trace["evidence_kinds"] == [
                "session_lifecycle",
                "session_lifecycle",
                "session_lifecycle",
                "session_lifecycle",
                "participant_terminal_observation",
                "participant_terminal_observation",
                "settlement",
            ],
            [str(trace_path)],
        ),
        _result(
            "privacy-filtering",
            "Public projection and bus delivery do not expose private participant terms",
            trace["privacy_scan"] == {
                "store_contains_private_terms": False,
                "bus_contains_private_terms": False,
            },
            [str(trace_path)],
        ),
        _result(
            "godot-runtime-slot-consumer",
            "Godot InteractionSession slot consumer accepts safe session projections and emits bounded terminal participation observation",
            godot_result.returncode == 0
            and godot_report.get("status") == "godot-runtime-interaction-session-verified"
            and godot_report.get("bridge_route_ok") is True
            and godot_report.get("bus_signal_ok") is True
            and godot_report.get("bridge_legacy_reuse") is False
            and isinstance(godot_report.get("live_backend"), dict)
            and godot_report.get("live_backend", {}).get("accepted") is True,
            [str(godot_log), str(godot_report_path)],
            f"exit_code={godot_result.returncode}",
        ),
    ]
    overall = all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_embodied_interaction_session_passed": overall,
        "godot_runtime_verified": godot_report.get("status") == "godot-runtime-interaction-session-verified",
        "scope": "backend-authority InteractionSession lifecycle over Gameplay event spine plus websocket delivery to Godot runtime slot consumer",
        "results": results,
        "artifacts": {
            "pytest_log": str(pytest_log),
            "trace": str(trace_path),
            "websocket_trace": str(websocket_trace_path),
            "godot_log": str(godot_log),
            "godot_runtime": str(godot_report_path),
        },
    }
    json_path = log_dir / "embodied-interaction-session-report.json"
    md_path = log_dir / "embodied-interaction-session-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Embodied Interaction Session Verification Report", report, "overall_embodied_interaction_session_passed")
    print(f"embodied_interaction_session_report_json={json_path}")
    print(f"embodied_interaction_session_report_md={md_path}")
    print(f"overall_embodied_interaction_session_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
