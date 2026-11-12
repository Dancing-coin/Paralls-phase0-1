from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

import app.main as main
from app.main import component_app as app, reset_runtime_state
from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.models import GameplayOutboxEntry
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.models.authority_event import AuthorityEvent
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.embodied_evidence_ledger import EmbodiedEvidenceLedger
from app.services.embodied_interaction_session_service import EmbodiedInteractionSessionService
from app.services.websocket_session_auth_service import WebSocketConnectionContext, WebSocketSessionEnrollment
from app.ws_protocol import Envelope


def test_websocket_session_probe_denies_without_creating_or_recovering_a_session() -> None:
    reset_runtime_state()
    _set_world_tick(main.embodied_interaction_session_service)
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
    _set_world_tick(main.embodied_interaction_session_service)
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


def test_authenticated_binding_is_checked_before_unknown_session_lookup(monkeypatch) -> None:
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

    reads = []
    monkeypatch.setattr(main, "time", lambda: now)

    def record_read(stream_id, **query):
        reads.append(stream_id)
        return []

    monkeypatch.setattr(main.gameplay_event_store, "read_stream", record_read)
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
    assert reads == ["session:client-known-session"]


def _bound_session_context(actor_refs: tuple[str, ...], *, now: int | None = None) -> WebSocketConnectionContext:
    now = int(main.time()) if now is None else now
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:session-reader",
        allowed_actor_refs=actor_refs,
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
    return WebSocketConnectionContext(
        remote_host="127.0.0.1",
        observed_at=now,
        connection_ref="connection:session-reader",
        binding=bound.binding,
    )


@pytest.mark.parametrize("durable", [False, True], ids=["memory", "durable"])
def test_session_pull_selects_first_proposal_across_stream_histories(tmp_path, monkeypatch, durable):
    reset_runtime_state()
    store = DurableGameplayEventStore(tmp_path / "session.sqlite") if durable else GameplayEventStore()
    monkeypatch.setattr(main, "gameplay_event_store", store)
    context = _bound_session_context(("character:siming",))
    def pull(session_id):
        return main._handle_envelope(Envelope(message_type="embodied_interaction_session_projection_pull", payload={
            "session_id": session_id, "after_global_sequence": 0,
        }), connection_context=context)
    def append_prior(session_id):
        from test_gameplay_event_store_contract import _batch, _event
        stream = f"session:{session_id}"
        tx = f"prior:{session_id}"
        event = _event(f"event:{tx}", stream_id=stream, tx=tx, command_id=tx)
        batch = _batch(tx=tx, command_id=tx, key=tx, events=[event], expected={stream: 0})
        batch["outbox_entries"] = []
        assert store.append_batch(batch).committed
    def propose(session_id, tick=481, causation="first"):
        service = EmbodiedInteractionSessionService(store=store, world_tick_provider=lambda: tick)
        return service.propose(session_id=session_id, semantic_action="handshake",
            initiator_ref="character:siming", participant_refs=["character:siming", "character:maya"],
            target_refs=["character:maya"], authority_preflight_ref="preflight:test", policy_revision=3,
            scene_revision=11, causation_id=causation, correlation_id="corr:test")
    denied = [{"message_type": "embodied_interaction_session_projection_denied",
               "payload": {"error_code": "session_access_unavailable"}}]
    try:
        assert pull("empty") == denied
        append_prior("no-proposal")
        assert pull("no-proposal") == denied
        append_prior("multi")
        assert propose("multi").accepted
        stream = store.read_stream("session:multi")
        first = stream[1]
        assert first.stream_revision == 2
        before = pull("multi")
        assert before == [{"message_type": "embodied_interaction_session_event", "payload": {
            "session_id": "multi", "semantic_action": "handshake", "state": "awaiting_responses",
            "safe_phase": "awaiting_responses", "initiator_ref": "character:siming",
            "participant_refs": ["character:siming", "character:maya"], "known_time": 481,
            "event_id": first.event_id, "global_sequence": first.global_sequence,
            "next_global_sequence": first.global_sequence,
        }}]
        # A new Owner instance loses session state, but the durable idempotency
        # key still protects the proposal already committed to this Store.
        retry = propose("multi", causation="second")
        assert not retry.accepted
        assert retry.error_code == "idempotency_key_reused"
        from test_gameplay_event_store_contract import _batch
        tx = "fixture:second-proposal"
        duplicate = first.model_copy(update={"event_id": tx, "transaction_id": tx,
            "command_id": tx, "stream_revision": 0, "global_sequence": 0,
            "payload": {**first.payload, "known_time": 999}}, deep=True)
        batch = _batch(tx=tx, command_id=tx, key=tx, events=[duplicate.model_dump()],
                       expected={"session:multi": 2})
        batch["outbox_entries"] = []
        assert store.append_batch(batch).committed
        assert pull("multi") == before
        legacy = EmbodiedInteractionSessionService(store=store)
        assert _propose(legacy, session_id="legacy-v1").accepted
        assert pull("legacy-v1") == denied
        legacy_first = store.read_stream("session:legacy-v1")[0]
        tx = "fixture:v2-after-v1"
        after_v1 = legacy_first.model_copy(update={"event_id": tx, "transaction_id": tx,
            "command_id": tx, "schema_version": 2, "stream_revision": 0, "global_sequence": 0,
            "payload": {**legacy_first.payload, "known_time": 481}}, deep=True)
        batch = _batch(tx=tx, command_id=tx, key=tx, events=[after_v1.model_dump()],
                       expected={"session:legacy-v1": 1})
        batch["outbox_entries"] = []
        assert store.append_batch(batch).committed
        assert pull("legacy-v1") == denied
    finally:
        if durable:
            store.close()


