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


class _StubL2:
    def prepare_reasoning_request(
        self,
        *,
        snapshot,
        event,
        memory_bundle,
        control_mode,
        working_memory_state=None,
        current_goal_state=None,
        goal_state_history=None,
        supervision_state=None,
        unresolved_tensions=None,
        background_agenda_state=None,
    ) -> dict[str, object]:
        return {
            "task_kind": "l2_reasoning",
            "context": {
                "actor_id": snapshot.actor_id,
                "control_mode": control_mode,
                "snapshot": snapshot.model_dump(),
                "memory": memory_bundle,
                "event": event.model_dump(),
                "working_memory_state": dict(working_memory_state or {}),
                "current_goal_state": dict(current_goal_state or {}),
                "goal_state_history": list(goal_state_history or []),
                "supervision_state": dict(supervision_state or {}),
                "unresolved_tensions": list(unresolved_tensions or []),
                "background_agenda_state": dict(background_agenda_state or {}),
            },
        }

    def interpret_perceived_event(
        self,
        snapshot,
        event,
        *,
        memory_bundle=None,
        control_mode="agent_full_auto",
        working_memory_state=None,
        current_goal_state=None,
        goal_state_history=None,
        supervision_state=None,
        unresolved_tensions=None,
        background_agenda_state=None,
    ) -> CharacterInterpretation:
        return CharacterInterpretation(
            actor_id=event.actor_id,
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
        clarity_score=0.82,
        certainty_score=0.63,
    )

    runtime.ingest_character_perceived_event(event)

    dynamic_state = runtime.get_dynamic_state("char_a")

    assert dynamic_state["vigilance_level"] == 0.2
    assert dynamic_state["stress_load"] == 0.4
    assert dynamic_state["social_pressure"] == 0.7
    assert dynamic_state["masking_pressure"] == 0.55
    assert dynamic_state["motivation_stack"] == ["preserve_order"]
