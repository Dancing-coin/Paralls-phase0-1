from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as main
from app.main import app, reset_runtime_state
from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.event_store import GameplayEventStore
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.embodied_evidence_ledger import EmbodiedEvidenceLedger
from app.services.embodied_interaction_session_service import EmbodiedInteractionSessionService


def _service() -> tuple[EmbodiedInteractionSessionService, GameplayEventStore, InMemoryAuthorityEventBus, EmbodiedEvidenceLedger]:
    store = GameplayEventStore()
    bus = InMemoryAuthorityEventBus()
    ledger = EmbodiedEvidenceLedger()
    service = EmbodiedInteractionSessionService(
        store=store,
        dispatcher=GameplayOutboxDispatcher(store=store, bus=bus),
        evidence_ledger=ledger,
    )
    return service, store, bus, ledger


def _propose(service: EmbodiedInteractionSessionService, *, session_id: str = "session:handshake:1") -> object:
    return service.propose(
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
        participant_private_terms={
            "character:siming": {"relationship_note": "private initiator memory"},
            "character:maya": {"consent_note": "private target context"},
        },
    )


def test_handshake_acceptance_commits_session_events_through_gameplay_spine_and_requires_both_terminal_observations() -> None:
    service, store, bus, ledger = _service()

    proposed = _propose(service)
    accepted = service.accept(
        session_id="session:handshake:1",
        participant_ref="character:maya",
        causation_id="cmd:session:handshake:1:accept",
        payload_digest="digest:accept:maya",
    )
    realizing = service.start_realizing(
        session_id="session:handshake:1",
        causation_id="cmd:session:handshake:1:realize",
    )
    first_observation = service.record_terminal_observation(
        session_id="session:handshake:1",
        participant_ref="character:siming",
        attempt_ref="attempt:handshake:siming",
        terminal_status="completed",
        payload_digest="digest:terminal:siming",
    )
    committed = service.record_terminal_observation(
        session_id="session:handshake:1",
        participant_ref="character:maya",
        attempt_ref="attempt:handshake:maya",
        terminal_status="completed",
        payload_digest="digest:terminal:maya",
    )

    assert proposed.accepted is True
    assert accepted.session is not None
    assert accepted.session.state == "authorized"
    assert {slot.participant_ref for slot in accepted.session.slot_assignments} == {
        "character:siming",
        "character:maya",
    }
    assert realizing.session is not None
    assert realizing.session.state == "realizing"
    assert first_observation.session is not None
    assert first_observation.session.state == "realizing"
    assert committed.session is not None
    assert committed.session.state == "committed"
    assert committed.session.settlement_ref == "settlement:session:handshake:1"
    assert [event.event_type for event in store.read_stream("session:session:handshake:1")] == [
        "embodied.interaction_session.proposed",
        "embodied.interaction_session.accepted",
        "embodied.interaction_session.authorized",
        "embodied.interaction_session.realizing",
        "embodied.interaction_session.participant_observed",
        "embodied.interaction_session.participant_observed",
        "embodied.interaction_session.committed",
    ]
    assert [event.payload["global_sequence"] for event in bus.list_events(event_type="embodied.interaction_session.committed")] == [7]
    assert [event.event_kind for event in ledger.events_for_attempt("session:handshake:1")] == [
        "session_lifecycle",
        "session_lifecycle",
        "session_lifecycle",
        "session_lifecycle",
        "participant_terminal_observation",
        "participant_terminal_observation",
        "settlement",
    ]


def test_handshake_refusal_rejects_session_and_never_authorizes_local_realization() -> None:
    service, store, bus, _ledger = _service()
    _propose(service)

    rejected = service.reject(
        session_id="session:handshake:1",
        participant_ref="character:maya",
        reason_code="participant_refused",
        causation_id="cmd:session:handshake:1:reject",
        payload_digest="digest:reject:maya",
    )
    realizing = service.start_realizing(
        session_id="session:handshake:1",
        causation_id="cmd:session:handshake:1:realize-after-reject",
    )

    assert rejected.session is not None
    assert rejected.session.state == "rejected"
    assert realizing.accepted is False
    assert realizing.error_code == "session_not_authorized"
    assert "embodied.interaction_session.authorized" not in [
        event.event_type for event in store.read_stream("session:session:handshake:1")
    ]
    assert bus.list_events(event_type="embodied.interaction_session.authorized") == []


def test_target_departure_interrupts_realizing_session_and_releases_reservations() -> None:
    service, store, _bus, _ledger = _service()
    _propose(service)
    service.accept(
        session_id="session:handshake:1",
        participant_ref="character:maya",
        causation_id="cmd:session:handshake:1:accept",
        payload_digest="digest:accept:maya",
    )
    service.start_realizing(
        session_id="session:handshake:1",
        causation_id="cmd:session:handshake:1:realize",
    )

    interrupted = service.report_target_departure(
        session_id="session:handshake:1",
        target_ref="character:maya",
        causation_id="cmd:session:handshake:1:target-departed",
    )
    late_observation = service.record_terminal_observation(
        session_id="session:handshake:1",
        participant_ref="character:siming",
        attempt_ref="attempt:handshake:siming",
        terminal_status="completed",
        payload_digest="digest:terminal:late",
    )

    assert interrupted.session is not None
    assert interrupted.session.state == "interrupted"
    assert interrupted.session.reservation_refs == []
    assert late_observation.accepted is False
    assert late_observation.error_code == "session_not_realizing"
    assert store.read_stream("session:session:handshake:1")[-1].payload["reason_code"] == "target_departed"


