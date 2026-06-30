from app.character_agent.models.cognition_update import CharacterCognitionUpdate
from app.character_agent.models.cognition_delta import (
    CharacterBeliefDelta,
    CharacterDynamicStateDelta,
    CharacterHigherOrderDelta,
    CharacterSocialDelta,
)
from app.character_agent.models.dynamic_state import CharacterDynamicState
from app.character_agent.models.event_memory import CharacterEventMemoryRecord
from app.character_agent.models.goal_runtime import (
    CharacterActiveGoalFrame,
    CharacterGoalHint,
    CharacterGoalStateRecord,
)
from app.character_agent.models.higher_order_memory import CharacterHigherOrderMemoryRecord
from app.character_agent.models.knowledge_memory import CharacterKnowledgeMemoryRecord
from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle
from app.character_agent.models.observation_memory import CharacterObservationMemoryRecord
from app.character_agent.models.social_memory import CharacterSocialMemoryRecord


def test_dynamic_state_tracks_live_subjective_pressure_fields() -> None:
    state = CharacterDynamicState(
        actor_id="char_a",
        vigilance_level=0.7,
        distraction_level=0.2,
        stress_load=0.5,
        social_pressure=0.6,
        masking_pressure=0.3,
        motivation_stack=["preserve_order", "avoid_public_exposure"],
    )

    assert state.motivation_stack == ["preserve_order", "avoid_public_exposure"]


def test_higher_order_memory_tracks_who_knows_what_about_whom() -> None:
    record = CharacterHigherOrderMemoryRecord(
        memory_id="hom:1",
        actor_id="char_a",
        subject_actor_id="char_b",
        proposition_key="obj_letter:is_sensitive",
        meta_belief="char_b suspects char_c knows the letter matters",
        confidence=0.66,
        source_event_id="evt:1",
        producer_ts=10,
    )

    assert record.subject_actor_id == "char_b"
    assert record.confidence == 0.66


def test_event_observation_knowledge_and_social_memory_records_are_typed() -> None:
    event = CharacterEventMemoryRecord(
        memory_id="event:char_a:evt:1:1",
        actor_id="char_a",
        event_id="evt:1",
        source_event_id="evt:1",
        world_ts=10,
        event_type="character_perceived_event",
        summary="char_b spoke nearby",
        clarity_score=0.8,
        certainty_score=0.9,
        refs=["char_b"],
    )
    observation = CharacterObservationMemoryRecord(
        memory_id="observation:char_a:evt:1:char_b:character_perceived_event:1",
        actor_id="char_a",
        source_event_id="evt:1",
        world_ts=10,
        observed_entity_id="char_b",
        observation_type="character_perceived_event",
        observation_summary="saw char_b speaking",
        clarity_score=0.4,
        certainty_score=0.55,
        distortion_tags=["occluded"],
        refs=["char_b"],
    )
    knowledge = CharacterKnowledgeMemoryRecord(
        memory_id="knowledge:char_a:char_b:is_probing",
        actor_id="char_a",
        proposition_key="char_b:is_probing",
        proposition="char_b may be probing",
        state="suspected",
        confidence=0.66,
        source_event_id="evt:1",
        producer_ts=10,
    )
    social = CharacterSocialMemoryRecord(
        memory_id="social:char_a:char_b",
        actor_id="char_a",
        entity_id="char_b",
        trust_baseline=0.3,
        suspicion_baseline=0.8,
        intimacy=0.1,
        dependency=0.0,
        unresolved_tension=0.4,
        shared_secret_refs=["secret:1"],
        source_event_id="evt:1",
        producer_ts=10,
    )

    assert event.summary == "char_b spoke nearby"
    assert observation.distortion_tags == ["occluded"]
    assert knowledge.proposition_key == "char_b:is_probing"
    assert social.entity_id == "char_b"


