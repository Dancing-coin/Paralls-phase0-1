"""The authority rechecks live policy even when callers bypass player routing."""

import pytest

from app.models.player_input import InteractIntent
from app.services.esm_service import ESMService


def _event(**updates):
    values = dict(player_id="character_agent", actor_id="char_a", room_id="room_demo",
                  scene_id="scene_demo", zone_id="zone_focus", intent_type="interact_intent",
                  producer_ts=20, target_object_id="obj_letter", interaction_type="inspect",
                  turn_id="turn:inspect", execution_contract_ref="execution:inspect")
    values.update(updates)
    return InteractIntent(**values)


@pytest.mark.parametrize("updates,code", [
    ({"target_object_id": "obj_unknown"}, "unsupported_object"),
    ({"interaction_type": "open"}, "unsupported_interaction"),
    ({"target_object_id": "obj_archive_door", "interaction_type": "close"},
     "invalid_interaction_state"),
])
def test_direct_execution_rechecks_registered_policy_and_current_state(updates, code):
    owner = ESMService()
    event = _event(**updates)
    request = owner.build_action_request(event)
    result = owner.resolve_interaction(event, action_request=request, is_in_range=True)
    assert result.result_type == "constraint_state_result"
    assert result.constraint_code == code
    assert result.settlement_status == "rejected"
    assert result.turn_id == event.turn_id
    assert result.idempotency_key == event.execution_contract_ref
    assert owner.resolve_interaction(event, action_request=request, is_in_range=True) == result


def test_direct_execution_rechecks_occupant_after_candidate_was_prepared():
    owner = ESMService()
    owner.commit_interaction_state(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
                                   target_object_id="obj_observation_bench", current_state="occupied",
                                   actor_id="char_b", interaction_type="sit")
    event = _event(target_object_id="obj_observation_bench", interaction_type="stand")
    result = owner.resolve_interaction(event, is_in_range=True)
    assert result.result_type == "constraint_state_result"
    assert result.constraint_code == "interaction_owner_mismatch"
    assert owner.interaction_owner_for(room_id="room_demo", scene_id="scene_demo",
                                      zone_id="zone_focus", target_object_id=event.target_object_id) == "char_b"


def test_direct_execution_rechecks_state_after_candidate_was_prepared():
    owner = ESMService()
    event = _event()
    request = owner.build_action_request(event)
    owner.commit_interaction_state(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
                                   target_object_id="obj_letter", current_state="removed_from_surface")
    result = owner.resolve_interaction(event, action_request=request, is_in_range=True)
    assert result.result_type == "constraint_state_result"
    assert result.constraint_code == "invalid_interaction_state"


@pytest.mark.parametrize("updates", [
    {"actor_id": "char_b"}, {"room_id": "room_other"},
    {"scene_id": "scene_other"}, {"zone_id": "zone_other"},
    {"target_object_id": "obj_plaque"}, {"interaction_type": "read"},
])
def test_canonical_request_cannot_authorize_a_different_event(updates):
    owner = ESMService()
    event = _event()
    request = owner.build_action_request(event)
    with pytest.raises(ValueError, match="interaction request does not match event"):
        owner.resolve_interaction(event.model_copy(update=updates), action_request=request, is_in_range=True)


def test_canonical_idempotency_cannot_move_to_a_different_scope():
    owner = ESMService()
    event = _event()
    request = owner.build_action_request(event)
    original = owner.resolve_interaction(event, action_request=request, is_in_range=True)
    changed = event.model_copy(update={"scene_id": "scene_other"})
    with pytest.raises(ValueError, match="canonical interaction idempotency conflict"):
        owner.resolve_interaction(changed, action_request=owner.build_action_request(changed), is_in_range=True)
    assert owner.resolve_interaction(event, action_request=request, is_in_range=True) == original
