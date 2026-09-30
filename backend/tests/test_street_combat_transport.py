from __future__ import annotations

import os

os.environ["PARALLS_HEAVENLY_GRAPH_PATH"] = ":memory:"

from app import config
config.settings.heavenly_graph_path = ":memory:"

from app.ws_protocol import Envelope
import app.main as main

from test_street_combat_authority import attempt


def _dispatch(message_type: str, payload: dict[str, object]) -> dict[str, object]:
    messages = main._handle_envelope(Envelope(message_type=message_type, payload=payload))
    assert len(messages) == 1
    return messages[0]


def _dispatch_many(message_type: str, payload: dict[str, object]) -> list[dict[str, object]]:
    return main._handle_envelope(Envelope(message_type=message_type, payload=payload))


def test_websocket_street_combat_correlates_pose_and_settlement() -> None:
    main.reset_runtime_state()
    pose = _dispatch("street_combat_pose", {"actor_id": "street_bandage", "position": [0.0, 0.2, -9.8], "physics_tick": 100})
    assert pose["message_type"] == "street_combat_pose_result"
    assert pose["payload"]["accepted"] is True
    assert pose["payload"]["actor_state"]["hp"] == 100
    assert pose["payload"]["actor_state"]["stamina"] == 100
    _dispatch("street_combat_pose", {"actor_id": "char_a", "position": [-2.0, 0.2, -9.8], "physics_tick": 100})
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


def test_committed_street_hit_enters_character_agent_execution_contract() -> None:
    main.reset_runtime_state()
    _dispatch("street_combat_pose", {"actor_id": "street_bandage", "position": [0.0, 0.2, -9.8], "physics_tick": 100})
    _dispatch("street_combat_pose", {"actor_id": "char_a", "position": [-2.0, 0.2, -9.8], "physics_tick": 100})
    messages = main._handle_envelope(Envelope(message_type="street_combat_attempt", payload={"attempt": attempt("agent-reaction").model_dump(mode="json")}))
    assert messages[0]["payload"]["authority_result"]["outcome"] == "committed"
    executions = [message["payload"] for message in messages if message["message_type"] == "character_agent_execution"]
    assert any(contract["actor_ref"] == "character:char_a" and contract["semantic_action_id"] == "action:melee.short_punch" for contract in executions), [(contract["semantic_action_id"], contract["semantic_intent_id"], contract["target_refs"]) for contract in executions]
