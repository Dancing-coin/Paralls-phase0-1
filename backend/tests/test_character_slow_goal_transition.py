from copy import deepcopy

import pytest

from app.character_agent.gateway.goal_proposal import GoalProposalContext
from app.character_agent.models.goal_runtime import CharacterActiveGoalFrame
from app.models.character_agent_runtime import CharacterIntentDecision
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.runtime.session_recovery import goal_state_from_event
from test_character_slow_goal_contract import proposal_context


def test_goal_only_plan_matches_original_transition_without_action_or_writes(tmp_path):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    context = GoalProposalContext.model_validate(proposal_context())
    runtime._goal_state_store.write("char_a", {"primary_goal": "open_gate"})
    before = runtime.get_goal_state_history("char_a")
    output = {"active_goal_frame": {"primary_goal": "find_key", "urgency": "high"}, "evidence_refs": ["outcome:1"]}
    event = runtime._plan_goal_proposal_event(context, output)
    decision = CharacterIntentDecision(
        actor_id="char_a", selected_intent="hold_position", persona_passed=True,
        logic_passed=True, gain_loss_passed=True, rationale="transition comparison",
        primary_goal="find_key", active_goal_frame=CharacterActiveGoalFrame.model_validate(output["active_goal_frame"]),
    )
    action = runtime._plan_goal_state_event("char_a", decision)
    assert action.pop("selected_intent") == "hold_position"
    assert {key: value for key, value in event.items() if key != "goal_provenance"} == action
    assert event["transition_kind"] == "shifted"
    assert "primary_goal_changed" in event["transition_reason_tags"]
    assert "primary_goal" in event["changed_fields"]
    assert "selected_intent" not in event
    assert set(event["goal_provenance"]) == {"contract", "request_id", "turn_id", "source_ref", "goal_revision", "frame_digest", "evidence_refs"}
    assert runtime.get_goal_state_history("char_a") == before
    assert runtime.get_session_timeline("char_a") == []
    stored = runtime._session_store.append_event("char_a", "goal_state_event", 20, event)
    assert stored["payload"]["goal_provenance"]["request_id"] == "proposal:1"
    runtime.close()
    restored = CharacterAgentRuntime(storage_root=tmp_path)
    assert restored.get_goal_state("char_a")["primary_goal"] == "find_key"
    assert len(restored.get_session_timeline("char_a")) == 1
    assert restored.get_session_timeline("char_a")[0]["payload"] == event
    restored.close()


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(contract="goal_proposal:v2"),
    lambda p: p.update(request_id=""),
    lambda p: p.update(goal_revision=True),
    lambda p: p.update(evidence_refs=["outcome:1", "outcome:1"]),
    lambda p: p.update(source_ref="missing"),
    lambda p: p.update(extra="untrusted"),
])
def test_goal_recovery_rejects_malformed_proposal_provenance(mutation):
    payload = {"primary_goal": "search", "goal_provenance": {
        "contract": "goal_proposal:v1", "request_id": "proposal:1", "turn_id": "turn:1",
        "source_ref": "outcome:1", "goal_revision": 2, "frame_digest": "digest",
        "evidence_refs": ["outcome:1"],
    }}
    mutation(payload["goal_provenance"])
    before = deepcopy(payload)
    with pytest.raises(ValueError):
        goal_state_from_event("char_a", payload)
    assert payload == before


def test_goal_recovery_rejects_action_disguised_as_proposal():
    payload = {"primary_goal": "search", "selected_intent": "attack", "goal_provenance": {
        "contract": "goal_proposal:v1", "request_id": "proposal:1", "turn_id": "turn:1",
        "source_ref": "outcome:1", "goal_revision": 2, "frame_digest": "digest",
        "evidence_refs": ["outcome:1"],
    }}
    with pytest.raises(ValueError):
        goal_state_from_event("char_a", payload)
