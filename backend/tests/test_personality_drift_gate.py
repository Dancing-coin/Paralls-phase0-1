from __future__ import annotations

from copy import deepcopy

from app.character_agent.logic.drift_accumulator import DriftAccumulator
from app.character_agent.logic.drift_promotion_gate import DriftPromotionGate
from app.character_agent.models.drift_candidate import DriftCandidateRecord
from app.character_agent.models.dynamic_state import CharacterDynamicState
from app.character_agent.models.need_tension import NeedTensionState
from app.models.character_agent_runtime import CharacterIntentDecision, CharacterInterpretation
from app.models.character_perceived import CharacterPerceivedEvent
from app.models.self_body_perceived import SelfBodyPerceivedEvent
from app.services.character_agent_runtime import CharacterAgentRuntime


def _make_interpretation(
    *,
    summary: str = "public dismissal near unstable doorway",
    reasoning_trace_summary: str | None = None,
) -> CharacterInterpretation:
    return CharacterInterpretation(
        actor_id="char_a",
        interpreted_summary=summary,
        interpretation_type="social_signal",
        salience_score=0.9,
        ambiguity_level="low",
        risk_level="medium",
        opportunity_level="low",
        attention_target="env_unstable_doorway",
        reasoning_trace_summary=reasoning_trace_summary,
    )


def test_drift_promotion_gate_rejects_single_scene_short_lived_candidate() -> None:
    gate = DriftPromotionGate()
    candidate = DriftCandidateRecord(
        actor_id="char_a",
        key="public_disclosure_caution",
        direction="increased",
        reinforcing_events=2,
        cross_scene_count=1,
        stable_time_span="short_arc",
        confidence=0.9,
        evidence_summary="single incident",
    )

    assert gate.should_promote(candidate) is False


def test_drift_promotion_gate_requires_all_thresholds() -> None:
    gate = DriftPromotionGate()
    candidate = DriftCandidateRecord(
        actor_id="char_a",
        key="public_disclosure_caution",
        direction="increased",
        reinforcing_events=8,
        cross_scene_count=3,
        stable_time_span="long_arc",
        confidence=0.7,
        evidence_summary="repeated public pressure pattern",
    )

    assert gate.should_promote(candidate) is True


def test_drift_accumulator_parses_explicit_runtime_hint_without_mutating_profile() -> None:
    accumulator = DriftAccumulator()
    effective_profile = {
        "identity_core": {
            "character_id": "char_a",
            "canonical_name": "Lin Yue",
        },
        "long_term_personality_drift_layer": {
            "stable_shifts": ["existing_shift"],
        },
    }
    profile_before = deepcopy(effective_profile)

    candidate = accumulator.observe(
        actor_id="char_a",
        effective_profile=effective_profile,
        interpretation=_make_interpretation(
            reasoning_trace_summary=(
                "drift_candidate:"
                "key=public_disclosure_caution|direction=increased|reinforcing_events=8|"
                "cross_scene_count=3|stable_time_span=long_arc|confidence=0.82"
            )
        ),
        dynamic_state=CharacterDynamicState(
            actor_id="char_a",
            vigilance_level=0.6,
            distraction_level=0.1,
            stress_load=0.7,
            social_pressure=0.8,
            masking_pressure=0.6,
        ),
        need_tension_state=NeedTensionState(
            actor_id="char_a",
            safety_pressure=0.7,
            esteem_pressure=0.8,
            dominant_need="safety",
            pressure_sources=["public_dismissal", "spatial_uncertainty"],
        ),
    )

    assert candidate is not None
    assert candidate.key == "public_disclosure_caution"
    assert candidate.cross_scene_count == 3
    assert candidate.reinforcing_events == 8
    assert candidate.stable_time_span == "long_arc"
    assert candidate.confidence == 0.82
    assert effective_profile == profile_before


def test_drift_accumulator_suppresses_candidate_already_present_in_drift_layer() -> None:
    accumulator = DriftAccumulator()

    candidate = accumulator.observe(
        actor_id="char_a",
        effective_profile={
            "identity_core": {
                "character_id": "char_a",
                "canonical_name": "Lin Yue",
            },
            "long_term_personality_drift_layer": {
                "stable_shifts": ["public_disclosure_caution"],
                "reinforced_patterns": [],
                "weakened_patterns": [],
            },
        },
        interpretation=_make_interpretation(
            reasoning_trace_summary=(
                "drift_candidate:"
                "key=public_disclosure_caution|direction=increased|reinforcing_events=8|"
                "cross_scene_count=3|stable_time_span=long_arc|confidence=0.82"
            )
        ),
        dynamic_state=CharacterDynamicState(
            actor_id="char_a",
            vigilance_level=0.6,
            distraction_level=0.1,
            stress_load=0.7,
            social_pressure=0.8,
            masking_pressure=0.6,
        ),
        need_tension_state=NeedTensionState(
            actor_id="char_a",
            safety_pressure=0.7,
            esteem_pressure=0.8,
            dominant_need="safety",
            pressure_sources=["public_dismissal", "spatial_uncertainty"],
        ),
    )

    assert candidate is None


