import pytest

from app.character_agent.models.background_agenda import CharacterBackgroundAgendaEntry, CharacterBackgroundAgendaState
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
    CharacterGoalPortfolioEntry,
    CharacterGoalStateRecord,
)
from app.character_agent.models.higher_order_memory import CharacterHigherOrderMemoryRecord
from app.character_agent.models.knowledge_memory import CharacterKnowledgeMemoryRecord
from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle
from app.character_agent.models.observation_memory import CharacterObservationMemoryRecord
from app.character_agent.models.social_memory import CharacterSocialMemoryRecord
from app.character_agent.models.supervision import (
    CharacterBackgroundCognitionResult,
    CharacterSupervisionAuthorization,
    CharacterSupervisionConstraints,
    CharacterSupervisionRequest,
    CharacterSupervisionState,
    CharacterUnresolvedTension,
)


def test_dynamic_state_delta_as_mapping_includes_affect_valence() -> None:
    delta = CharacterDynamicStateDelta(affect_valence=-0.8)

    assert delta.as_mapping() == {"affect_valence": -0.8}


def test_dynamic_state_delta_as_mapping_includes_positive_affect_fields() -> None:
    delta = CharacterDynamicStateDelta(
        joy=0.7,
        calm=0.6,
        trust=0.5,
        gratitude=0.4,
        pride=0.3,
        confidence=0.2,
        hope=0.1,
    )

    assert delta.as_mapping() == {
        "joy": 0.7,
        "calm": 0.6,
        "trust": 0.5,
        "gratitude": 0.4,
        "pride": 0.3,
        "confidence": 0.2,
        "hope": 0.1,
    }


def test_dynamic_state_delta_rejects_out_of_range_affect_valence() -> None:
    with pytest.raises(ValueError):
        CharacterDynamicStateDelta(affect_valence=-1.1)


def test_dynamic_state_delta_rejects_bool_affect_valence() -> None:
    with pytest.raises(ValueError):
        CharacterDynamicStateDelta(affect_valence=True)


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


def test_goal_portfolio_entry_tracks_parallel_goal_metadata() -> None:
    entry = CharacterGoalPortfolioEntry(
        goal_id="goal_protect_secret",
        goal="protect_secret",
        horizon="long",
        status="active",
        priority=0.92,
        urgency="high",
        source="model_deliberation",
        target_ref="char_b",
        blockers=["high_masking_pressure"],
        supporting_evidence=["guarded_attention"],
    )

    assert entry.goal_id == "goal_protect_secret"
    assert entry.horizon == "long"
    assert entry.supporting_evidence == ["guarded_attention"]


def test_active_goal_frame_can_carry_parallel_goal_portfolio_state() -> None:
    frame = CharacterActiveGoalFrame(
        primary_goal="protect_secret",
        long_term_goal="preserve_order",
        mid_term_strategy="contain_exposure",
        immediate_goal="withhold_until_private",
        supporting_goals=["clarify_intent"],
        blockers=["char_b_public_presence"],
        goal_sources=["l2_goal_hint:social_signal"],
        urgency="high",
        dominant_goal_id="goal_protect_secret",
        preserved_goal_ids=["goal_clarify_intent"],
        suppressed_goal_ids=["goal_social_ease"],
        goal_arbitration_summary="safety dominates while keeping clarification active",
        goal_portfolio=[
            CharacterGoalPortfolioEntry(
                goal_id="goal_protect_secret",
                goal="protect_secret",
                horizon="long",
                status="active",
                priority=0.93,
                urgency="high",
                source="model_deliberation",
            ),
            CharacterGoalPortfolioEntry(
                goal_id="goal_clarify_intent",
                goal="clarify_intent",
                horizon="mid",
                status="active",
                priority=0.71,
                urgency="medium",
                source="model_deliberation",
            ),
        ],
    )

    assert frame.dominant_goal_id == "goal_protect_secret"
    assert frame.preserved_goal_ids == ["goal_clarify_intent"]
    assert frame.goal_portfolio[1].goal == "clarify_intent"


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
        dominant_goal_id="goal_protect_secret",
        preserved_goal_ids=["goal_preserve_optionality"],
        suppressed_goal_ids=["goal_public_reassurance"],
        goal_arbitration_summary="safety remains dominant while public reassurance is suppressed",
        goal_portfolio=[
            CharacterGoalPortfolioEntry(
                goal_id="goal_protect_secret",
                goal="protect_secret",
                horizon="long",
                status="active",
                priority=0.94,
                urgency="high",
                source="model_deliberation",
            )
        ],
        transition_kind="repairing",
        transition_reason_tags=["strategy_blocked", "social_signal_reappraisal"],
    )

    assert record.transition_kind == "repairing"
    assert record.goal_portfolio[0].goal_id == "goal_protect_secret"


