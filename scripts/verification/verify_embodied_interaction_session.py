from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from fastapi.testclient import TestClient

import app.main as backend_main
from app.main import component_app as app, reset_runtime_state
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
    # Keep this on a fresh in-memory actor store so repeated profiles cannot
    # load a stale durable sidecar from a prior run. A domain-owned session is
    # used to verify that the transport denies known and unknown IDs equally.
    previous_graph_path = backend_main.settings.heavenly_graph_path
    backend_main.settings.heavenly_graph_path = ":memory:"
    try:
        reset_runtime_state()
        session_id = "session:handshake:websocket-verify"
        proposed = backend_main.embodied_interaction_session_service.propose(
            session_id=session_id,
            semantic_action="handshake",
            initiator_ref="character:siming",
            participant_refs=["character:siming", "character:maya"],
            target_refs=["character:maya"],
            authority_preflight_ref=f"preflight:{session_id}",
            policy_revision=3,
            scene_revision=11,
            causation_id=f"cmd:{session_id}:propose",
            correlation_id=f"corr:{session_id}",
        )
        if not proposed.accepted:
            raise RuntimeError(f"session_fixture_rejected:{proposed.error_code}")
        before_probe_sequence = backend_main.gameplay_event_store.get_last_global_sequence()
        client = TestClient(app)
        with client.websocket_connect("/ws") as websocket:
            messages = []
            for requested_session_id in (session_id, "session:handshake:unknown"):
                websocket.send_json({
                    "message_type": "embodied_interaction_session_probe",
                    "payload": {
                        "session_id": requested_session_id,
                        "semantic_action": "handshake",
                        "initiator_ref": "character:client-forged",
                        "participant_refs": ["character:client-forged", "character:maya"],
                        "target_refs": ["character:maya"],
                    },
                })
                messages.append(websocket.receive_json())
            for requested_session_id in (session_id, "session:handshake:unknown"):
                websocket.send_json(
                    {
                        "message_type": "embodied_interaction_session_projection_pull",
                        "payload": {
                            "session_id": requested_session_id,
                            "after_global_sequence": 0,
                        },
                    }
                )
                messages.append(websocket.receive_json())
        after_probe_sequence = backend_main.gameplay_event_store.get_last_global_sequence()
    finally:
        backend_main.settings.heavenly_graph_path = previous_graph_path

    expected_probe_denial = {
        "message_type": "ack",
        "payload": {
            "accepted": False,
            "source_type": "embodied_interaction_session_probe",
            "route": "embodied_interaction_session",
            "error_code": "session_access_unavailable",
        },
    }
    expected_pull_denial = {
        "message_type": "embodied_interaction_session_projection_denied",
        "payload": {"error_code": "session_access_unavailable"},
    }
    denied_uniformly = messages == [expected_probe_denial, expected_probe_denial,
                                    expected_pull_denial, expected_pull_denial]
    protected_values_absent = all(
        value not in str(messages)
        for value in (session_id, "session:handshake:unknown", "after_global_sequence")
    )
    unknown_stream_events = backend_main.gameplay_event_store.read_stream("session:session:handshake:unknown")
    trace_path = log_dir / "embodied-interaction-session-websocket-trace.json"
    write_json(
        trace_path,
        {
            "messages": messages,
            "known_and_unknown_denied_uniformly": denied_uniformly,
            "protected_values_absent": protected_values_absent,
            "probe_created_no_events": before_probe_sequence == after_probe_sequence,
            "probe_created_no_unknown_session": unknown_stream_events == [],
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
    # all中该探针会被不同profile调用；新进程也不能复用先前已提交同session的存档。
    with TemporaryDirectory(prefix="paralls-session-") as storage:
        backend_process = None
        try:
            _health, backend_process = ensure_backend(
                project_root, python_exe, prefer_fresh_backend=True,
                env={"PARALLS_HEAVENLY_GRAPH_PATH": str(Path(storage) / "runtime.sqlite3")},
            )
            godot_result = run_command(
                [
                    str(godot_exe),
                    "--path",
                    str(project_root),
                    "--scene",
                    GODOT_PROBE_SCENE,
                    "--headless",
                    "--render-thread",
                    "safe",
                ],
                project_root,
                godot_log,
                # 探针有3秒连接和5秒接收期限；不以循环次数提前截断结构化报告。
                timeout_seconds=30,
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
    expected_sequence = list(
        range(
            trace["global_sequences"][0],
            trace["global_sequences"][0] + len(trace["global_sequences"]),
        )
    )
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
            "websocket-session-authorization-denial",
            "Known and unknown session IDs receive the same denial without returning identifiers or creating a session",
            websocket_trace["known_and_unknown_denied_uniformly"]
            and websocket_trace["protected_values_absent"]
            and websocket_trace["probe_created_no_events"]
            and websocket_trace["probe_created_no_unknown_session"],
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
        "scope": "backend-authority InteractionSession lifecycle plus uniform websocket denial until trusted session visibility evidence is available",
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
    from pathlib import Path
    from run_context import run_scope

    with run_scope(Path(__file__).resolve().parents[2]):
        raise SystemExit(main())