class _StubDriftAccumulator:
    def __init__(self, candidate: DriftCandidateRecord | None) -> None:
        self.candidate = candidate

    def observe(self, **_: object) -> DriftCandidateRecord | None:
        return self.candidate


def test_runtime_records_drift_promotion_event_without_mutating_authored_profile() -> None:
    runtime = CharacterAgentRuntime()
    authored_profile_before = deepcopy(runtime._profile_payload("char_a"))
    runtime._drift_accumulator = _StubDriftAccumulator(
        DriftCandidateRecord(
            actor_id="char_a",
            key="public_disclosure_caution",
            direction="increased",
            reinforcing_events=8,
            cross_scene_count=3,
            stable_time_span="long_arc",
            confidence=0.81,
            evidence_summary="repeated public pressure pattern",
        )
    )

    def interpret_stub(*args, **kwargs) -> CharacterInterpretation:
        return _make_interpretation()

    def select_intent_stub(*args, **kwargs) -> CharacterIntentDecision:
        return CharacterIntentDecision(
            actor_id="char_a",
            selected_intent="observe_target",
            persona_passed=True,
            logic_passed=True,
            gain_loss_passed=True,
            rationale="hold position and observe",
        )

    runtime._l2.interpret_perceived_event = interpret_stub
    runtime._l3.select_intent = select_intent_stub

    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=512,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="public_dismissal near spatial_uncertainty doorway",
            source_candidate_event_id="visual_fact:512:char_a",
            target_environment_id="env_unstable_doorway",
        )
    )

    timeline = runtime.get_session_timeline("char_a")
    drift_events = [
        entry
        for entry in timeline
        if entry["event_type"] == "character_personality_drift_promotion_event"
    ]

    assert len(drift_events) == 1
    assert drift_events[0]["payload"]["key"] == "public_disclosure_caution"
    assert drift_events[0]["payload"]["reinforcing_events"] == 8
    assert runtime._profile_payload("char_a") == authored_profile_before


def test_runtime_suppresses_duplicate_drift_promotion_events_for_same_candidate() -> None:
    runtime = CharacterAgentRuntime()
    runtime._drift_accumulator = _StubDriftAccumulator(
        DriftCandidateRecord(
            actor_id="char_a",
            key="public_disclosure_caution",
            direction="increased",
            reinforcing_events=8,
            cross_scene_count=3,
            stable_time_span="long_arc",
            confidence=0.81,
            evidence_summary="repeated public pressure pattern",
        )
    )

    def interpret_stub(*args, **kwargs) -> CharacterInterpretation:
        return _make_interpretation()

    def select_intent_stub(*args, **kwargs) -> CharacterIntentDecision:
        return CharacterIntentDecision(
            actor_id="char_a",
            selected_intent="observe_target",
            persona_passed=True,
            logic_passed=True,
            gain_loss_passed=True,
            rationale="hold position and observe",
        )

    runtime._l2.interpret_perceived_event = interpret_stub
    runtime._l3.select_intent = select_intent_stub

    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=512,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="public_dismissal near spatial_uncertainty doorway",
            source_candidate_event_id="visual_fact:512:char_a",
            target_environment_id="env_unstable_doorway",
        )
    )
    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=513,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="public_dismissal near spatial_uncertainty doorway",
            source_candidate_event_id="visual_fact:513:char_a",
            target_environment_id="env_unstable_doorway",
        )
    )

    drift_events = [
        entry
        for entry in runtime.get_session_timeline("char_a")
        if entry["event_type"] == "character_personality_drift_promotion_event"
    ]

    assert len(drift_events) == 1


def test_self_body_route_does_not_record_drift_promotion_events() -> None:
    runtime = CharacterAgentRuntime()
    runtime._drift_accumulator = _StubDriftAccumulator(
        DriftCandidateRecord(
            actor_id="char_a",
            key="public_disclosure_caution",
            direction="increased",
            reinforcing_events=8,
            cross_scene_count=3,
            stable_time_span="long_arc",
            confidence=0.81,
            evidence_summary="repeated public pressure pattern",
        )
    )

    def interpret_stub(*args, **kwargs) -> CharacterInterpretation:
        return _make_interpretation(summary="body strain interpretation")

    def select_intent_stub(*args, **kwargs) -> CharacterIntentDecision:
        return CharacterIntentDecision(
            actor_id="char_a",
            selected_intent="observe_target",
            persona_passed=True,
            logic_passed=True,
            gain_loss_passed=True,
            rationale="hold position and observe",
        )

    runtime._l2.interpret_self_body_event = interpret_stub
    runtime._l3.select_intent = select_intent_stub

    runtime.ingest_self_body_perceived_event(
        SelfBodyPerceivedEvent(
            actor_id="char_a",
            body_state_class="interaction_strain",
            producer_ts=620,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="body_state_result/interaction_strain=engaged",
            source_body_result_id="body_result:char_a:620",
        )
    )

    drift_events = [
        entry
        for entry in runtime.get_session_timeline("char_a")
        if entry["event_type"] == "character_personality_drift_promotion_event"
    ]

    assert drift_events == []
