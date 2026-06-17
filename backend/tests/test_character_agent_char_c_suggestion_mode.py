from app.main import reset_runtime_state
from app.l6.authority_bus.router import handle_envelope_entry
from app.ws_protocol import Envelope


def test_websocket_targeted_auditory_fact_for_char_c_does_not_emit_autonomous_character_agent_output_in_player_priority_mode() -> None:
    reset_runtime_state()
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
    reset_runtime_state()
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
