from copy import deepcopy

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
        }
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
    service, _ = _service()
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
    assert interpretation.ambiguity_level == "medium"


def test_l2_reasoner_offline_path_treats_body_state_hints_as_body_state_interpretation() -> None:
    service, _ = _service()
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
    service, _ = _service()
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
    service, _ = _service()
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
    service, _ = _service()
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
    service, _ = _service()
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
    service, _ = _service()
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

    assert interpretation.ambiguity_level == "medium"


def test_l2_reasoner_profile_cache_isolated_from_nested_context_mutation() -> None:
    service, profile_loader = _service()

    first_profile = service._profile_for_actor("char_a")
    first_profile["identity_core"]["canonical_name"] = "Mutated Name"

    second_profile = service._profile_for_actor("char_a")

    assert second_profile["identity_core"]["canonical_name"] == "Lin Yue"
    assert profile_loader.loaded_actor_ids == ["char_a"]
