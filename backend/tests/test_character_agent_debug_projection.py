from app.character_agent.execution.l4_executor import CharacterAgentL4Executor
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.models.dynamic_state import CharacterDynamicState
from app.character_agent.models.event_memory import CharacterEventMemoryRecord
from app.character_agent.models.higher_order_memory import CharacterHigherOrderMemoryRecord
from app.character_agent.models.goal_runtime import CharacterGoalStateRecord
from app.character_agent.models.knowledge_memory import CharacterKnowledgeMemoryRecord
from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle
from app.character_agent.models.observation_memory import CharacterObservationMemoryRecord
from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.character_agent.models.social_memory import CharacterSocialMemoryRecord
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
from app.models.character_perceived import CharacterPerceivedEvent
from app.services.character_agent_debug_projection import CharacterAgentDebugProjection


class _LocalGateway:
    def __init__(self) -> None:
        self._gateway = CharacterModelGateway()

    def run_task(
        self,
        *,
        task_kind: str,
        context: dict[str, object],
        route_override: str | None = None,
    ) -> dict[str, object]:
        return self._gateway.run_task(
            task_kind=task_kind,
            context=context,
            route_override=route_override or "local_only",
        )


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
        memory_bundle=CharacterMemoryRecordBundle(
            knowledge_memories=[
                CharacterKnowledgeMemoryRecord(
                    memory_id="knowledge:char_a:char_b:1",
                    actor_id="char_a",
                    proposition_key="char_b:is_guarding_letter",
                    proposition="char_b may be protecting the letter",
                    state="suspected",
                    confidence=0.62,
                    source_event_id="evt:1",
                    producer_ts=1,
                )
            ],
            social_memories=[
                CharacterSocialMemoryRecord(
                    memory_id="social:char_a:char_b",
                    actor_id="char_a",
                    entity_id="char_b",
                    trust_baseline=0.25,
                    suspicion_baseline=0.75,
                    intimacy=0.0,
                    dependency=0.0,
                    unresolved_tension=0.5,
                    shared_secret_refs=[],
                    source_event_id="evt:2",
                    producer_ts=2,
                )
            ],
            higher_order_memories=[
                CharacterHigherOrderMemoryRecord(
                    memory_id="higher:char_a:char_b:1",
                    actor_id="char_a",
                    subject_actor_id="char_b",
                    proposition_key="social_probe:knowledge_asymmetry",
                    meta_belief="char_b suspects char_a knows more",
                    confidence=0.72,
                    source_event_id="evt:3",
                    producer_ts=3,
                )
            ],
        ),
        interpretation_summary="char_b may know something useful",
        decision_summary="approach and probe",
        execution_summary="approach with guarded posture",
        latest_outcome_summary="distance constraint hit near obj_letter",
        latest_siming_summary="siming highlighted char_b",
        cadence_summary="perception=200|cognition=500|degraded=False",
        continuity_summary="contact=char_b|interrupted=approach|transition=accepted",
        dynamic_state=CharacterDynamicState(
            actor_id="char_a",
            vigilance_level=0.4,
            distraction_level=0.2,
            stress_load=0.5,
            social_pressure=0.7,
            masking_pressure=0.55,
            motivation_stack=["preserve_order"],
        ),
        goal_state=CharacterGoalStateRecord(
            actor_id="char_a",
            primary_goal="protect_secret",
            long_term_goal="preserve_order",
            mid_term_strategy="contain_exposure",
            immediate_goal="withhold_until_private",
            supporting_goals=["clarify_intent"],
            blockers=["high_masking_pressure"],
            goal_sources=["dynamic_state", "knowledge_state"],
            urgency="high",
            transition_kind="repairing",
            transition_reason_tags=["strategy_blocked"],
        ),
    )

    assert state.focus_target == "char_b"
    assert state.perception_summary == "visual_fact/fixed_gaze_on_target | auditory_fact/speaker_active"
    assert "char_b may be protecting the letter" in state.memory_summary
    assert "char_b" in state.memory_summary
    assert "char_b suspects char_a knows more" in state.memory_summary
    assert "social_pressure=0.7" in state.memory_summary
    assert "masking_pressure=0.55" in state.memory_summary
    assert "vigilance_level=0.4" in state.memory_summary
    assert state.cadence_summary == "perception=200|cognition=500|degraded=False"
    assert state.continuity_summary == "contact=char_b|interrupted=approach|transition=accepted"
    assert state.latest_outcome_summary == "distance constraint hit near obj_letter"
    assert state.latest_siming_summary == "siming highlighted char_b"
    assert state.dynamic_state is not None
    assert state.dynamic_state.social_pressure == 0.7
    assert state.goal_state is not None
    assert state.goal_state.mid_term_strategy == "contain_exposure"
    assert state.goal_state.transition_kind == "repairing"


def test_character_agent_debug_projection_includes_typed_event_and_observation_memory_summaries() -> None:
    projection = CharacterAgentDebugProjection()
    snapshot = CharacterPrivateWorldSnapshot(
        actor_id="char_a",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=210,
        visible_entities=["visual_fact/fixed_gaze_on_target"],
        audible_entities=[],
        attention_targets=["char_b"],
        current_attention_targets=["char_b"],
        clarity_score=0.9,
        certainty_score=0.87,
        updated_at=211,
    )

    state = projection.project_snapshot(
        actor_id="char_a",
        producer_ts=211,
        snapshot=snapshot,
        memory_bundle=CharacterMemoryRecordBundle(
            event_memories=[
                CharacterEventMemoryRecord(
                    memory_id="event:char_a:char_b:1",
                    actor_id="char_a",
                    event_id="evt:char_b:1",
                    source_event_id="evt:char_b:1",
                    world_ts=1,
                    event_type="dialogue",
                    summary="char_b deflected the question",
                    clarity_score=0.72,
                    certainty_score=0.8,
                    refs=["char_b"],
                )
            ],
            observation_memories=[
                CharacterObservationMemoryRecord(
                    memory_id="obs:char_a:char_b:1",
                    actor_id="char_a",
                    source_event_id="evt:char_b:2",
                    world_ts=2,
                    observed_entity_id="char_b",
                    observation_type="posture",
                    observation_summary="char_b avoided eye contact",
                    clarity_score=0.76,
                    certainty_score=0.81,
                    distortion_tags=[],
                    refs=["char_b"],
                )
            ],
        ),
        interpretation_summary="char_b is concealing intent",
        decision_summary="pause and reassess",
        execution_summary="hold position",
        latest_outcome_summary="",
        latest_siming_summary="",
    )

    assert "char_b deflected the question" in state.memory_summary
    assert "char_b avoided eye contact" in state.memory_summary


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
    local_gateway = _LocalGateway()
    l2 = CharacterAgentL2Service(gateway=local_gateway)
    l3 = CharacterAgentL3Service(gateway=local_gateway)
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
