from copy import deepcopy

from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.models.cognition_delta import (
    CharacterBeliefDelta,
    CharacterDynamicStateDelta,
    CharacterHigherOrderDelta,
    CharacterSocialDelta,
)
from app.character_agent.models.dynamic_state import CharacterDynamicState
from app.character_agent.models.goal_runtime import CharacterGoalHint
from app.character_agent.models.higher_order_memory import CharacterHigherOrderMemoryRecord
from app.character_agent.models.knowledge_memory import CharacterKnowledgeMemoryRecord
from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle
from app.character_agent.models.social_memory import CharacterSocialMemoryRecord
from app.character_agent.models.working_memory_state import CharacterWorkingMemoryState
from app.models.character_agent_runtime import CharacterPrivateWorldSnapshot
from app.models.character_perceived import CharacterPerceivedEvent
from app.services.character_agent_l2 import CharacterAgentL2Service


class _RecordingGateway:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.requests: list[dict[str, object]] = []

    def run_task(
        self,
        *,
        task_kind: str,
        context: dict[str, object],
        route_override: str | None = None,
    ) -> dict[str, object]:
        self.requests.append(
            {
                "task_kind": task_kind,
                "context": context,
                "route_override": route_override,
            }
        )
        return self.response


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

    def prepare_run_request(
        self,
        *,
        task_kind: str,
        context: dict[str, object],
        route_override: str | None = None,
    ) -> dict[str, object]:
        return self._gateway.prepare_run_request(
            task_kind=task_kind,
            context=context,
            route_override=route_override or "local_only",
        )


class _StubProfile:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = deepcopy(payload)

    def model_dump(self) -> dict[str, object]:
        return deepcopy(self._payload)


class _StubProfileLoader:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = deepcopy(payload)
        self.loaded_actor_ids: list[str] = []

    def load(self, actor_id: str) -> _StubProfile:
        self.loaded_actor_ids.append(actor_id)
        return _StubProfile(self.payload)


def _profile_payload(
    *,
    actor_id: str = "char_a",
    canonical_name: str = "Lin Yue",
    occupation_role: str = "mediator",
) -> dict[str, object]:
    return {
        "identity_core": {
            "character_id": actor_id,
            "canonical_name": canonical_name,
            "aliases": [canonical_name],
            "occupation_role": occupation_role,
        },
        "trait_vector_layer": {
            "courage": 0.64,
            "scheming": 0.31,
            "empathy": 0.82,
            "rationality": 0.74,
            "sociability": 0.58,
        },
        "virtue_value_layer": {
            "value_priorities": ["care", "order", "trustworthiness"],
            "red_lines": ["expose another person's private record casually"],
            "forbidden_behaviors": ["fabricate authority"],
        },
        "capability_constraint_layer": {
            "skills": ["observation", "mediation"],
            "knowledge_domains": ["archive routine", "room etiquette"],
            "physical_constraints": ["not built for prolonged sprinting"],
            "psychological_constraints": ["resists escalating conflict before evidence is clear"],
            "social_constraints": ["cannot authorize sealed object access alone"],
        },
        "conversation_personality_layer": {
            "social_openness": 0.57,
            "privacy_sensitivity": 0.63,
            "talk_initiative": 0.48,
            "deception_control": 0.87,
            "trust_threshold_for_private_talk": 0.66,
        },
    }


def _service(
    *,
    gateway: _RecordingGateway | None = None,
    actor_id: str = "char_a",
    canonical_name: str = "Lin Yue",
    occupation_role: str = "mediator",
) -> tuple[CharacterAgentL2Service, _StubProfileLoader]:
    profile_loader = _StubProfileLoader(
        _profile_payload(
            actor_id=actor_id,
            canonical_name=canonical_name,
            occupation_role=occupation_role,
        )
    )
    return (
        CharacterAgentL2Service(gateway=gateway, profile_loader=profile_loader),
        profile_loader,
    )


