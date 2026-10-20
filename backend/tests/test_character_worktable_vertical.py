"""Frozen action/target selection through L4 and the durable object owner.

The supplied choice exercises execution, not model quality or Godot playback.
"""
import pytest

from test_character_object_execution import vertical
from app.character_agent.execution.l4_executor import CharacterAgentL4Executor
from app.character_agent.models.turn_context import CharacterTurnContext
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.models.character_agent_runtime import CharacterInterpretation


def selected_contract(runtime, owner, sessions, intent, sequence):
    snapshot = runtime.get_private_snapshot("char_a")
    snapshot.target_catalog = owner.project_character_targets(snapshot)
    interpretation = CharacterInterpretation(actor_id="char_a", interpreted_summary="visible worktable",
        interpretation_type="object", salience_score=0.5, ambiguity_level="low", risk_level="low",
        opportunity_level="medium", attention_target="obj_worktable")
    turn = CharacterTurnContext.begin(actor_id="char_a", source_event_ref=f"percept:{sequence}",
        producer_ts=10 + sequence, causation_id=f"cause:{sequence}", correlation_id=f"corr:{sequence}",
        input_revision_vector={"session:char_a": sequence}, memory_revision_vector={},
        policy_revision="policy:1", snapshot_revision=sequence, branch_id="main")
    planner = CharacterAgentL3Service()
    prepared = planner.prepare_intent_plan(interpretation=interpretation, control_mode="agent_full_auto",
        snapshot=snapshot.model_dump(mode="json"), turn_context=turn)
    label = f"{intent}:obj_worktable"
    assert label in prepared.candidate_mapping
    output = {"candidate_intents": [label], "selected_intent": label,
        "recommended_intents": [label], "candidate_digest": prepared.candidate_digest}
    plan = planner.finish_intent_plan(prepared, output)
    decision = planner.decision_from_plan(plan, interpretation=interpretation)
    executor = CharacterAgentL4Executor()
    contract = executor.build_execution_contract(snapshot, interpretation, decision, turn)
    runtime._append_session_event(actor_id="char_a", event_type="character_agent_execution_request",
        producer_ts=contract.producer_ts, payload=contract.model_dump(mode="json"))
    assert contract.semantic_action_id == {"use_object": "action:use", "finish_use": "action:finish_use"}[intent]
    assert contract.target_refs == ("obj_worktable",)
    assert "interaction_reach" in contract.claims
    shadow = executor.build_execution_plan(snapshot=snapshot, interpretation=interpretation, decision=decision)
    assert shadow["action_request_bundle"]["requested_actions"][0]["interaction_type"] == (
        "use" if intent == "use_object" else "finish_use")
    return contract


def test_frozen_worktable_selection_l4_owner_cycle_and_original_retry(tmp_path):
    with vertical(tmp_path, target="obj_worktable", intent="use_object", action="action:use") as (
        execution, runtime, owner, source, world, sessions, clock, _
    ):
        use = selected_contract(runtime, owner, sessions, "use_object", 1)
        execution.offer(use)
        original = execution.execute(use)
        assert original[2].settlement_status == "committed"
        assert owner.interaction_state_for(room_id="r", scene_id="s", zone_id="z", target_object_id="obj_worktable") == "engaged"
        finish = selected_contract(runtime, owner, sessions, "finish_use", 2)
        assert finish.expected_observation["target_admission_digest"] != use.expected_observation["target_admission_digest"]
        execution.offer(finish)
        assert execution.execute(finish)[3].committed
        assert owner.interaction_state_for(room_id="r", scene_id="s", zone_id="z", target_object_id="obj_worktable") == "ready"
        assert execution.execute(use) == original
        assert world.get_last_global_sequence() == 3


@pytest.mark.parametrize("targets,intent,action", [
    (["obj_worktable", "obj_plaque"], "use_object", "action:use"),
    (["obj_worktable", "char_b"], "use_object", "action:use"),
    (["obj_plaque"], "use_object", "action:use"),
    (["obj_worktable"], "use_object", "action:finish_use"),
])
def test_invalid_worktable_route_has_no_world_or_outcome_write(tmp_path, targets, intent, action):
    with vertical(tmp_path, target="obj_worktable", intent=intent, action=action) as (
        execution, runtime, owner, source, world, sessions, clock, contract
    ):
        invalid = contract.model_copy(update={"target_refs": tuple(targets),
            "target_ref": targets[0] if len(targets) == 1 else None,
            "idempotency_key": "execution:invalid:" + ":".join(targets) + action})
        runtime._append_session_event(actor_id="char_a", event_type="character_agent_execution_request",
            producer_ts=10, payload=invalid.model_dump(mode="json"))
        execution.offer(invalid)
        with pytest.raises(ValueError):
            execution.execute(invalid)
        assert world.get_last_global_sequence() == 1
        assert not any(e["event_type"] == "character_agent_settlement_result"
                       for e in runtime.get_session_timeline("char_a"))
