from __future__ import annotations

import os
import hashlib
import hmac
import json
import pytest
from time import time

os.environ["PARALLS_HEAVENLY_GRAPH_PATH"] = ":memory:"

from app import config
config.settings.heavenly_graph_path = ":memory:"

from app.ws_protocol import Envelope
import app.main as main
from app import config
from app.gameplay.physics_contact_receipt import PhysicsContactReceipt
from app.services.websocket_session_auth_service import WebSocketSessionEnrollment

from test_street_combat_authority import attempt
from test_combat_settlement_threat_consumer import _attempt as _canonical_combat_attempt, _sources
from app.services.websocket_session_auth_service import WebSocketConnectionContext


def _context(actor="street_bandage"):
    return WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=int(time()),
                                      connection_ref=f"connection:street:{actor}")


def _enroll(actor="street_bandage"):
    context = _context(actor)
    now = int(time())
    credential = main.embodied_controller_auth_service.create_trusted_local_launch_credential(
        actor_id=actor, controller_instance_id=f"controller:{actor}", issued_at=now, expires_at=now + 100)
    messages = main._handle_envelope(Envelope(message_type="embodied_controller_bind", payload={
        "credential_kind": "trusted_local_launch", "credential": credential, "actor_id": actor,
        "controller_instance_id": f"controller:{actor}", "protocol_version": 1,
    }), connection_context=context)
    assert messages[-1]["message_type"] == "embodied_controller_bound"
    return messages[-1]["payload"]


def _prepare_bound_actors():
    _enroll()
    _enroll("char_a")


def _dispatch(message_type: str, payload: dict[str, object], *, actor="street_bandage") -> dict[str, object]:
    messages = _dispatch_many(message_type, payload, actor=actor)
    assert len(messages) == 1
    return messages[0]


def _dispatch_many(message_type: str, payload: dict[str, object], *, actor="street_bandage") -> list[dict[str, object]]:
    return main._handle_envelope(Envelope(message_type=message_type, payload=payload), connection_context=_context(actor))


def test_websocket_street_combat_client_attempt_fails_closed_without_contact_receipt() -> None:
    main.reset_runtime_state()
    _prepare_bound_actors()
    pose = _dispatch("street_combat_pose", {"actor_id": "street_bandage", "connection_epoch": 1, "position": [0.0, 0.2, -9.8], "physics_tick": 100})
    assert pose["message_type"] == "street_combat_pose_result"
    assert pose["payload"]["accepted"] is True
    assert pose["payload"]["actor_state"]["hp"] == 100
    assert pose["payload"]["actor_state"]["stamina"] == 100
    _dispatch("street_combat_pose", {"actor_id": "char_a", "connection_epoch": 1, "position": [-2.0, 0.2, -9.8], "physics_tick": 100}, actor="char_a")
    before_events = len(main.gameplay_event_store.read_events())
    messages = _dispatch_many("street_combat_attempt", {"attempt": attempt("transport").model_dump(mode="json")})
    assert messages[0]["message_type"] == "street_combat_result"
    assert messages[0]["payload"] == {"accepted": False, "error_code": "websocket_session_required"}
    assert len(messages) == 1
    assert len(main.gameplay_event_store.read_events()) == before_events
    assert main.unified_character_action_settlement_service.mutation_count == 0
    assert main.unified_character_action_settlement_service.street_actor_state("char_a")["hp"] == 100


def test_websocket_street_combat_rejects_client_truth() -> None:
    main.reset_runtime_state()
    payload = attempt("bad").model_dump(mode="json")
    payload["damage"] = 999
    response = _dispatch("street_combat_attempt", {"attempt": payload})
    assert response["message_type"] == "street_combat_result"
    assert response["payload"]["accepted"] is False
    assert main.unified_character_action_settlement_service.mutation_count == 0


def test_client_street_attempt_does_not_trigger_character_agent_execution() -> None:
    main.reset_runtime_state()
    _prepare_bound_actors()
    _dispatch("street_combat_pose", {"actor_id": "street_bandage", "connection_epoch": 1, "position": [0.0, 0.2, -9.8], "physics_tick": 100})
    _dispatch("street_combat_pose", {"actor_id": "char_a", "connection_epoch": 1, "position": [-2.0, 0.2, -9.8], "physics_tick": 100}, actor="char_a")
    before_events = len(main.gameplay_event_store.read_events())
    messages = _dispatch_many("street_combat_attempt", {"attempt": attempt("agent-reaction").model_dump(mode="json")})
    assert messages[0]["payload"] == {"accepted": False, "error_code": "websocket_session_required"}
    executions = [message["payload"] for message in messages if message["message_type"] == "character_agent_execution"]
    assert executions == []
    assert len(main.gameplay_event_store.read_events()) == before_events
    assert main.unified_character_action_settlement_service.mutation_count == 0