def test_memory_record_bundle_groups_typed_cognitive_memory_pools() -> None:
    bundle = CharacterMemoryRecordBundle(
        event_memories=[
            CharacterEventMemoryRecord(
                memory_id="event:char_a:evt:1:1",
                actor_id="char_a",
                event_id="evt:1",
                source_event_id="evt:1",
                world_ts=10,
                event_type="character_perceived_event",
                summary="char_b spoke nearby",
                clarity_score=0.8,
                certainty_score=0.9,
                refs=["char_b"],
            )
        ],
        observation_memories=[
            CharacterObservationMemoryRecord(
                memory_id="observation:char_a:evt:1:char_b:character_perceived_event:1",
                actor_id="char_a",
                source_event_id="evt:1",
                world_ts=10,
                observed_entity_id="char_b",
                observation_type="character_perceived_event",
                observation_summary="saw char_b speaking",
                clarity_score=0.4,
                certainty_score=0.55,
                distortion_tags=["occluded"],
                refs=["char_b"],
            )
        ],
        knowledge_memories=[
            CharacterKnowledgeMemoryRecord(
                memory_id="knowledge:char_a:char_b:is_probing",
                actor_id="char_a",
                proposition_key="char_b:is_probing",
                proposition="char_b may be probing",
                state="suspected",
                confidence=0.66,
                source_event_id="evt:1",
                producer_ts=10,
            )
        ],
        social_memories=[
            CharacterSocialMemoryRecord(
                memory_id="social:char_a:char_b",
                actor_id="char_a",
                entity_id="char_b",
                trust_baseline=0.3,
                suspicion_baseline=0.8,
                intimacy=0.1,
                dependency=0.0,
                unresolved_tension=0.4,
                shared_secret_refs=["secret:1"],
                source_event_id="evt:1",
                producer_ts=10,
            )
        ],
        higher_order_memories=[
            CharacterHigherOrderMemoryRecord(
                memory_id="hom:1",
                actor_id="char_a",
                subject_actor_id="char_b",
                proposition_key="obj_letter:is_sensitive",
                meta_belief="char_b suspects char_c knows the letter matters",
                confidence=0.66,
                source_event_id="evt:1",
                producer_ts=10,
            )
        ],
    )

    assert bundle.event_memories[0].summary == "char_b spoke nearby"
    assert bundle.knowledge_memories[0].proposition_key == "char_b:is_probing"


def test_cognition_update_groups_belief_social_higher_order_and_dynamic_deltas() -> None:
    update = CharacterCognitionUpdate(
        interpreted_situation="char_b appears to test whether char_c will disclose",
        belief_deltas=[CharacterBeliefDelta(proposition_key="char_b:is_probing", state="suspected")],
        social_deltas=[CharacterSocialDelta(entity_id="char_b", suspicion_baseline=0.8)],
        higher_order_deltas=[CharacterHigherOrderDelta(subject_actor_id="char_b", meta_belief="char_b suspects char_c knows more")],
        dynamic_state_delta=CharacterDynamicStateDelta(social_pressure=0.6, masking_pressure=0.4),
        goal_hints=[
            CharacterGoalHint(
                goal="protect_secret",
                source="social_signal",
                strength=0.85,
                evidence_tags=["guarded_attention"],
            )
        ],
        reasoning_trace_summary="char_b:probing-read",
    )

    assert update.dynamic_state_delta.social_pressure == 0.6
    assert update.belief_deltas[0].proposition_key == "char_b:is_probing"
    assert update.social_deltas[0].entity_id == "char_b"
    assert update.higher_order_deltas[0].subject_actor_id == "char_b"
    assert update.goal_hints[0].goal == "protect_secret"
    assert update.reasoning_trace_summary == "char_b:probing-read"


def test_goal_hint_is_a_typed_runtime_object() -> None:
    hint = CharacterGoalHint(
        goal="protect_secret",
        source="social_signal",
        strength=0.86,
        evidence_tags=["guarded_attention", "target_knows_sensitive_object"],
    )

    assert hint.goal == "protect_secret"
    assert hint.evidence_tags == ["guarded_attention", "target_knows_sensitive_object"]


def test_active_goal_frame_tracks_long_mid_and_immediate_layers() -> None:
    frame = CharacterActiveGoalFrame(
        primary_goal="protect_secret",
        long_term_goal="preserve_order",
        mid_term_strategy="contain_exposure",
        immediate_goal="withhold_until_private",
        supporting_goals=["clarify_intent"],
        blockers=["char_b_public_presence"],
        goal_sources=["l2_goal_hint:social_signal"],
        urgency="high",
    )

    assert frame.mid_term_strategy == "contain_exposure"


def test_goal_state_record_tracks_repair_and_recovery_metadata() -> None:
    record = CharacterGoalStateRecord(
        actor_id="char_c",
        primary_goal="protect_secret",
        long_term_goal="preserve_order",
        mid_term_strategy="repair_cover_story",
        immediate_goal="withdraw",
        supporting_goals=["preserve_optionality"],
        blockers=["target_already_suspicious"],
        goal_sources=["knowledge_state", "l2_goal_hint:social_signal"],
        urgency="high",
        transition_kind="repairing",
        transition_reason_tags=["strategy_blocked", "social_signal_reappraisal"],
    )

    assert record.transition_kind == "repairing"