def _snapshot() -> CharacterPrivateWorldSnapshot:
    return CharacterPrivateWorldSnapshot(
        actor_id="char_a",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=1300,
        updated_at=1300,
        audible_entities=["auditory_fact/speaker_active"],
        last_siming_catalyst="watch obj_letter",
        clarity_score=0.82,
        certainty_score=0.61,
    )


def test_l2_reasoner_prepares_model_run_request_from_snapshot_memory_and_control_mode() -> None:
    service, profile_loader = _service()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="auditory",
        producer_ts=1301,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:1301:char_a",
        clarity_score=0.82,
        certainty_score=0.61,
    )

    run_request = service.prepare_reasoning_request(
        snapshot=_snapshot(),
        event=event,
        memory_bundle={
            "working_memory": [{"event_id": "evt:1300"}],
            "event_memories": [{"summary": "char_a spoke nearby"}],
            "observation_memories": [{"observation_summary": "char_a spoke nearby"}],
            "knowledge_memories": [{"proposition_key": "social:char_a:trust_level", "proposition": "char_a:trust_level=guarded"}],
            "social_memories": [{"entity_id": "char_a", "trust_baseline": 0.25}],
        },
        control_mode="player_priority_assisted",
    )

    assert run_request["task_kind"] == "l2_reasoning"
    assert run_request["context"]["actor_id"] == "char_a"
    assert run_request["context"]["control_mode"] == "player_priority_assisted"
    assert run_request["context"]["profile"]["identity_core"]["character_id"] == "char_a"
    assert run_request["context"]["memory"]["knowledge_memories"][0]["proposition_key"] == "social:char_a:trust_level"
    assert run_request["context"]["memory"]["event_memories"][0]["summary"] == "char_a spoke nearby"
    assert run_request["context"]["snapshot"]["last_siming_catalyst"] == "watch obj_letter"
    assert run_request["context"]["working_memory_state"] == {}
    assert "character_id=char_a" in run_request["prompt"]["user_instruction"]
    assert "canonical_name=Lin Yue" in run_request["prompt"]["user_instruction"]
    assert "occupation_role=mediator" in run_request["prompt"]["user_instruction"]
    assert run_request["route"]["route_mode"] == "online_default"
    assert profile_loader.loaded_actor_ids == ["char_a"]


def test_l2_reasoner_prompt_includes_profile_behavioral_fields_for_model_routes() -> None:
    service, _ = _service()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="auditory",
        producer_ts=1301,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:1301:char_a",
        clarity_score=0.82,
        certainty_score=0.61,
    )

    run_request = service.prepare_reasoning_request(
        snapshot=_snapshot(),
        event=event,
        memory_bundle={
            "working_memory": [],
            "event_memories": [],
            "observation_memories": [],
            "knowledge_memories": [],
            "social_memories": [],
        },
        control_mode="player_priority_assisted",
    )

    prompt = run_request["prompt"]["user_instruction"]

    assert "value_priorities=care|order|trustworthiness" in prompt
    assert "skills=observation|mediation" in prompt
    assert "privacy_sensitivity=0.63" in prompt
    assert "trust_threshold_for_private_talk=0.66" in prompt


def test_l2_reasoner_prompt_includes_compact_personality_projection_summary() -> None:
    service, _ = _service()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="auditory",
        producer_ts=1301,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:1301:char_a",
        clarity_score=0.82,
        certainty_score=0.61,
    )

    run_request = service.prepare_reasoning_request(
        snapshot=_snapshot(),
        event=event,
        memory_bundle={
            "working_memory": [],
            "event_memories": [],
            "observation_memories": [],
            "knowledge_memories": [],
            "social_memories": [],
        },
        control_mode="player_priority_assisted",
        effective_profile={
            **_profile_payload(),
            "personality_projection": {
                "conflict_deescalation_bias": 0.83,
                "procedural_discipline": 0.84,
                "stress_vulnerability": 0.31,
                "empathic_attunement": 0.81,
            },
        },
    )

    prompt = run_request["prompt"]["user_instruction"]

    assert (
        "personality_projection=conflict_deescalation_bias=0.83|"
        "procedural_discipline=0.84|stress_vulnerability=0.31"
    ) in prompt
    assert "empathic_attunement=0.81" not in prompt
    assert "agreeableness" not in prompt


