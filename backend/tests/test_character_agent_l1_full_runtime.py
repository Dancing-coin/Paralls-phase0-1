from app.models.character_perceived import CharacterPerceivedEvent
from app.models.self_body_perceived import SelfBodyPerceivedEvent
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
from app.services.character_agent_l1 import CharacterAgentL1Service
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


def _local_runtime() -> CharacterAgentRuntime:
    runtime = CharacterAgentRuntime()
    local_gateway = _LocalGateway()
    runtime._l2 = CharacterAgentL2Service(gateway=local_gateway, profile_registry=runtime._profile_registry)
    runtime._l3 = CharacterAgentL3Service(gateway=local_gateway)
    return runtime


def test_character_agent_l1_tracks_full_private_snapshot_fields() -> None:
    service = CharacterAgentL1Service()
    perceived = CharacterPerceivedEvent(
        actor_id="char_c",
        percept_channel="auditory",
        producer_ts=410,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="auditory_fact/speaker_active",
        source_candidate_event_id="auditory_fact:410:char_c",
        clarity_score=0.72,
        certainty_score=0.58,
    )

    snapshot = service.apply_character_perceived_event(perceived)

    assert snapshot.actor_id == "char_c"
    assert snapshot.audible_entities == ["auditory_fact/speaker_active"]
    assert snapshot.visible_entities == []
    assert snapshot.unresolved_signals == []
    assert snapshot.active_anomalies == []
    assert snapshot.current_attention_targets == []
    assert snapshot.short_horizon_social_presence == []
    assert snapshot.local_spatial_confidence_map == {}
    assert snapshot.recent_world_changes == []
    assert snapshot.recent_constraint_results == []
    assert snapshot.body_state_hints == []
    assert snapshot.last_siming_catalyst is None
    assert snapshot.vigilance_level == "baseline"
    assert snapshot.distraction_level == "baseline"
    assert snapshot.bias_tags == []
    assert snapshot.clarity_score == 0.72
    assert snapshot.certainty_score == 0.58


def test_character_agent_l1_tracks_new_modality_and_quality_fields() -> None:
    service = CharacterAgentL1Service()
    perceived = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="olfactory",
        producer_ts=419,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="olfactory_fact/smoke_trace",
        source_candidate_event_id="olfactory_fact:419:char_a",
        clarity_score=0.62,
        certainty_score=0.41,
    )

    snapshot = service.apply_character_perceived_event(perceived)

    assert snapshot.olfactory_entities == ["olfactory_fact/smoke_trace"]
    assert snapshot.partial_observations == ["olfactory_fact/smoke_trace"]
    assert snapshot.distorted_details == ["olfactory_fact/smoke_trace"]
    assert snapshot.missed_details == ["olfactory_fact/smoke_trace"]
    assert snapshot.salience_tags == ["olfactory:olfactory_fact/smoke_trace"]
    assert snapshot.attention_pressure == 0.62


def test_character_agent_l1_keeps_char_c_inside_the_runtime_species() -> None:
    runtime = _local_runtime()
    event = CharacterPerceivedEvent(
        actor_id="char_c",
        percept_channel="visual",
        producer_ts=411,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:411:char_c",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    commands = runtime.ingest_character_perceived_event(event)
    snapshot = runtime.get_private_snapshot("char_c")

    assert runtime.supports_actor("char_c")
    assert snapshot is not None
    assert snapshot.actor_id == "char_c"
    assert commands == []


def test_character_agent_l1_keeps_char_c_self_body_inputs_inside_runtime_species() -> None:
    runtime = _local_runtime()
    event = SelfBodyPerceivedEvent(
        actor_id="char_c",
        body_state_class="interaction_strain",
        producer_ts=412,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="body_state_result/interaction_strain=engaged",
        source_body_result_id="body_result:char_c:412",
    )

    commands = runtime.ingest_self_body_perceived_event(event)
    snapshot = runtime.get_private_snapshot("char_c")

    assert runtime.supports_actor("char_c")
    assert snapshot is not None
    assert snapshot.actor_id == "char_c"
    assert commands == []


def test_character_agent_l1_tracks_target_attention_social_presence_and_spatial_confidence() -> None:
    service = CharacterAgentL1Service()
    perceived = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="spatial",
        producer_ts=413,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="spatial_access_fact/actor_approached_actor",
        source_candidate_event_id="spatial_access_fact:413:char_a",
        source_actor_id="char_c",
        target_actor_id="char_b",
        distance_m=2.4,
        clarity_score=0.84,
        certainty_score=0.67,
    )

    snapshot = service.apply_character_perceived_event(perceived)

    assert snapshot.unresolved_signals == ["spatial_access_fact/actor_approached_actor"]
    assert snapshot.attention_targets == ["char_b"]
    assert snapshot.current_attention_targets == ["char_b"]
    assert snapshot.short_horizon_social_presence == ["char_b"]
    assert snapshot.local_spatial_confidence_map == {"char_b": 0.67}


def test_character_agent_l1_siming_catalyst_raises_vigilance_level() -> None:
    service = CharacterAgentL1Service()

    snapshot = service.apply_siming_output(
        {
            "target_actor_id": "char_a",
            "target_environment_id": "env_lamp",
            "presentation_hint": "watch env_lamp",
            "producer_ts": 418,
            "causation_id": "siming:418",
            "correlation_id": "siming:418",
        }
    )

    assert snapshot.last_siming_catalyst == "watch env_lamp"
    assert snapshot.attention_targets == ["env_lamp"]
    assert snapshot.current_attention_targets == ["env_lamp"]
    assert snapshot.vigilance_level == "elevated"


def test_runtime_settlement_and_dialogue_writeback_update_private_snapshot_history() -> None:
    runtime = _local_runtime()
    event = CharacterPerceivedEvent(
        actor_id="char_b",
        percept_channel="visual",
        producer_ts=414,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:414:char_b",
        clarity_score=1.0,
        certainty_score=1.0,
    )
    runtime.ingest_character_perceived_event(event)

    runtime.record_settlement_result(
        actor_id="char_b",
        producer_ts=415,
        payload={
            "result_type": "action_resolution_result",
            "change_summary": "moved closer to target",
        },
    )
    runtime.record_settlement_result(
        actor_id="char_b",
        producer_ts=416,
        payload={
            "result_type": "constraint_state_result",
            "constraint_summary": "target is too far away",
        },
    )
    runtime.record_dialogue_response(
        actor_id="char_b",
        producer_ts=417,
        payload={
            "output_type": "dialogue_response",
            "summary": "I will keep watch.",
        },
    )

    snapshot = runtime.get_private_snapshot("char_b")

    assert snapshot is not None
    assert snapshot.recent_world_changes == ["moved closer to target", "dialogue_response:I will keep watch."]
    assert snapshot.recent_constraint_results == ["target is too far away"]