def test_bound_initiator_reads_only_proposal_fields_and_committed_world_tick(monkeypatch) -> None:
    reset_runtime_state()
    _set_world_tick(main.embodied_interaction_session_service)
    assert _propose(main.embodied_interaction_session_service, session_id="known-session").accepted
    context = _bound_session_context(("character:siming",))

    response = main._handle_envelope(
        Envelope(message_type="embodied_interaction_session_projection_pull", payload={
            "session_id": "known-session", "after_global_sequence": 0,
        }),
        connection_context=context,
    )

    assert len(response) == 1
    assert response[0]["message_type"] == "embodied_interaction_session_event"
    payload = response[0]["payload"]
    event = main.gameplay_event_store.read_stream("session:known-session")[0]
    assert payload == {
        "session_id": "known-session",
        "semantic_action": "handshake",
        "state": "awaiting_responses",
        "safe_phase": "awaiting_responses",
        "initiator_ref": "character:siming",
        "participant_refs": ["character:siming", "character:maya"],
        "known_time": 481,
        "event_id": event.event_id,
        "global_sequence": event.global_sequence,
        "next_global_sequence": event.global_sequence,
    }
    for forbidden in ("target_refs", "slot_assignments", "reservation_refs", "participant_private_terms"):
        assert forbidden not in str(payload)


def test_unbound_wrong_actor_and_unknown_session_have_identical_denial(monkeypatch) -> None:
    reset_runtime_state()
    _set_world_tick(main.embodied_interaction_session_service)
    assert _propose(main.embodied_interaction_session_service, session_id="known-session").accepted
    expected = [{
        "message_type": "embodied_interaction_session_projection_denied",
        "payload": {"error_code": "session_access_unavailable"},
    }]
    unbound = WebSocketConnectionContext(
        remote_host="127.0.0.1", observed_at=100, connection_ref="connection:unbound",
    )
    wrong_actor = _bound_session_context(("character:maya",))

    responses = [
        main._handle_envelope(Envelope(message_type="embodied_interaction_session_projection_pull", payload={
            "session_id": "known-session", "after_global_sequence": 0,
        }), connection_context=unbound),
        main._handle_envelope(Envelope(message_type="embodied_interaction_session_projection_pull", payload={
            "session_id": "known-session", "after_global_sequence": 0,
        }), connection_context=wrong_actor),
        main._handle_envelope(Envelope(message_type="embodied_interaction_session_projection_pull", payload={
            "session_id": "unknown-session", "after_global_sequence": 0,
        }), connection_context=_bound_session_context(("character:siming",))),
    ]

    assert responses == [expected, expected, expected]