@pytest.mark.parametrize("message_type", ["street_combat_pose", "street_combat_attempt"])
@pytest.mark.parametrize("case,code", [
    ("unbound", "controller_binding_required"),
    ("wrong_actor", "controller_binding_subject_mismatch"),
    ("other_connection", "controller_binding_required"),
    ("revoked", "controller_binding_required"),
    ("wrong_epoch", "stale_connection_epoch"),
    ("missing_epoch", "stale_connection_epoch"),
])
def test_street_transport_requires_current_own_actor_binding(message_type, case, code):
    main.reset_runtime_state()
    actor = "street_bandage"
    context = _context()
    if case != "unbound":
        binding = _enroll()
        if case == "revoked":
            main.embodied_controller_auth_service.revoke_controller_epoch(
                controller_instance_id=binding["controller_instance_id"], connection_epoch=binding["connection_epoch"])
    if case == "wrong_actor": actor = "char_a"
    if case == "other_connection": context.connection_ref = "connection:other"
    if message_type == "street_combat_pose":
        payload = {"actor_id": actor, "connection_epoch": 2 if case == "wrong_epoch" else 1,
                   "position": [0.0, 0.2, -9.8], "physics_tick": 100}
        if case == "missing_epoch": payload.pop("connection_epoch")
    else:
        payload = {"attempt": attempt("unauthorized", actor=actor,
                                       connection_epoch=2 if case == "wrong_epoch" else 1).model_dump(mode="json")}
        if case == "missing_epoch":
            # ActionAttempt rejects a missing required epoch before authorization.
            payload["attempt"].pop("connection_epoch")
    before = main.unified_character_action_settlement_service.street_actor_state("char_a")
    messages = main._handle_envelope(Envelope(message_type=message_type, payload=payload), connection_context=context)
    result = messages[0]["payload"]
    assert result["accepted"] is False
    if not (case == "missing_epoch" and message_type == "street_combat_attempt"):
        assert result["error_code"] == code
    assert main.unified_character_action_settlement_service.street_actor_state("char_a") == before
    assert main.unified_character_action_settlement_service.mutation_count == 0


def test_encounter_admission_requires_authenticated_websocket_session() -> None:
    main.reset_runtime_state()
    context = _context("char_a")
    before = len(main.gameplay_event_store.read_events())
    messages = main._handle_envelope(
        Envelope(message_type="street_combat_encounter_admit", payload={
            "world_ref": "world:demo", "timeline_ref": "timeline:main",
            "actor_ref": "character:char_a", "target_ref": "character:char_b",
            "actor_incarnation_ref": "character:char_a@1",
            "target_incarnation_ref": "character:char_b@1",
            "presence_event_ids": ["missing:a", "missing:b"],
            "life_event_ids": ["missing:a", "missing:b"],
            "faction_event_id": "missing:faction",
            "command_id": "admit:transport", "idempotency_key": "admit:transport",
            "causation_id": "cause:transport", "correlation_id": "corr:transport",
        }), connection_context=context)
    assert messages[0]["message_type"] == "street_combat_encounter_result"
    assert messages[0]["payload"] == {"accepted": False, "error_code": "websocket_session_required"}
    assert len(main.gameplay_event_store.read_events()) == before


def test_street_combat_recovery_requires_authenticated_session() -> None:
    main.reset_runtime_state()
    messages = _dispatch_many("street_combat_recovery_snapshot_request", {"connection_epoch": 1})
    assert messages[0]["message_type"] == "street_combat_recovery_snapshot"
    assert messages[0]["payload"] == {"accepted": False, "error_code": "websocket_session_required"}