def test_third_party_interruption_interrupts_realizing_session_without_committing_shared_action() -> None:
    service, store, _bus, _ledger = _service()
    _propose(service)
    service.accept(
        session_id="session:handshake:1",
        participant_ref="character:maya",
        causation_id="cmd:session:handshake:1:accept",
        payload_digest="digest:accept:maya",
    )
    service.start_realizing(
        session_id="session:handshake:1",
        causation_id="cmd:session:handshake:1:realize",
    )

    interrupted = service.interrupt(
        session_id="session:handshake:1",
        actor_ref="character:third-party",
        reason_code="third_party_interruption",
        causation_id="cmd:session:handshake:1:third-party-interrupt",
    )

    assert interrupted.session is not None
    assert interrupted.session.state == "interrupted"
    assert interrupted.session.settlement_ref is None
    assert store.read_stream("session:session:handshake:1")[-1].event_type == "embodied.interaction_session.interrupted"
    assert store.read_stream("session:session:handshake:1")[-1].payload["actor_ref"] == "character:third-party"


def test_session_projection_and_bus_delivery_filter_private_participant_terms() -> None:
    service, store, bus, _ledger = _service()

    _propose(service)
    service.accept(
        session_id="session:handshake:1",
        participant_ref="character:maya",
        causation_id="cmd:session:handshake:1:accept",
        payload_digest="digest:accept:maya",
    )

    public_projection = service.public_projection("session:handshake:1")
    store_payloads = [event.payload for event in store.read_events()]
    bus_payloads = [event.payload for event in bus.list_events()]

    assert public_projection == {
        "session_id": "session:handshake:1",
        "semantic_action": "handshake",
        "state": "authorized",
        "participant_refs": ["character:siming", "character:maya"],
        "target_refs": ["character:maya"],
        "safe_phase": "authorized",
        "sync_status": "authorized",
    }
    assert "participant_private_terms" not in str(public_projection)
    assert "private initiator memory" not in str(store_payloads)
    assert "private target context" not in str(store_payloads)
    assert "private initiator memory" not in str(bus_payloads)
    assert "private target context" not in str(bus_payloads)


def test_websocket_session_probe_delivers_committed_session_events_from_gameplay_outbox_to_godot_envelope() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "embodied_interaction_session_probe",
                "payload": {
                    "session_id": "session:handshake:websocket",
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

        received = [websocket.receive_json() for _ in range(5)]

    ack = received[0]
    session_events = [message for message in received if message["message_type"] == "embodied_interaction_session_event"]
    session_payloads = [message["payload"] for message in session_events]
    bus_events = main.authority_event_bus.list_events()
    store_events = main.gameplay_event_store.read_stream("session:session:handshake:websocket")

    assert ack == {
        "message_type": "ack",
        "payload": {
            "accepted": True,
            "source_type": "embodied_interaction_session_probe",
            "route": "embodied_interaction_session",
        },
    }
    assert [event.event_type for event in store_events] == [
        "embodied.interaction_session.proposed",
        "embodied.interaction_session.accepted",
        "embodied.interaction_session.authorized",
        "embodied.interaction_session.realizing",
    ]
    assert [event.event_type for event in bus_events] == [event.event_type for event in store_events]
    assert [payload["event_type"] for payload in session_payloads] == [event.event_type for event in store_events]
    assert [payload["global_sequence"] for payload in session_payloads] == [
        event.global_sequence for event in store_events
    ]
    assert [payload["stream_revision"] for payload in session_payloads] == [1, 2, 3, 4]
    assert all(payload["session_id"] == "session:handshake:websocket" for payload in session_payloads)
    assert all(payload["semantic_action"] == "handshake" for payload in session_payloads)
    assert session_payloads[-1]["state"] == "realizing"
    assert session_payloads[-1]["safe_phase"] == "realizing"
    assert session_payloads[-1]["sync_status"] == "realizing"
    assert session_payloads[-1]["slot_assignments"][1]["participant_ref"] == "character:maya"
    assert all(payload["transaction_id"].startswith("tx:session:handshake:websocket:") for payload in session_payloads)
    assert all(payload["event_id"].startswith("evt:session:handshake:websocket:") for payload in session_payloads)
    assert "participant_private_terms" not in str(session_payloads)
    assert "private initiator memory" not in str(session_payloads)
    assert "private target context" not in str(session_payloads)
    assert "character_actor_status" not in str(session_payloads)
    assert "bone_transforms" not in str(session_payloads)
    assert "rigid_body_velocity" not in str(session_payloads)