def test_legacy_proposal_is_replayable_but_not_projected(monkeypatch) -> None:
    reset_runtime_state()
    _set_world_tick(main.embodied_interaction_session_service)
    assert _propose(main.embodied_interaction_session_service, session_id="legacy-session").accepted
    stream_id = "session:legacy-session"
    legacy = main.gameplay_event_store.read_stream(stream_id)[0]
    legacy.event_type = "embodied.interaction_session.proposed"
    legacy.schema_version = 1
    legacy.payload.pop("known_time", None)
    legacy.payload.pop("participant_private_terms", None)
    main.gameplay_event_store._events_by_id[legacy.event_id] = legacy
    main.gameplay_event_store._events_by_stream[stream_id][0] = legacy
    response = main._handle_envelope(
        Envelope(message_type="embodied_interaction_session_projection_pull", payload={
            "session_id": "legacy-session", "after_global_sequence": 0,
        }),
        connection_context=_bound_session_context(("character:siming",)),
    )
    assert response == [{
        "message_type": "embodied_interaction_session_projection_denied",
        "payload": {"error_code": "session_access_unavailable"},
    }]


def test_proposal_without_world_clock_keeps_legacy_write_and_is_not_projected() -> None:
    reset_runtime_state()
    store = GameplayEventStore()
    service = EmbodiedInteractionSessionService(store=store)

    result = _propose(service, session_id="legacy-write-session")

    assert result.accepted is True
    assert result.projection_status == "currently_unprojectable"
    event = store.read_stream("session:legacy-write-session")[0]
    assert event.event_type == "embodied.interaction_session.proposed"
    assert event.schema_version == 1
    assert event.payload["target_refs"] == ["character:maya"]
    assert "known_time" not in event.payload
    assert "participant_private_terms" not in event.payload
    import app.main as runtime_main
    previous_store = runtime_main.gameplay_event_store
    runtime_main.gameplay_event_store = store
    try:
        with pytest.raises(ValueError, match="^session_access_unavailable$"):
            runtime_main._build_committed_session_event_projection(event.event_id)
    finally:
        runtime_main.gameplay_event_store = previous_store


def test_proposal_with_invalid_world_tick_is_rejected_without_legacy_fallback() -> None:
    store = GameplayEventStore()
    service = EmbodiedInteractionSessionService(store=store, world_tick_provider=lambda: -1)

    result = _propose(service, session_id="invalid-clock-session")

    assert result.accepted is False
    assert result.error_code == "session_world_time_unavailable"
    assert store.read_stream("session:invalid-clock-session") == []


def test_revocation_after_pull_prevents_session_projection_send(monkeypatch) -> None:
    reset_runtime_state()
    _set_world_tick(main.embodied_interaction_session_service)
    assert _propose(main.embodied_interaction_session_service, session_id="revoked-session").accepted
    original_resolve = main.websocket_session_auth_service.resolve_binding
    armed = False
    resolutions = 0

    def revoke_after_pull(session_ref):
        nonlocal resolutions
        if armed:
            resolutions += 1
        if armed and resolutions == 2:
            main.websocket_session_auth_service.revoke_session(
                session_ref, reason_code="test_revocation", now=101,
            )
        return original_resolve(session_ref)

    monkeypatch.setattr(main.websocket_session_auth_service, "resolve_binding", revoke_after_pull)
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:session-reader",
        allowed_actor_refs=("character:siming",),
        issued_at=0,
        expires_at=int(main.time()) + 60,
    )
    with TestClient(app, client=("127.0.0.1", 47114)).websocket_connect("/ws") as websocket:
        websocket.send_json({"message_type": "websocket_session_bind", "payload": {
            "credential_kind": "trusted_local_launch", "credential": credential,
            "protocol_version": 2,
            "capability_offer": main.GameplayMirrorCapabilityOffer(
                protocol_version=2, supports_snapshot=True, supports_receipt=True,
                projection_schemas=("gameplay_runtime_state.godot.v1",),
            ).model_dump(),
        }})
        bind_ack = websocket.receive_json()
        assert bind_ack["payload"]["accepted"] is True, bind_ack
        assert websocket.receive_json()["message_type"] == "websocket_session_bound"
        armed = True
        websocket.send_json({"message_type": "embodied_interaction_session_projection_pull", "payload": {
            "session_id": "revoked-session", "after_global_sequence": 0,
        }})
        response = websocket.receive_json()
    assert response == {
        "message_type": "embodied_interaction_session_projection_denied",
        "payload": {"error_code": "session_access_unavailable"},
    }
    assert "revoked-session" not in str(response)