def test_supervision_models_capture_authorized_background_cognition_contract() -> None:
    constraints = CharacterSupervisionConstraints(
        allow_background_loop=True,
        background_mode="quiet",
        min_tick_interval_ms=9000,
        max_tick_budget_tokens=220,
        attention_theme=["safety_watch"],
        blocked_goal_classes=["conflict_escalation"],
        allow_proactive_initiation=False,
    )
    request = CharacterSupervisionRequest(
        request_id="req:1",
        actor_id="char_a",
        requested_level="medium",
        reason_code="safety_risk",
        reason_summary="room instability is rising",
        requested_constraints=constraints,
        requested_duration_ms=30000,
        producer_ts=10,
    )
    authorization = CharacterSupervisionAuthorization(
        authorization_id="auth:1",
        actor_id="char_a",
        approved_level="medium",
        approved_by="strategy_service",
        approval_reason="approved by strategy",
        constraints=constraints,
        effective_from_ts=10,
        expires_at_ts=40,
        producer_ts=10,
    )
    state = CharacterSupervisionState(
        actor_id="char_a",
        current_level="medium",
        source="strategy_authorized",
        active_constraints=constraints,
        entered_at_ts=10,
        expires_at_ts=40,
        last_refresh_ts=10,
        last_reason_summary="approved by strategy",
    )
    tension = CharacterUnresolvedTension(
        tension_id="char_a:constraint_result:obj_letter",
        category="constraint_result",
        summary="obj_letter remains locked",
        target_ref="obj_letter",
        priority=0.82,
        status="active",
        source_event_id="result:1",
        source_stage="settlement_result",
        last_reinforced_ts=12,
    )
    result = CharacterBackgroundCognitionResult(
        actor_id="char_a",
        ran=True,
        producer_ts=20,
        reason="background_tick_completed",
        interpretation_summary="the lock failure still matters",
        selected_intent="observe",
        current_level="medium",
    )

    assert request.requested_constraints.background_mode == "quiet"
    assert authorization.constraints.allow_proactive_initiation is False
    assert state.active_constraints.blocked_goal_classes == ["conflict_escalation"]
    assert tension.target_ref == "obj_letter"
    assert result.current_level == "medium"


def test_background_agenda_state_tracks_persistent_agenda_entries() -> None:
    state = CharacterBackgroundAgendaState(
        actor_id="char_a",
        latent_tendency="observe",
        watch_focus="obj_letter",
        agenda_summary="keep tracking the locked object while preserving cover",
        agenda_phase="quiet",
        supervision_level="medium",
        dominant_agenda_id="agenda_clarify_obj_letter",
        agenda_entries=[
            CharacterBackgroundAgendaEntry(
                agenda_id="agenda_clarify_obj_letter",
                agenda_kind="clarify",
                title="clarify obj_letter anomaly",
                summary="the object remains suspicious after earlier failure",
                target_ref="obj_letter",
                horizon="mid",
                status="active",
                priority=0.82,
                source="background_reflection",
                last_reinforced_ts=20,
            ),
            CharacterBackgroundAgendaEntry(
                agenda_id="agenda_preserve_cover",
                agenda_kind="protect",
                title="preserve cover",
                target_ref="char_b",
                horizon="long",
                status="active",
                priority=0.74,
                source="goal_state",
                last_reinforced_ts=20,
            ),
        ],
        updated_at=20,
    )

    assert state.dominant_agenda_id == "agenda_clarify_obj_letter"
    assert state.agenda_entries[0].agenda_kind == "clarify"
    assert state.agenda_entries[1].title == "preserve cover"
