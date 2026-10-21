from __future__ import annotations

import os
import pytest

os.environ["PARALLS_HEAVENLY_GRAPH_PATH"] = ":memory:"

from app import config
config.settings.heavenly_graph_path = ":memory:"

from app.ws_protocol import Envelope
import app.main as main

from test_street_combat_authority import attempt
from app.services.websocket_session_auth_service import WebSocketConnectionContext


def _context(actor="street_bandage"):
    return WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=100,
                                      connection_ref=f"connection:street:{actor}")


def _enroll(actor="street_bandage"):
    context = _context(actor)
    credential = main.embodied_controller_auth_service.create_trusted_local_launch_credential(
        actor_id=actor, controller_instance_id=f"controller:{actor}", issued_at=100, expires_at=200)
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


def test_websocket_street_combat_correlates_pose_and_settlement() -> None:
    main.reset_runtime_state()
    _prepare_bound_actors()
    pose = _dispatch("street_combat_pose", {"actor_id": "street_bandage", "connection_epoch": 1, "position": [0.0, 0.2, -9.8], "physics_tick": 100})
    assert pose["message_type"] == "street_combat_pose_result"
    assert pose["payload"]["accepted"] is True
    assert pose["payload"]["actor_state"]["hp"] == 100
    assert pose["payload"]["actor_state"]["stamina"] == 100
    _dispatch("street_combat_pose", {"actor_id": "char_a", "connection_epoch": 1, "position": [-2.0, 0.2, -9.8], "physics_tick": 100}, actor="char_a")
    first = _dispatch_many("street_combat_attempt", {"attempt": attempt("transport").model_dump(mode="json")})[0]
    assert first["message_type"] == "street_combat_result"
    result = first["payload"]["authority_result"]
    assert result["attempt_id"] == "attempt:transport"
    assert result["outcome"] == "committed"
    assert result["committed_projection"]["target_hp"] == 80
    duplicate = _dispatch_many("street_combat_attempt", {"attempt": attempt("transport").model_dump(mode="json")})[0]
    assert duplicate["payload"]["authority_result"]["transaction_id"] == result["transaction_id"]
    assert main.unified_character_action_settlement_service.street_actor_state("char_a")["hp"] == 80


def test_websocket_street_combat_rejects_client_truth() -> None:
    main.reset_runtime_state()
    payload = attempt("bad").model_dump(mode="json")
    payload["damage"] = 999
    response = _dispatch("street_combat_attempt", {"attempt": payload})
    assert response["message_type"] == "street_combat_result"
    assert response["payload"]["accepted"] is False
    assert main.unified_character_action_settlement_service.mutation_count == 0


def test_committed_street_hit_enters_character_agent_protective_execution_contract() -> None:
    main.reset_runtime_state()
    _prepare_bound_actors()
    _dispatch("street_combat_pose", {"actor_id": "street_bandage", "connection_epoch": 1, "position": [0.0, 0.2, -9.8], "physics_tick": 100})
    _dispatch("street_combat_pose", {"actor_id": "char_a", "connection_epoch": 1, "position": [-2.0, 0.2, -9.8], "physics_tick": 100}, actor="char_a")
    messages = _dispatch_many("street_combat_attempt", {"attempt": attempt("agent-reaction").model_dump(mode="json")})
    assert messages[0]["payload"]["authority_result"]["outcome"] == "committed"
    executions = [message["payload"] for message in messages if message["message_type"] == "character_agent_execution"]
    assert any(contract["actor_ref"] == "character:char_a" and contract["semantic_action_id"] == "action:self_protect" for contract in executions), [(contract["semantic_action_id"], contract["semantic_intent_id"], contract["target_refs"]) for contract in executions]
    assert all(contract["semantic_action_id"] != "action:melee.short_punch" for contract in executions)


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