def test_websocket_session_pull_replays_after_durable_reopen_without_bus(tmp_path, monkeypatch):
    reset_runtime_state()
    path = tmp_path / "session.db"
    store = DurableGameplayEventStore(path)
    service = EmbodiedInteractionSessionService(store=store, world_tick_provider=lambda: 481)
    assert _propose(service, session_id="restart-session").accepted
    event = store.read_stream("session:restart-session")[0]
    monkeypatch.setattr(main, "gameplay_event_store", store)
    before_reopen = main._build_committed_session_event_projection(event.event_id)
    store.close()
    reopened = DurableGameplayEventStore(path)
    try:
        monkeypatch.setattr(main, "gameplay_event_store", reopened)
        monkeypatch.setattr(main, "authority_event_bus", InMemoryAuthorityEventBus())
        monkeypatch.setattr(main, "embodied_interaction_session_service", EmbodiedInteractionSessionService(
            store=reopened, world_tick_provider=lambda: 481,
        ))
        def unexpected_outbox_read(_outbox_id):
            pytest.fail("session projection must be reconstructed from the committed event")
        monkeypatch.setattr(reopened, "get_outbox", unexpected_outbox_read)
        restored_projection = main._build_committed_session_event_projection(event.event_id)
        assert restored_projection == before_reopen
        assert restored_projection["payload"]["event_id"] == event.event_id
        assert restored_projection["payload"]["known_time"] == 481
        assert restored_projection["payload"]["participant_refs"] == ["character:siming", "character:maya"]
        with TestClient(app, client=("127.0.0.1", 47113)).websocket_connect("/ws") as websocket:
            now = int(main.time())
            credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
                principal_ref="principal:session-reader",
                allowed_actor_refs=("character:siming",),
                issued_at=0,
                expires_at=now + 60,
            )
            websocket.send_json({"message_type": "websocket_session_bind", "payload": {
                "credential_kind": "trusted_local_launch", "credential": credential,
                "protocol_version": 2,
                "capability_offer": main.GameplayMirrorCapabilityOffer(
                    protocol_version=2, supports_snapshot=True, supports_receipt=True,
                    projection_schemas=("gameplay_runtime_state.godot.v1",),
                ).model_dump(),
            }})
            bind_ack = websocket.receive_json()
            assert bind_ack["payload"]["accepted"] is True, bind_ack
            assert websocket.receive_json()["message_type"] == "websocket_session_bound"
            websocket.send_json({"message_type": "embodied_interaction_session_projection_pull", "payload": {
                "session_id": "restart-session", "after_global_sequence": 0,
            }})
            response = websocket.receive_json()
        assert response["message_type"] == "embodied_interaction_session_event"
        assert response["payload"] == restored_projection["payload"]
    finally:
        reopened.close()


def test_websocket_session_pull_excludes_injected_forged_bus_event():
    reset_runtime_state()
    _set_world_tick(main.embodied_interaction_session_service)
    assert _propose(main.embodied_interaction_session_service, session_id="forged-bus-session").accepted
    event = main.gameplay_event_store.read_stream("session:forged-bus-session")[0]
    forged = AuthorityEvent.model_validate({
        "event_id": event.event_id,
        "event_type": "embodied.interaction_session.proposed",
        "producer_ts": event.global_sequence,
        "room_id": "room_demo", "scene_id": "scene_demo", "zone_id": "zone_focus",
        "source": {"layer": "embodied", "system": "interaction_session"},
        "routing": {"audience_mode": "broadcast", "routing_mode": "event_type"},
        "priority": "p1", "durability": "replayable",
        "causation_id": event.causation_id, "correlation_id": event.correlation_id,
        "payload": {"session_id": "forged-bus-session", "event_id": event.event_id,
                    "semantic_action": "forged-action", "known_time": 999999},
    })
    main.authority_event_bus.publish(forged)
    assert any(item.payload == forged.payload for item in main.authority_event_bus.list_events())
    with TestClient(app, client=("127.0.0.1", 47114)).websocket_connect("/ws") as websocket:
        credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
            principal_ref="principal:session-reader", allowed_actor_refs=("character:siming",),
            issued_at=0, expires_at=int(main.time()) + 60,
        )
        websocket.send_json({"message_type": "websocket_session_bind", "payload": {
            "credential_kind": "trusted_local_launch", "credential": credential,
            "protocol_version": 2,
            "capability_offer": main.GameplayMirrorCapabilityOffer(
                protocol_version=2, supports_snapshot=True, supports_receipt=True,
                projection_schemas=("gameplay_runtime_state.godot.v1",),
            ).model_dump(),
        }})
        assert websocket.receive_json()["payload"]["accepted"] is True
        assert websocket.receive_json()["message_type"] == "websocket_session_bound"
        websocket.send_json({"message_type": "embodied_interaction_session_projection_pull", "payload": {
            "session_id": "forged-bus-session", "after_global_sequence": 0,
        }})
        response = websocket.receive_json()
    assert response["message_type"] == "embodied_interaction_session_event"
    assert response["payload"]["event_id"] == event.event_id
    assert response["payload"]["semantic_action"] == "handshake"
    assert response["payload"]["known_time"] == 481
    assert "forged-action" not in str(response)


