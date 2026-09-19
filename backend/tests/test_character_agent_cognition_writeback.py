import pytest

from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.models.cognition_delta import (
    CharacterBeliefDelta,
    CharacterDynamicStateDelta,
    CharacterHigherOrderDelta,
    CharacterSocialDelta,
)
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.models.character_agent_runtime import CharacterInterpretation
from app.models.character_perceived import CharacterPerceivedEvent
from app.services.character_agent_runtime import CharacterAgentRuntime


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

    def complete_prepared_request(self, request_json):
        return self._gateway.complete_prepared_request(request_json)

    def prepare_run_request(self, *, task_kind, context, route_override=None, prepared_recall=None):
        return self._gateway.prepare_run_request(
            task_kind=task_kind, context=context, route_override=route_override or "local_only",
 prepared_recall=prepared_recall,
        )


class _StubL2(CharacterAgentL2Service):
    def __init__(self):
        super().__init__(gateway=_LocalGateway())

    def map_reasoning_output(self, *, actor_id, output) -> CharacterInterpretation:
        return CharacterInterpretation(
            actor_id=actor_id,
            interpreted_summary="char_b is probing for a private disclosure",
            interpretation_type="social_signal",
            salience_score=0.84,
            ambiguity_level="medium",
            risk_level="medium",
            opportunity_level="low",
            attention_target="char_b",
            inner_prompt_candidate="preserve optionality",
            belief_deltas=[CharacterBeliefDelta(proposition_key="char_b:is_probing", state="suspected", confidence=0.72)],
            social_deltas=[CharacterSocialDelta(entity_id="char_b", trust_baseline=0.3, suspicion_baseline=0.82)],
            higher_order_deltas=[
                CharacterHigherOrderDelta(
                    subject_actor_id="char_b",
                    proposition_key="obj_letter:is_sensitive",
                    meta_belief="char_b suspects char_c knows more",
                    confidence=0.66,
                )
            ],
            dynamic_state_delta=CharacterDynamicStateDelta(social_pressure=0.7, masking_pressure=0.55),
            reasoning_trace_summary="char_c:probing-read",
        )


class _PositiveAffectStubL2(_StubL2):
    def map_reasoning_output(self, *, actor_id, output) -> CharacterInterpretation:
        interpretation = super().map_reasoning_output(actor_id=actor_id, output=output)
        return interpretation.model_copy(
            update={
                "dynamic_state_delta": CharacterDynamicStateDelta(
                    trust=0.6,
                    gratitude=0.5,
                    pride=0.4,
                    confidence=0.3,
                )
            }
        )


def test_runtime_applies_cognition_writeback_from_l2_output() -> None:
    runtime = CharacterAgentRuntime()
    runtime._l2 = _StubL2()
    runtime._l3 = CharacterAgentL3Service(gateway=_LocalGateway())
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="auditory",
        producer_ts=501,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:501:char_a",
        source_actor_id="char_b",
        target_actor_id="char_a",
        clarity_score=0.82,
        certainty_score=0.63,
    )

    runtime.ingest_character_perceived_event(event)

    timeline = runtime.get_session_timeline("char_a")
    memory_bundle = runtime.get_memory_bundle("char_a")
    dynamic_state = runtime.get_dynamic_state("char_a")
    event_types = [entry["event_type"] for entry in timeline]

    assert "knowledge_belief_event" in event_types
    assert "social_cognition_event" in event_types
    assert "higher_order_belief_event" in event_types
    assert "dynamic_state_event" in event_types
    assert any(item["proposition_key"] == "char_b:is_probing" for item in memory_bundle["knowledge_memories"])
    assert any(item["entity_id"] == "char_b" for item in memory_bundle["social_memories"])
    assert any(item["subject_actor_id"] == "char_b" for item in memory_bundle["higher_order_memories"])
    assert dynamic_state["social_pressure"] == 0.7
    assert dynamic_state["masking_pressure"] == 0.55


@pytest.mark.parametrize("durable", [False, True])
def test_runtime_applies_positive_affect_writeback_into_grouped_affect_state(tmp_path, durable) -> None:
    runtime = CharacterAgentRuntime(storage_root=tmp_path if durable else None)
    runtime._l2 = _PositiveAffectStubL2()
    runtime._l3 = CharacterAgentL3Service(gateway=_LocalGateway())
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="auditory",
        producer_ts=504,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/thanks_and_trust",
        source_candidate_event_id="auditory_fact:504:char_a",
        source_actor_id="char_b",
        target_actor_id="char_a",
        clarity_score=0.9,
        certainty_score=0.9,
    )

    runtime.ingest_character_perceived_event(event)

    typed_dynamic_state = runtime.get_dynamic_state_record("char_a")

    assert typed_dynamic_state.affect_state.trust == 0.6
    assert typed_dynamic_state.affect_state.gratitude == 0.5
    assert typed_dynamic_state.affect_state.pride == 0.4
    assert typed_dynamic_state.affect_state.confidence == 0.3
    expected = typed_dynamic_state.storage_dump()
    dynamic_events = [entry for entry in runtime.get_session_timeline("char_a")
                      if entry["event_type"] == "dynamic_state_event"]
    assert dynamic_events[-1]["payload"] == expected
    assert runtime._session_store.read_runtime_state("char_a")["dynamic_state"] == expected
    runtime.close()
    if durable:
        reopened = CharacterAgentRuntime(storage_root=tmp_path)
        try:
            assert reopened.get_dynamic_state_record("char_a").storage_dump() == expected
        finally:
            reopened.close()


def test_runtime_cognition_writeback_merges_dynamic_state_without_dropping_existing_fields() -> None:
    runtime = CharacterAgentRuntime()
    runtime._dynamic_state_store.write(
        "char_a",
        {
            "actor_id": "char_a",
            "vigilance_level": 0.2,
            "distraction_level": 0.1,
            "stress_load": 0.4,
            "social_pressure": 0.3,
            "masking_pressure": 0.2,
            "motivation_stack": ["preserve_order"],
        },
    )
    runtime._l2 = _StubL2()
    runtime._l3 = CharacterAgentL3Service(gateway=_LocalGateway())
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="auditory",
        producer_ts=502,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:502:char_a",
        source_actor_id="char_b",
        target_actor_id="char_a",
        clarity_score=0.96,
        certainty_score=0.94,
    )

    runtime.ingest_character_perceived_event(event)

    dynamic_state = runtime.get_dynamic_state("char_a")

    assert dynamic_state["vigilance_level"] == 0.2
    assert dynamic_state["stress_load"] == 0.4
    assert dynamic_state["social_pressure"] == 0.7
    assert dynamic_state["masking_pressure"] == 0.55
    assert dynamic_state["motivation_stack"] == ["preserve_order"]
