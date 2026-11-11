from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

import app.main as main
from app.main import component_app as app, reset_runtime_state
from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.models import GameplayOutboxEntry
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.embodied_evidence_ledger import EmbodiedEvidenceLedger
from app.services.embodied_interaction_session_service import EmbodiedInteractionSessionService
from app.services.websocket_session_auth_service import WebSocketConnectionContext, WebSocketSessionEnrollment
from app.ws_protocol import Envelope


def test_websocket_session_probe_denies_without_creating_or_recovering_a_session() -> None:
    reset_runtime_state()
    assert _propose(main.embodied_interaction_session_service, session_id="known-session").accepted
    before_sequence = main.gameplay_event_store.get_last_global_sequence()
    expected = {
        "message_type": "ack",
        "payload": {
            "accepted": False,
            "source_type": "embodied_interaction_session_probe",
            "route": "embodied_interaction_session",
            "error_code": "session_access_unavailable",
        },
    }
    responses = []

    with TestClient(app).websocket_connect("/ws") as websocket:
        for session_id in ("known-session", "unknown-session"):
            websocket.send_json({"message_type": "embodied_interaction_session_probe", "payload": {
                "session_id": session_id,
                "semantic_action": "handshake",
                "initiator_ref": "character:client-forged",
                "participant_refs": ["character:client-forged", "character:other"],
            }})
            responses.append(websocket.receive_json())

    assert responses == [expected, expected]
    assert main.gameplay_event_store.get_last_global_sequence() == before_sequence
    assert main.gameplay_event_store.read_stream("session:unknown-session") == []


def test_websocket_session_projection_denial_does_not_disclose_session_or_cursor(monkeypatch) -> None:
    reset_runtime_state()
    assert _propose(main.embodied_interaction_session_service, session_id="known-session").accepted
    expected = {
        "message_type": "embodied_interaction_session_projection_denied",
        "payload": {"error_code": "session_access_unavailable"},
    }
    responses = []

    def unexpected_read(_stream_id):
        pytest.fail("session stream was read before principal visibility evidence was available")

    monkeypatch.setattr(main.gameplay_event_store, "read_stream", unexpected_read)
    with TestClient(app).websocket_connect("/ws") as websocket:
        for session_id, cursor in (
            ("known-session", 0),
            ("unknown-session", 0),
            ("known-session", 999),
            ("unknown-session", 999),
        ):
            websocket.send_json({"message_type": "embodied_interaction_session_projection_pull", "payload": {
                "session_id": session_id,
                "after_global_sequence": cursor,
            }})
            responses.append(websocket.receive_json())

    assert responses == [expected, expected, expected, expected]
    assert "known-session" not in str(responses)
    assert "unknown-session" not in str(responses)
    assert "after_global_sequence" not in str(responses)
    assert "999" not in str(responses)


def test_authenticated_actor_binding_without_session_disclosure_evidence_is_denied(monkeypatch) -> None:
    reset_runtime_state()
    now = 100
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:player",
        allowed_actor_refs=("character:siming",),
        issued_at=now,
        expires_at=now + 60,
    )
    bound = main.websocket_session_auth_service.bind_session(
        WebSocketSessionEnrollment(
            credential_kind="trusted_local_launch",
            credential=credential,
            protocol_version=1,
        ),
        remote_host="127.0.0.1",
        now=now,
    )
    assert bound.accepted and bound.binding is not None
    context = WebSocketConnectionContext(
        remote_host="127.0.0.1",
        observed_at=now,
        connection_ref="connection:bound-session-reader",
        binding=bound.binding,
    )

    def unexpected_read(_stream_id):
        pytest.fail("session lookup ran before disclosure evidence was available")

    monkeypatch.setattr(main.gameplay_event_store, "read_stream", unexpected_read)
    response = main._handle_envelope(
        Envelope(message_type="embodied_interaction_session_projection_pull", payload={
            "session_id": "client-known-session",
            "after_global_sequence": 4,
        }),
        connection_context=context,
    )

    assert response == [{
        "message_type": "embodied_interaction_session_projection_denied",
        "payload": {"error_code": "session_access_unavailable"},
    }]