def test_websocket_session_pull_uses_committed_event_not_bus_or_outbox(monkeypatch):
    reset_runtime_state()
    _set_world_tick(main.embodied_interaction_session_service)
    assert _propose(main.embodied_interaction_session_service, session_id="forged-session").accepted
    event = main.gameplay_event_store.read_stream("session:forged-session")[0]
    def unexpected_bus_read():
        pytest.fail("session pull must not consume authority bus projections")
    def unexpected_outbox_read(_outbox_id):
        pytest.fail("session pull must not consume outbox projections")
    monkeypatch.setattr(main.authority_event_bus, "list_events", unexpected_bus_read)
    monkeypatch.setattr(main.gameplay_event_store, "get_outbox", unexpected_outbox_read)
    internal_projection = main._build_committed_session_event_projection(event.event_id)
    assert internal_projection["payload"]["global_sequence"] == event.global_sequence
    assert "private-forged-value" not in str(internal_projection)
    with TestClient(app, client=("127.0.0.1", 47114)).websocket_connect("/ws") as websocket:
        now = int(main.time())
        credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
            principal_ref="principal:session-reader",
            allowed_actor_refs=("character:siming",),
            issued_at=0,
            expires_at=now + 60,
        )
        websocket.send_json({"message_type": "websocket_session_bind", "payload": {
            "credential_kind": "trusted_local_launch", "credential": credential,
            "protocol_version": 2,
            "capability_offer": main.GameplayMirrorCapabilityOffer(
                protocol_version=2, supports_snapshot=True, supports_receipt=True,
                projection_schemas=("gameplay_runtime_state.godot.v1",),
            ).model_dump(),
        }})
        bind_ack = websocket.receive_json()
        assert bind_ack["payload"]["accepted"] is True, bind_ack
        assert websocket.receive_json()["message_type"] == "websocket_session_bound"
        websocket.send_json({"message_type": "embodied_interaction_session_projection_pull", "payload": {
            "session_id": "forged-session", "after_global_sequence": 0,
        }})
        response = websocket.receive_json()
    assert response["message_type"] == "embodied_interaction_session_event"
    assert response["payload"] == internal_projection["payload"]
    assert "private-forged-value" not in str(response)


@pytest.mark.parametrize("dispatch", [False, True])
@pytest.mark.parametrize("event_type,policy", [
    ("embodied.interaction_session.private", "authority_only"),
    ("other.private", "session_public_safe"),
])
def test_websocket_session_pull_rejects_authority_only_event(dispatch, event_type, policy):
    reset_runtime_state()
    _set_world_tick(main.embodied_interaction_session_service)
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


def _service(*, with_world_clock: bool = True) -> tuple[EmbodiedInteractionSessionService, GameplayEventStore, InMemoryAuthorityEventBus, EmbodiedEvidenceLedger]:
    store = GameplayEventStore()
    bus = InMemoryAuthorityEventBus()
    ledger = EmbodiedEvidenceLedger()
    service = EmbodiedInteractionSessionService(
        store=store,
        dispatcher=GameplayOutboxDispatcher(store=store, bus=bus),
        evidence_ledger=ledger,
        world_tick_provider=(lambda: 481) if with_world_clock else None,
    )
    return service, store, bus, ledger


def _set_world_tick(service: EmbodiedInteractionSessionService, tick: int = 481) -> None:
    service._world_tick_provider = lambda: tick


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
    proposal = store_payloads[0]
    assert store.read_stream("session:session:handshake:1")[0].event_type == "embodied.interaction_session.proposed"
    assert proposal["target_refs"] == ["character:maya"]
    assert proposal["known_time"] == 481
    assert "participant_private_terms" not in proposal
    assert "private target context" not in str(proposal)
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
