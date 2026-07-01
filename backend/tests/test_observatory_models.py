from app.character_agent.models.dynamic_state import CharacterDynamicState
from app.character_agent.models.goal_runtime import CharacterGoalStateRecord
from app.models.observatory import (
    ActorDramaticEvent,
    ActorDramaticState,
    ScriptBeat,
    SimingDramaticEvent,
    SimingDramaticState,
    WorldOutcomeEvent,
)


def test_actor_dramatic_state_carries_stable_observatory_fields() -> None:
    state = ActorDramaticState(
        actor_id="char_a",
        producer_ts=101,
        causation_id="cause-1",
        correlation_id="corr-1",
        participants=["char_a", "char_b"],
        current_intent="approach",
        focus_target="char_b",
        state_label="attentive",
        why_now_summary="char_b just spoke",
        perception_summary="heard char_b speaking",
        memory_summary="recently tracked char_b as guarded",
        interpretation_summary="char_b may know something useful",
        decision_summary="close distance and probe",
        execution_summary="approach with guarded posture",
        latest_outcome_summary="none",
        latest_siming_summary="siming nudged attention toward char_b",
        cadence_summary="perception=200|cognition=500|degraded=False",
        continuity_summary="contact=char_b|interrupted=approach|transition=accepted",
        dynamic_state=CharacterDynamicState(
            actor_id="char_a",
            vigilance_level=0.3,
            distraction_level=0.1,
            stress_load=0.4,
            social_pressure=0.2,
            masking_pressure=0.1,
        ),
        goal_state=CharacterGoalStateRecord(
            actor_id="char_a",
            primary_goal="protect_secret",
            long_term_goal="preserve_order",
            mid_term_strategy="contain_exposure",
            immediate_goal="withhold_until_private",
            supporting_goals=["clarify_intent"],
            blockers=["high_masking_pressure"],
            goal_sources=["dynamic_state"],
            urgency="high",
            transition_kind="repairing",
            transition_reason_tags=["strategy_blocked"],
        ),
    )

    assert state.actor_id == "char_a"
    assert state.producer_ts == 101
    assert state.causation_id == "cause-1"
    assert state.correlation_id == "corr-1"
    assert state.participants == ["char_a", "char_b"]
    assert state.latest_siming_summary == "siming nudged attention toward char_b"
    assert state.cadence_summary == "perception=200|cognition=500|degraded=False"
    assert state.continuity_summary == "contact=char_b|interrupted=approach|transition=accepted"
    assert state.dynamic_state is not None
    assert state.dynamic_state.vigilance_level == 0.3
    assert state.goal_state is not None
    assert state.goal_state.mid_term_strategy == "contain_exposure"


def test_actor_dramatic_event_carries_structured_stage_and_summary() -> None:
    event = ActorDramaticEvent(
        actor_id="char_b",
        producer_ts=102,
        causation_id="cause-2",
        correlation_id="corr-2",
        participants=["char_b", "obj_letter"],
        stage="decision",
        summary="char_b selected inspect_object toward obj_letter",
        focus_target="obj_letter",
        intent_label="inspect_object",
        detail={"source_event_id": "cand-2"},
    )

    assert event.stage == "decision"
    assert event.intent_label == "inspect_object"
    assert event.participants == ["char_b", "obj_letter"]


def test_siming_state_and_event_keep_director_specific_fields() -> None:
    state = SimingDramaticState(
        producer_ts=103,
        causation_id="cause-3",
        correlation_id="corr-3",
        participants=["char_a", "env_lamp"],
        fairness_summary="visibility imbalance detected around env_lamp",
        intervention_candidate="fact_reveal:env_lamp",
        intervention_decision="approved",
        selected_path="visual_fact_path",
        intervention_band="fact_reveal",
        target_ref="env_lamp",
        reason_summary="make the light drop legible to the cast",
        downstream_status="pending_delivery",
        no_action_reason="",
    )
    event = SimingDramaticEvent(
        producer_ts=104,
        causation_id="cause-4",
        correlation_id="corr-4",
        participants=["char_b", "env_lamp"],
        stage="intervention_decision",
        summary="siming approved a visual fact reveal for env_lamp",
        selected_path="visual_fact_path",
        intervention_band="fact_reveal",
        target_ref="env_lamp",
        reason_summary="char_b needs a clearer cue",
        downstream_status="published",
        no_action_reason="",
    )

    assert state.selected_path == "visual_fact_path"
    assert state.downstream_status == "pending_delivery"
    assert event.stage == "intervention_decision"
    assert event.reason_summary == "char_b needs a clearer cue"


def test_world_outcome_and_script_beat_models_link_scene_truth() -> None:
    outcome = WorldOutcomeEvent(
        producer_ts=105,
        causation_id="interact:105",
        correlation_id="scene-beat-1",
        participants=["char_c", "obj_letter"],
        actor_id="char_c",
        target_ref="obj_letter",
        request_type="inspect",
        settlement_status="accepted",
        constraint_summary="",
        world_change_summary="obj_letter changed from hidden to visible",
        dramatic_consequence_summary="the letter becomes readable to the room",
        source_message_type="world_result",
        detail={"result_type": "object_state_result"},
    )
    beat = ScriptBeat(
        beat_id="beat-scene-beat-1-1",
        producer_ts=106,
        causation_id="interact:105",
        correlation_id="scene-beat-1",
        participants=["char_c", "obj_letter", "siming"],
        dramatic_summary="char_c inspects the letter and the world acknowledges the reveal",
        actor_event_refs=["char_c:decision:1"],
        siming_event_refs=["siming:decision:1"],
        world_event_refs=["world:obj_letter:1"],
    )

    assert outcome.settlement_status == "accepted"
    assert outcome.world_change_summary == "obj_letter changed from hidden to visible"
    assert beat.participants == ["char_c", "obj_letter", "siming"]
    assert beat.world_event_refs == ["world:obj_letter:1"]