@pytest.mark.parametrize("outbox_available", [True, False])
def test_websocket_session_pull_replays_after_durable_reopen_without_bus(tmp_path, monkeypatch, outbox_available):
    reset_runtime_state()
    path = tmp_path / "session.db"
    store = DurableGameplayEventStore(path)
    service = EmbodiedInteractionSessionService(store=store)
    assert _propose(service, session_id="restart-session").accepted
    event = store.read_stream("session:restart-session")[0]
    expected_projection = store.get_outbox(f"outbox:{event.event_id}").payload_projection["payload"]
    monkeypatch.setattr(main, "gameplay_event_store", store)
    before_reopen = main._build_committed_session_event_projection(event.event_id)
    store.close()
    reopened = DurableGameplayEventStore(path)
    try:
        monkeypatch.setattr(main, "gameplay_event_store", reopened)
        monkeypatch.setattr(main, "authority_event_bus", InMemoryAuthorityEventBus())
        monkeypatch.setattr(main, "embodied_interaction_session_service", EmbodiedInteractionSessionService(store=reopened))
        if not outbox_available:
            def missing_outbox(outbox_id):
                raise KeyError(outbox_id)
            monkeypatch.setattr(reopened, "get_outbox", missing_outbox)
        if outbox_available:
            restored_projection = main._build_committed_session_event_projection(event.event_id)
            assert restored_projection == before_reopen
            assert restored_projection["payload"]["event_id"] == event.event_id
            assert restored_projection["payload"]["slot_assignments"] == expected_projection["slot_assignments"]
            assert restored_projection["payload"]["participant_refs"] == expected_projection["participant_refs"]
        else:
            with pytest.raises(ValueError, match="^session_access_unavailable$"):
                main._build_committed_session_event_projection(event.event_id)
        with TestClient(app).websocket_connect("/ws") as websocket:
            websocket.send_json({"message_type": "embodied_interaction_session_projection_pull", "payload": {
                "session_id": "restart-session", "after_global_sequence": 0,
            }})
            response = websocket.receive_json()
        assert response == {
            "message_type": "embodied_interaction_session_projection_denied",
            "payload": {"error_code": "session_access_unavailable"},
        }
        assert "restart-session" not in str(response)
    finally:
        reopened.close()


@pytest.mark.parametrize("outbox_state", ["valid", "missing", "event_id", "transaction_id", "global_sequence", "topic", "audience"])
def test_websocket_session_pull_ignores_forged_bus_projection(monkeypatch, outbox_state):
    reset_runtime_state()
    assert _propose(main.embodied_interaction_session_service, session_id="forged-session").accepted
    event = main.gameplay_event_store.read_stream("session:forged-session")[0]
    legitimate = next(item for item in main.authority_event_bus.list_events() if item.event_id == event.event_id)
    forged = legitimate.model_copy(deep=True)
    forged.payload["reason_code"] = "private-forged-value"
    forged.payload["global_sequence"] = 999999
    bus = InMemoryAuthorityEventBus()
    bus.publish(forged)
    bus.publish(legitimate)
    monkeypatch.setattr(main, "authority_event_bus", bus)
    if outbox_state == "missing":
        def missing_outbox(outbox_id):
            raise KeyError(outbox_id)
        monkeypatch.setattr(main.gameplay_event_store, "get_outbox", missing_outbox)
    elif outbox_state != "valid":
        entry = main.gameplay_event_store.get_outbox(f"outbox:{event.event_id}")
        wrong_value = -1 if outbox_state == "global_sequence" else "other"
        monkeypatch.setattr(main.gameplay_event_store, "get_outbox", lambda _: entry.model_copy(update={outbox_state: wrong_value}))
    if outbox_state == "valid":
        internal_projection = main._build_committed_session_event_projection(event.event_id)
        assert internal_projection["payload"]["global_sequence"] == event.global_sequence
        assert "private-forged-value" not in str(internal_projection)
    else:
        with pytest.raises(ValueError, match="^session_access_unavailable$"):
            main._build_committed_session_event_projection(event.event_id)
    with TestClient(app).websocket_connect("/ws") as websocket:
        websocket.send_json({"message_type": "embodied_interaction_session_projection_pull", "payload": {
            "session_id": "forged-session", "after_global_sequence": 0,
        }})
        response = websocket.receive_json()
    assert response == {
        "message_type": "embodied_interaction_session_projection_denied",
        "payload": {"error_code": "session_access_unavailable"},
    }
    assert "forged-session" not in str(response)
    assert "private-forged-value" not in str(response)