def test_authenticated_contact_receipt_flows_through_embodied_and_threat_owners(monkeypatch):
    authority_ref = "authority:test:physics"
    secret = "test-physics-contact-secret-material-32-bytes"
    monkeypatch.setattr(config.settings, "physics_contact_authority_secrets", {authority_ref: secret}, raising=False)
    main.reset_runtime_state()
    _enroll("char_a")
    _enroll("char_b")
    source = _sources(main.gameplay_event_store)

    context = _context("char_a")
    now = context.observed_at
    enrollment = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="player:combat-test", allowed_actor_refs=("character:char_a",),
        issued_at=now, expires_at=now + 100,
    )
    session = main.websocket_session_auth_service.bind_session(
        WebSocketSessionEnrollment(credential_kind="trusted_local_launch", credential=enrollment,
                                   protocol_version=1),
        remote_host="127.0.0.1", now=now,
    )
    assert session.accepted and session.binding is not None
    context.binding = session.binding

    admitted = main._handle_envelope(Envelope(message_type="street_combat_encounter_admit", payload={
        "world_ref": source.world_ref, "timeline_ref": source.timeline_ref,
        "actor_ref": "character:char_a", "target_ref": "character:char_b",
        "command_id": "admit:live-contact", "idempotency_key": "admit:live-contact",
        "causation_id": "cause:admit:live-contact", "correlation_id": "corr:live-contact",
    }), connection_context=context)
    assert admitted[0]["payload"]["accepted"] is True

    for actor_id, position in (("char_a", [0.0, 0.2, -9.8]), ("char_b", [1.0, 0.2, -9.8])):
        _dispatch("street_combat_pose", {"actor_id": actor_id, "connection_epoch": 1,
                                           "position": position, "physics_tick": 100}, actor=actor_id)

    action_attempt = _canonical_combat_attempt("live-contact")
    active = main.combat_threat_authority.resolve_active_admitted_encounter(
        session_ref=session.binding.session_ref, principal_ref=session.binding.principal_ref,
        connection_epoch=session.binding.connection_epoch, lease_expires_at=session.binding.lease_expires_at,
        now=context.observed_at, actor_ref=action_attempt.actor_ref, target_ref=action_attempt.target_refs[0],
    )
    assert active is not None
    from app.gameplay.combat_durable_adapter import CombatSourceContext
    source_context = CombatSourceContext(
        world_ref=active["world_ref"], timeline_ref=active["timeline_ref"], encounter_ref=active["encounter_ref"],
        actor_incarnation_ref=active["actor_incarnation_ref"], target_incarnation_ref=active["target_incarnation_ref"],
        presence_source_event_ids=tuple(active["source_event_ids"][:2]),
        life_state_source_event_ids=tuple(active["source_event_ids"][2:4]),
        faction_source_event_id=active["source_event_ids"][4],
    )
    threat_eligibility = main.combat_threat_authority.source_eligibility(
        actor_ref=action_attempt.actor_ref, target_ref=action_attempt.target_refs[0],
        presence_event_ids=source_context.presence_source_event_ids,
        life_event_ids=source_context.life_state_source_event_ids,
        faction_event_id=source_context.faction_source_event_id,
        world_ref=source_context.world_ref, timeline_ref=source_context.timeline_ref,
        actor_incarnation_ref=source_context.actor_incarnation_ref,
        target_incarnation_ref=source_context.target_incarnation_ref,
    )
    assert threat_eligibility["eligible"] is True, threat_eligibility
    receipt = PhysicsContactReceipt(
        authority_ref=authority_ref,
        actor_ref=action_attempt.actor_ref,
        target_ref=action_attempt.target_refs[0],
        connection_epoch=action_attempt.connection_epoch,
        attempt_id=action_attempt.attempt_id,
        physics_tick=action_attempt.physics_tick,
        target_incarnation_ref="character:char_b@1",
        action_descriptor_digest=action_attempt.action_descriptor_digest,
        attempt_payload_digest=action_attempt.payload_digest,
        contact_source_digest="sha256:" + hashlib.sha256(b"physics-source:live-contact").hexdigest(),
        signature="0" * 64,
    )
    signature = hmac.new(secret.encode(), receipt.canonical_bytes(), hashlib.sha256).hexdigest()
    receipt = receipt.model_copy(update={"signature": signature})
    result = main._handle_envelope(Envelope(message_type="street_combat_attempt", payload={
        "attempt": action_attempt.model_dump(mode="json"),
        "contact_receipt": receipt.model_dump(mode="json"),
    }), connection_context=context)[0]

    assert result["message_type"] == "street_combat_result"
    assert result["payload"]["accepted"] is True, result["payload"]
    assert result["payload"]["action_receipt"]["outcome"] == "committed"
    assert result["payload"]["settlement_receipt"]["committed"] is True
    assert result["payload"]["threat_receipt"]["committed"] is True
    assert result["payload"]["contact_receipt"]["committed"] is True
    assert main.unified_character_action_settlement_service.street_actor_state("char_b")["hp"] == 80
    recovery = main._handle_envelope(
        Envelope(message_type="street_combat_recovery_snapshot_request",
                 payload={"connection_epoch": session.binding.connection_epoch}),
        connection_context=context,
    )[0]
    assert recovery["payload"]["accepted"] is True
    encounters = recovery["payload"]["snapshot"]["combat_encounters"]
    assert len(encounters) == 1
    assert encounters[0]["settlements"]
    assert encounters[0]["settlements"][0]["source"]["encounter_ref"] == encounters[0]["encounter_ref"]