def test_l2_reasoner_accepts_typed_working_memory_state_in_reasoning_request() -> None:
    service, _ = _service()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="auditory",
        producer_ts=1301,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:1301:char_a",
        clarity_score=0.82,
        certainty_score=0.61,
    )

    run_request = service.prepare_reasoning_request(
        snapshot=_snapshot(),
        event=event,
        memory_bundle={
            "working_memory": [],
            "event_memories": [],
            "observation_memories": [],
            "knowledge_memories": [],
            "social_memories": [],
        },
        control_mode="player_priority_assisted",
        working_memory_state=CharacterWorkingMemoryState(
            recent_perceived_events=[{"event_type": "character_perceived_event"}],
            recent_esm_results=[],
            recent_siming_catalysts=[],
            private_snapshot={"actor_id": "char_a"},
            dynamic_state=CharacterDynamicState(
                actor_id="char_a",
                vigilance_level=0.2,
                distraction_level=0.1,
                stress_load=0.4,
                social_pressure=0.3,
                masking_pressure=0.2,
                motivation_stack=["preserve_order"],
            ),
        ),
    )

    assert run_request["context"]["working_memory_state"]["dynamic_state"]["actor_id"] == "char_a"
    assert run_request["context"]["working_memory_state"]["dynamic_state"]["motivation_stack"] == ["preserve_order"]


def test_l2_reasoner_accepts_typed_memory_record_bundle_in_reasoning_request() -> None:
    service, _ = _service()
    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="auditory",
        producer_ts=1301,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:1301:char_a",
        clarity_score=0.82,
        certainty_score=0.61,
    )

    run_request = service.prepare_reasoning_request(
        snapshot=_snapshot(),
        event=event,
        memory_bundle=CharacterMemoryRecordBundle(
            knowledge_memories=[
                CharacterKnowledgeMemoryRecord(
                    memory_id="knowledge:char_a:social:char_a:trust_level",
                    actor_id="char_a",
                    proposition_key="social:char_a:trust_level",
                    proposition="char_a:trust_level=guarded",
                    state="tentatively_believed",
                    confidence=0.65,
                    source_event_id="evt:1",
                    producer_ts=1,
                )
            ],
            social_memories=[
                CharacterSocialMemoryRecord(
                    memory_id="social:char_a:char_a",
                    actor_id="char_a",
                    entity_id="char_a",
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
                    memory_id="higher:char_a:char_a:1",
                    actor_id="char_a",
                    subject_actor_id="char_a",
                    proposition_key="social_probe:knowledge_asymmetry",
                    meta_belief="char_a suspects char_b knows more",
                    confidence=0.72,
                    source_event_id="evt:3",
                    producer_ts=3,
                )
            ],
        ),
        control_mode="player_priority_assisted",
    )

    assert run_request["context"]["memory"]["knowledge_memories"][0]["proposition_key"] == "social:char_a:trust_level"
    assert run_request["context"]["memory"]["social_memories"][0]["entity_id"] == "char_a"


def test_l2_reasoner_maps_structured_gateway_output_into_interpretation() -> None:
    service, _ = _service()

    interpretation = service.map_reasoning_output(
        actor_id="char_a",
        output={
            "interpreted_summary": "char_a may be speaking nearby",
            "interpretation_type": "social_signal",
            "salience_score": 0.82,
            "ambiguity_level": "medium",
            "risk_level": "low",
            "opportunity_level": "medium",
            "attention_target": "char_a",
            "inner_prompt_candidate": "listen before responding",
        },
    )

    assert interpretation.actor_id == "char_a"
    assert interpretation.interpreted_summary == "char_a may be speaking nearby"
    assert interpretation.interpretation_type == "social_signal"
    assert interpretation.attention_target == "char_a"


