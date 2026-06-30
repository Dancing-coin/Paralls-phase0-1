import app.main as app_main
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
from app.main import reset_runtime_state
from app.l6.authority_bus.router import handle_envelope_entry
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.ws_protocol import Envelope


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


def _reset_runtime_state_with_local_character_model() -> None:
    reset_runtime_state()
    runtime = CharacterAgentRuntime()
    local_gateway = _LocalGateway()
    runtime._l2 = CharacterAgentL2Service(gateway=local_gateway, profile_registry=runtime._profile_registry)
    runtime._l3 = CharacterAgentL3Service(gateway=local_gateway)
    app_main.character_agent_runtime = runtime
    app_main.siming_event_pipeline._character_dispatch_adapter._runtime = runtime


def test_websocket_targeted_auditory_fact_for_char_c_does_not_emit_autonomous_character_agent_output_in_player_priority_mode() -> None:
    _reset_runtime_state_with_local_character_model()
    received = handle_envelope_entry(
        Envelope(
            message_type="raw_fact_event",
            payload={
                "event_type": "raw_fact_event",
                "fact_family": "auditory_fact",
                "fact_type": "speaker_active",
                "relation_type": "speech_mode_changed",
                "producer_ts": 990,
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "source": {
                    "layer": "L1",
                    "system": "godot.raw_fact_emitter",
                    "actor_id": "char_a",
                    "object_id": "",
                    "environment_id": "",
                },
                "targets": {
                    "actor_id": "char_c",
                    "object_id": "",
                    "environment_id": "",
                },
                "world": {},
                "observability": {"visual": False, "auditory": True, "occluded": False},
                "acoustics": {
                    "loudness_band": "medium",
                    "speech_mode": "normal",
                    "reachability": "clear",
                    "ambient_noise": "quiet",
                },
                "effect_kind": "pulse",
                "subject_key": "",
                "causation_id": "aud:990",
                "correlation_id": "aud:990",
            },
        )
    )

    outputs = [message for message in received if message["message_type"] == "character_agent_output"]

    assert outputs == []


def test_websocket_targeted_auditory_fact_for_char_c_emits_suggestion_packet_in_player_priority_mode() -> None:
    _reset_runtime_state_with_local_character_model()
    received = handle_envelope_entry(
        Envelope(
            message_type="raw_fact_event",
            payload={
                "event_type": "raw_fact_event",
                "fact_family": "auditory_fact",
                "fact_type": "speaker_active",
                "relation_type": "speech_mode_changed",
                "producer_ts": 991,
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "source": {
                    "layer": "L1",
                    "system": "godot.raw_fact_emitter",
                    "actor_id": "char_a",
                    "object_id": "",
                    "environment_id": "",
                },
                "targets": {
                    "actor_id": "char_c",
                    "object_id": "",
                    "environment_id": "",
                },
                "world": {},
                "observability": {"visual": False, "auditory": True, "occluded": False},
                "acoustics": {
                    "loudness_band": "medium",
                    "speech_mode": "normal",
                    "reachability": "clear",
                    "ambient_noise": "quiet",
                },
                "effect_kind": "pulse",
                "subject_key": "",
                "causation_id": "aud:991",
                "correlation_id": "aud:991",
            },
        )
    )

    packets = [message for message in received if message["message_type"] == "character_agent_suggestion"]

    assert packets
    assert packets[0]["payload"]["actor_id"] == "char_c"
    assert packets[0]["payload"]["control_mode"] == "player_priority_assisted"
    assert "recommended_intents" in packets[0]["payload"]
    assert "why_this_now" in packets[0]["payload"]
    assert "urge_vector" in packets[0]["payload"]
    assert "primary_goal" in packets[0]["payload"]
    assert "long_term_goal" in packets[0]["payload"]
    assert "mid_term_strategy" in packets[0]["payload"]
    assert "urgency" in packets[0]["payload"]
    assert "transition_kind" in packets[0]["payload"]
    assert "transition_reason_tags" in packets[0]["payload"]