@pytest.mark.parametrize("dispatch", [False, True])
@pytest.mark.parametrize("event_type,policy", [
    ("embodied.interaction_session.private", "authority_only"),
    ("other.private", "session_public_safe"),
])
def test_websocket_session_pull_rejects_authority_only_event(dispatch, event_type, policy):
    reset_runtime_state()
    assert _propose(main.embodied_interaction_session_service, session_id="private-session").accepted
    head = main.gameplay_event_store.get_last_global_sequence()
    batch = build_atomic_event_batch(
        command_id="private:session", principal_ref="authority", stream_id="session:private-session",
        expected_revision=main.gameplay_event_store.get_stream_head("session:private-session"), event_specs=[(event_type, {
            "session_id": "private-session", "reason_code": "secret-value",
        })], idempotency_key="private:session", causation_id="private:session", correlation_id="private:session",
    )
    batch.events[0].visibility_policy = policy
    if dispatch:
        batch.outbox_entries = [GameplayOutboxEntry(
            outbox_id="outbox:private-session", transaction_id=batch.transaction_id,
            event_id=batch.events[0].event_id, global_sequence=0, topic=event_type,
            audience="godot_room", payload_projection={"payload": {"reason_code": "secret-value"}},
        )]
    assert main.gameplay_event_store.append_batch(batch).committed
    with pytest.raises(ValueError, match="^session_access_unavailable$"):
        main._build_committed_session_event_projection(batch.events[0].event_id)
    if dispatch:
        assert GameplayOutboxDispatcher(store=main.gameplay_event_store, bus=main.authority_event_bus).dispatch_pending().failed_count == 0
    with TestClient(app).websocket_connect("/ws") as websocket:
        websocket.send_json({"message_type": "embodied_interaction_session_projection_pull", "payload": {
            "session_id": "private-session", "after_global_sequence": head,
        }})
        response = websocket.receive_json()
    assert response == {
        "message_type": "embodied_interaction_session_projection_denied",
        "payload": {"error_code": "session_access_unavailable"},
    }
    assert "private-session" not in str(response)
    assert "secret-value" not in str(response)


def test_committed_session_projection_rejects_unknown_event():
    reset_runtime_state()
    with pytest.raises(ValueError, match="^session_access_unavailable$"):
        main._build_committed_session_event_projection("unknown-event")


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

        ack = websocket.receive_json()
        store_events = main.gameplay_event_store.read_stream("session:session:handshake:websocket")
        session_messages = []
        for _ in range(4):
            websocket.send_json(
                {
                    "message_type": "embodied_interaction_session_projection_pull",
                    "payload": {
                        "session_id": "session:handshake:websocket",
                        "after_global_sequence": 0,
                    },
                }
            )
            message = websocket.receive_json()
            session_messages.append(message)
    assert ack == {
        "message_type": "ack",
        "payload": {
            "accepted": False,
            "source_type": "embodied_interaction_session_probe",
            "route": "embodied_interaction_session",
            "error_code": "session_access_unavailable",
        },
    }
    assert store_events == []
    assert all(message == {
        "message_type": "embodied_interaction_session_projection_denied",
        "payload": {"error_code": "session_access_unavailable"},
    } for message in session_messages)
    assert main.gameplay_event_store.read_stream("session:session:handshake:websocket") == []
    assert "session:handshake:websocket" not in str([ack, session_messages])

    bus_events = [
        event
        for event in main.authority_event_bus.list_events()
        if event.payload.get("session_id") == "session:handshake:websocket"
    ]

    assert bus_events == []


def test_websocket_session_probe_returns_only_admission_ack_before_projection_pulls() -> None:
    reset_runtime_state()
    messages = main._handle_envelope(
        Envelope(
            message_type="embodied_interaction_session_probe",
            payload={
                "session_id": "session:handshake:projection-pull",
                "semantic_action": "handshake",
                "initiator_ref": "character:siming",
                "participant_refs": ["character:siming", "character:maya"],
                "target_refs": ["character:maya"],
            },
        )
    )

    assert messages == [
        {
            "message_type": "ack",
            "payload": {
                "accepted": False,
                "source_type": "embodied_interaction_session_probe",
                "route": "embodied_interaction_session",
                "error_code": "session_access_unavailable",
            },
        }
    ]
    assert main.gameplay_event_store.read_stream("session:session:handshake:projection-pull") == []