def test_l2_reasoner_maps_belief_social_higher_order_and_dynamic_deltas() -> None:
    service, _ = _service()

    interpretation = service.map_reasoning_output(
        actor_id="char_a",
        output={
            "interpreted_summary": "char_b is probing",
            "interpretation_type": "social_signal",
            "salience_score": 0.8,
            "ambiguity_level": "medium",
            "risk_level": "medium",
            "opportunity_level": "low",
            "attention_target": "char_b",
            "inner_prompt_candidate": "stay guarded",
            "belief_deltas": [{"proposition_key": "char_b:is_probing", "state": "suspected"}],
            "social_deltas": [{"entity_id": "char_b", "suspicion_baseline": 0.8}],
            "higher_order_deltas": [{"subject_actor_id": "char_b", "meta_belief": "char_b suspects char_c knows more"}],
            "dynamic_state_delta": {"social_pressure": 0.7},
            "goal_hints": [
                {
                    "goal": "protect_secret",
                    "source": "social_signal",
                    "strength": 0.85,
                    "evidence_tags": ["guarded_attention"],
                }
            ],
            "reasoning_trace_summary": "char_a:probing-read",
        },
    )

    assert isinstance(interpretation.belief_deltas[0], CharacterBeliefDelta)
    assert isinstance(interpretation.social_deltas[0], CharacterSocialDelta)
    assert isinstance(interpretation.higher_order_deltas[0], CharacterHigherOrderDelta)
    assert interpretation.belief_deltas[0].proposition_key == "char_b:is_probing"
    assert interpretation.social_deltas[0].entity_id == "char_b"
    assert interpretation.higher_order_deltas[0].subject_actor_id == "char_b"
    assert isinstance(interpretation.dynamic_state_delta, CharacterDynamicStateDelta)
    assert interpretation.dynamic_state_delta.social_pressure == 0.7
    assert isinstance(interpretation.goal_hints[0], CharacterGoalHint)
    assert interpretation.goal_hints[0].evidence_tags == ["guarded_attention"]
    assert interpretation.reasoning_trace_summary == "char_a:probing-read"


def test_l2_reasoner_uses_model_gateway_for_interpretation() -> None:
    gateway = _RecordingGateway(
        {
            "interpreted_summary": "char_a may be speaking nearby",
            "interpretation_type": "social_signal",
            "salience_score": 0.93,
            "ambiguity_level": "medium",
            "risk_level": "low",
            "opportunity_level": "medium",
            "attention_target": "char_a",
            "inner_prompt_candidate": "listen before responding",
        }
    )
    service, profile_loader = _service(gateway=gateway)

    interpretation = service.interpret_perceived_event(
        _snapshot(),
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="auditory",
            producer_ts=1301,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="auditory_fact/speaker_active",
            source_candidate_event_id="auditory_fact:1301:char_a",
            clarity_score=0.82,
            certainty_score=0.61,
        ),
    )

    assert gateway.requests
    assert gateway.requests[0]["task_kind"] == "l2_reasoning"
    assert gateway.requests[0]["context"]["profile"]["identity_core"]["character_id"] == "char_a"
    assert "knowledge_memories" in gateway.requests[0]["context"]["memory"]
    assert interpretation.interpreted_summary == "char_a may be speaking nearby"
    assert interpretation.attention_target == "char_a"
    assert profile_loader.loaded_actor_ids == ["char_a"]


def test_l2_reasoner_offline_path_raises_risk_for_active_anomalies() -> None:
    service, _ = _service(gateway=_LocalGateway())
    snapshot = _snapshot().model_copy(update={"active_anomalies": ["olfactory_fact/smoke_density_rise"]})
    interpretation = service.interpret_perceived_event(
        snapshot,
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="olfactory",
            producer_ts=1302,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="olfactory_fact/smoke_density_rise",
            source_candidate_event_id="olfactory_fact:1302:char_a",
            clarity_score=0.66,
            certainty_score=0.53,
        ),
    )

    assert interpretation.risk_level == "medium"
    assert interpretation.ambiguity_level == "high"


