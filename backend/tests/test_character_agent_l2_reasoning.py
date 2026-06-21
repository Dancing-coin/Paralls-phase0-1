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


def _snapshot() -> CharacterPrivateWorldSnapshot:
    return CharacterPrivateWorldSnapshot(
        actor_id="char_c",
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
    service = CharacterAgentL2Service()
    event = CharacterPerceivedEvent(
        actor_id="char_c",
        percept_channel="auditory",
        producer_ts=1301,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:1301:char_c",
        clarity_score=0.82,
        certainty_score=0.61,
    )

    run_request = service.prepare_reasoning_request(
        snapshot=_snapshot(),
        event=event,
        memory_bundle={
            "working_memory": [{"event_id": "evt:1300"}],
            "episodic_memories": [{"summary": "char_a spoke nearby"}],
            "relational_memories": [{"entity_id": "char_a", "value": "guarded"}],
        },
        control_mode="player_priority_assisted",
    )

    assert run_request["task_kind"] == "l2_reasoning"
    assert run_request["context"]["actor_id"] == "char_c"
    assert run_request["context"]["control_mode"] == "player_priority_assisted"
    assert run_request["context"]["memory"]["episodic_memories"][0]["summary"] == "char_a spoke nearby"
    assert run_request["context"]["snapshot"]["last_siming_catalyst"] == "watch obj_letter"
    assert run_request["context"]["working_memory_state"] == {}
    assert run_request["route"]["route_mode"] == "online_default"


def test_l2_reasoner_maps_structured_gateway_output_into_interpretation() -> None:
    service = CharacterAgentL2Service()

    interpretation = service.map_reasoning_output(
        actor_id="char_c",
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

    assert interpretation.actor_id == "char_c"
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
    service = CharacterAgentL2Service(gateway=gateway)

    interpretation = service.interpret_perceived_event(
        _snapshot(),
        CharacterPerceivedEvent(
            actor_id="char_c",
            percept_channel="auditory",
            producer_ts=1301,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="auditory_fact/speaker_active",
            source_candidate_event_id="auditory_fact:1301:char_c",
            clarity_score=0.82,
            certainty_score=0.61,
        ),
    )

    assert gateway.requests
    assert gateway.requests[0]["task_kind"] == "l2_reasoning"
    assert interpretation.interpreted_summary == "char_a may be speaking nearby"
    assert interpretation.attention_target == "char_a"


def test_l2_reasoner_offline_path_raises_risk_for_active_anomalies() -> None:
    service = CharacterAgentL2Service()
    snapshot = _snapshot().model_copy(update={"active_anomalies": ["olfactory_fact/smoke_density_rise"]})
    interpretation = service.interpret_perceived_event(
        snapshot,
        CharacterPerceivedEvent(
            actor_id="char_c",
            percept_channel="olfactory",
            producer_ts=1302,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="olfactory_fact/smoke_density_rise",
            source_candidate_event_id="olfactory_fact:1302:char_c",
            clarity_score=0.66,
            certainty_score=0.53,
        ),
    )

    assert interpretation.risk_level == "medium"
    assert interpretation.ambiguity_level == "medium"


def test_l2_reasoner_offline_path_treats_body_state_hints_as_body_state_interpretation() -> None:
    service = CharacterAgentL2Service()
    snapshot = _snapshot().model_copy(
        update={
            "body_state_hints": ["interaction_strain:body_state_result/interaction_strain=engaged"],
            "audible_entities": [],
        }
    )
    interpretation = service.interpret_perceived_event(
        snapshot,
        CharacterPerceivedEvent(
            actor_id="char_c",
            percept_channel="visual",
            producer_ts=1303,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="body_state_result/interaction_strain=engaged",
            source_candidate_event_id="body_state_result:1303:char_c",
            clarity_score=1.0,
            certainty_score=1.0,
        ),
    )

    assert interpretation.interpretation_type == "body_state"
    assert interpretation.risk_level == "medium"


def test_l2_reasoner_offline_path_raises_opportunity_for_recent_world_changes() -> None:
    service = CharacterAgentL2Service()
    snapshot = _snapshot().model_copy(
        update={
            "audible_entities": [],
            "recent_world_changes": ["moved closer to target"],
        }
    )
    interpretation = service.interpret_perceived_event(
        snapshot,
        CharacterPerceivedEvent(
            actor_id="char_c",
            percept_channel="visual",
            producer_ts=1305,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="state_change",
            source_candidate_event_id="state_change:1305:char_c",
            clarity_score=1.0,
            certainty_score=1.0,
        ),
    )

    assert interpretation.opportunity_level == "medium"


def test_l2_reasoner_offline_path_raises_risk_for_recent_constraint_results() -> None:
    service = CharacterAgentL2Service()
    snapshot = _snapshot().model_copy(update={"recent_constraint_results": ["target is too far away"]})
    interpretation = service.interpret_perceived_event(
        snapshot,
        CharacterPerceivedEvent(
            actor_id="char_c",
            percept_channel="visual",
            producer_ts=1304,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="visual_fact/fixed_gaze_on_target",
            source_candidate_event_id="visual_fact:1304:char_c",
            clarity_score=1.0,
            certainty_score=1.0,
        ),
    )

    assert interpretation.risk_level == "medium"


def test_l2_reasoner_offline_path_raises_opportunity_for_last_siming_catalyst() -> None:
    service = CharacterAgentL2Service()
    snapshot = _snapshot().model_copy(update={"last_siming_catalyst": "watch obj_letter", "audible_entities": []})
    interpretation = service.interpret_perceived_event(
        snapshot,
        CharacterPerceivedEvent(
            actor_id="char_c",
            percept_channel="visual",
            producer_ts=1306,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="siming_catalyst",
            source_candidate_event_id="siming:1306:char_c",
            clarity_score=1.0,
            certainty_score=1.0,
        ),
    )

    assert interpretation.opportunity_level == "medium"


def test_l2_reasoner_offline_path_raises_opportunity_for_elevated_vigilance_level() -> None:
    service = CharacterAgentL2Service()
    snapshot = _snapshot().model_copy(update={"vigilance_level": "elevated", "audible_entities": []})
    interpretation = service.interpret_perceived_event(
        snapshot,
        CharacterPerceivedEvent(
            actor_id="char_c",
            percept_channel="visual",
            producer_ts=1307,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="state_change",
            source_candidate_event_id="state_change:1307:char_c",
            clarity_score=1.0,
            certainty_score=1.0,
        ),
    )

    assert interpretation.opportunity_level == "medium"


def test_l2_reasoner_offline_path_raises_ambiguity_for_elevated_distraction_level() -> None:
    service = CharacterAgentL2Service()
    snapshot = _snapshot().model_copy(update={"distraction_level": "elevated", "audible_entities": []})
    interpretation = service.interpret_perceived_event(
        snapshot,
        CharacterPerceivedEvent(
            actor_id="char_c",
            percept_channel="visual",
            producer_ts=1308,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="state_change",
            source_candidate_event_id="state_change:1308:char_c",
            clarity_score=1.0,
            certainty_score=1.0,
        ),
    )

    assert interpretation.ambiguity_level == "medium"
