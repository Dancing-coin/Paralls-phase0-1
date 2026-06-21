from app.character_agent.execution.l4_executor import CharacterAgentL4Executor
from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
from app.models.character_perceived import CharacterPerceivedEvent
from app.services.character_agent_debug_projection import CharacterAgentDebugProjection


def test_character_agent_debug_projection_builds_snapshot_with_runtime_summaries() -> None:
    projection = CharacterAgentDebugProjection()
    snapshot = CharacterPrivateWorldSnapshot(
        actor_id="char_a",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=200,
        visible_entities=["visual_fact/fixed_gaze_on_target"],
        audible_entities=["auditory_fact/speaker_active"],
        attention_targets=["char_b"],
        current_attention_targets=["char_b"],
        recent_world_changes=["env_lamp changed from stable to alerted"],
        recent_constraint_results=["distance_constraint:obj_letter"],
        body_state_hints=["interaction_strain=engaged"],
        last_siming_catalyst="notice char_b",
        vigilance_level="elevated",
        distraction_level="low",
        clarity_score=0.92,
        certainty_score=0.88,
        updated_at=201,
    )
    state = projection.project_snapshot(
        actor_id="char_a",
        producer_ts=201,
        snapshot=snapshot,
        memory_bundle={
            "working_memory": [{"summary": "char_b just spoke"}],
            "episodic_memories": [{"summary": "char_b guarded around the letter"}],
            "relational_memories": [{"entity_id": "char_b", "value": "guarded"}],
        },
        interpretation_summary="char_b may know something useful",
        decision_summary="approach and probe",
        execution_summary="approach with guarded posture",
        latest_outcome_summary="distance constraint hit near obj_letter",
        latest_siming_summary="siming highlighted char_b",
    )

    assert state.focus_target == "char_b"
    assert state.perception_summary == "visual_fact/fixed_gaze_on_target | auditory_fact/speaker_active"
    assert state.memory_summary == "char_b just spoke | char_b guarded around the letter"
    assert state.latest_outcome_summary == "distance constraint hit near obj_letter"
    assert state.latest_siming_summary == "siming highlighted char_b"


def test_character_agent_debug_projection_builds_stage_events_from_runtime_truth() -> None:
    event = CharacterPerceivedEvent(
        actor_id="char_b",
        percept_channel="visual",
        producer_ts=202,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/object_state_changed",
        source_candidate_event_id="cand-202",
        target_object_id="obj_letter",
        clarity_score=1.0,
        certainty_score=1.0,
    )
    l2 = CharacterAgentL2Service()
    l3 = CharacterAgentL3Service()
    executor = CharacterAgentL4Executor()
    snapshot = CharacterPrivateWorldSnapshot(
        actor_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=202,
        visible_entities=["visual_fact/object_state_changed"],
        attention_targets=["obj_letter"],
        current_attention_targets=["obj_letter"],
        clarity_score=1.0,
        certainty_score=1.0,
        updated_at=202,
    )
    interpretation = l2.interpret_perceived_event(
        snapshot,
        event,
        memory_bundle={"working_memory": [], "episodic_memories": [], "relational_memories": []},
        control_mode="agent_full_auto",
        working_memory_state={},
    )
    decision = l3.select_intent(
        interpretation,
        snapshot=snapshot.model_dump(),
        memory_bundle={"working_memory": [], "episodic_memories": [], "relational_memories": []},
        control_mode="agent_full_auto",
        working_memory_state={},
    )
    execution_plan = executor.build_execution_plan(
        snapshot=snapshot,
        interpretation=interpretation,
        decision=decision,
    )

    projection = CharacterAgentDebugProjection()
    perceive_event = projection.project_stage_event(
        actor_id="char_b",
        producer_ts=202,
        stage="character_perceived_event",
        summary=event.perceived_summary,
        focus_target="obj_letter",
        intent_label="",
        participants=["char_b", "obj_letter"],
    )
    decision_event = projection.project_stage_event(
        actor_id="char_b",
        producer_ts=203,
        stage="decision",
        summary=interpretation.interpreted_summary,
        focus_target=interpretation.attention_target or "",
        intent_label=decision.selected_intent,
        participants=["char_b", "obj_letter"],
        detail={"execution_summary": execution_plan["social_spatial_channel"]["spacing_behavior"]},
    )

    assert perceive_event.stage == "character_perceived_event"
    assert perceive_event.focus_target == "obj_letter"
    assert decision_event.stage == "decision"
    assert decision_event.intent_label == decision.selected_intent
    assert decision_event.detail["execution_summary"] == execution_plan["social_spatial_channel"]["spacing_behavior"]