def test_l2_reasoner_offline_path_treats_body_state_hints_as_body_state_interpretation() -> None:
    service, _ = _service(gateway=_LocalGateway())
    snapshot = _snapshot().model_copy(
        update={
            "body_state_hints": ["interaction_strain:body_state_result/interaction_strain=engaged"],
            "audible_entities": [],
        }
    )
    interpretation = service.interpret_perceived_event(
        snapshot,
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=1303,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="body_state_result/interaction_strain=engaged",
            source_candidate_event_id="body_state_result:1303:char_a",
            clarity_score=1.0,
            certainty_score=1.0,
        ),
    )

    assert interpretation.interpretation_type == "body_state"
    assert interpretation.risk_level == "medium"


def test_l2_reasoner_offline_path_raises_opportunity_for_recent_world_changes() -> None:
    service, _ = _service(gateway=_LocalGateway())
    snapshot = _snapshot().model_copy(
        update={
            "audible_entities": [],
            "recent_world_changes": ["moved closer to target"],
        }
    )
    interpretation = service.interpret_perceived_event(
        snapshot,
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=1305,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="state_change",
            source_candidate_event_id="state_change:1305:char_a",
            clarity_score=1.0,
            certainty_score=1.0,
        ),
    )

    assert interpretation.opportunity_level == "medium"


def test_l2_reasoner_offline_path_raises_risk_for_recent_constraint_results() -> None:
    service, _ = _service(gateway=_LocalGateway())
    snapshot = _snapshot().model_copy(update={"recent_constraint_results": ["target is too far away"]})
    interpretation = service.interpret_perceived_event(
        snapshot,
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=1304,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="visual_fact/fixed_gaze_on_target",
            source_candidate_event_id="visual_fact:1304:char_a",
            clarity_score=1.0,
            certainty_score=1.0,
        ),
    )

    assert interpretation.risk_level == "medium"


def test_l2_reasoner_offline_path_raises_opportunity_for_last_siming_catalyst() -> None:
    service, _ = _service(gateway=_LocalGateway())
    snapshot = _snapshot().model_copy(update={"last_siming_catalyst": "watch obj_letter", "audible_entities": []})
    interpretation = service.interpret_perceived_event(
        snapshot,
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=1306,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="siming_catalyst",
            source_candidate_event_id="siming:1306:char_a",
            clarity_score=1.0,
            certainty_score=1.0,
        ),
    )

    assert interpretation.opportunity_level == "medium"


def test_l2_reasoner_offline_path_raises_opportunity_for_elevated_vigilance_level() -> None:
    service, _ = _service(gateway=_LocalGateway())
    snapshot = _snapshot().model_copy(update={"vigilance_level": "elevated", "audible_entities": []})
    interpretation = service.interpret_perceived_event(
        snapshot,
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=1307,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="state_change",
            source_candidate_event_id="state_change:1307:char_a",
            clarity_score=1.0,
            certainty_score=1.0,
        ),
    )

    assert interpretation.opportunity_level == "medium"


def test_l2_reasoner_offline_path_raises_ambiguity_for_elevated_distraction_level() -> None:
    service, _ = _service(gateway=_LocalGateway())
    snapshot = _snapshot().model_copy(update={"distraction_level": "elevated", "audible_entities": []})
    interpretation = service.interpret_perceived_event(
        snapshot,
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=1308,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="state_change",
            source_candidate_event_id="state_change:1308:char_a",
            clarity_score=1.0,
            certainty_score=1.0,
        ),
    )

    assert interpretation.ambiguity_level == "high"


def test_l2_reasoner_profile_cache_isolated_from_nested_context_mutation() -> None:
    service, profile_loader = _service()

    first_profile = service._profile_for_actor("char_a")
    first_profile["identity_core"]["canonical_name"] = "Mutated Name"

    second_profile = service._profile_for_actor("char_a")

    assert second_profile["identity_core"]["canonical_name"] == "Lin Yue"
    assert profile_loader.loaded_actor_ids == ["char_a"]
