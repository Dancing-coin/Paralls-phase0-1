"""Inspect keeps its candidate source and scope at the authority boundary."""

import pytest

from app.character_agent.execution.l4_executor import CharacterAgentL4Executor
from app.character_agent.models.turn_context import CharacterTurnContext
from app.models.character_agent_runtime import (
    CharacterIntentDecision, CharacterInterpretation, CharacterPrivateWorldSnapshot,
)


def _contract(attention_target="obj_letter"):
    snapshot = CharacterPrivateWorldSnapshot(
        actor_id="char_a", room_id="room_review", scene_id="scene_archive",
        zone_id="zone_desk", producer_ts=10, updated_at=10,
    )
    interpretation = CharacterInterpretation(
        actor_id="char_a", interpreted_summary="inspect the received letter",
        interpretation_type="state_change", salience_score=.8,
        ambiguity_level="low", risk_level="low", opportunity_level="medium",
        attention_target=attention_target,
    )
    decision = CharacterIntentDecision(
        actor_id="char_a", selected_intent="inspect_object", persona_passed=True,
        logic_passed=True, gain_loss_passed=True, rationale="inspect",
        semantic_action_id="action:inspect", target_refs=["obj_letter"],
        candidate_id="inspect_object:obj_letter", candidate_digest="candidate:1",
        candidate_revision_pins={
            "target_admission_digest": "sha256:owner-state",
            "target_revision_vector": {"obj_letter": 2},
        },
        owner_route="esm.interaction",
    )
    turn = CharacterTurnContext.begin(
        actor_id="char_a", source_event_ref="perceived:letter:1", producer_ts=10,
        input_revision_vector={"session:char_a": 0}, memory_revision_vector={},
        policy_revision="policy:1", snapshot_revision=0,
        causation_id="cause:1", correlation_id="corr:1", branch_id="branch:main",
    )
    return CharacterAgentL4Executor().build_execution_contract(snapshot, interpretation, decision, turn)


def test_execution_contract_retains_owner_digest_and_received_scope():
    contract = _contract()
    assert contract.expected_observation["target_admission_digest"] == "sha256:owner-state"
    assert contract.expected_observation["candidate_id"] == "inspect_object:obj_letter"
    assert contract.expected_observation["candidate_digest"] == "candidate:1"
    assert contract.expected_observation["owner_route"] == "esm.interaction"
    assert dict(contract.expected_target_revision_vector) == {"obj_letter": 2}
    assert dict(contract.expected_observation["execution_scope"]) == {
        "room_id": "room_review", "scene_id": "scene_archive", "zone_id": "zone_desk",
    }


@pytest.mark.parametrize("attention_target", [None, "obj_letter", "obj_plaque"])
def test_inspect_projects_to_registered_esm_verb_in_frozen_scope(attention_target):
    from app import main

    contract = _contract(attention_target)
    assert contract.target_refs == ("obj_letter",)
    action = main._semantic_action_from_execution_contract(contract)
    assert action["request_type"] == "interact"
    assert action["interaction_type"] == "inspect"
    message, = main._as_character_agent_contract_action_request_envelopes(contract, producer_ts=10)
    payload = message["payload"]
    assert (payload["room_id"], payload["scene_id"], payload["zone_id"]) == (
        "room_review", "scene_archive", "zone_desk",
    )
    assert payload["target_object_id"] == "obj_letter"
    assert payload["action_profile"] == "inspect"
    assert payload["idempotency_key"] == contract.idempotency_key
    assert payload["turn_id"] == contract.turn_id
