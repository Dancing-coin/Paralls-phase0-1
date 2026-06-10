import app.main as main
from app.models.visual_fact import VisualFactEvent
from app.ws_protocol import Envelope


def test_visual_fact_light_drop_returns_projected_siming_authority_event() -> None:
    main.reset_runtime_state()

    outbound = main._handle_envelope(
        Envelope(
            message_type="visual_fact_event",
            payload=VisualFactEvent(
                actor_id="char_c",
                room_id="room_demo",
                scene_id="scene_demo",
                zone_id="zone_focus",
                producer_ts=300,
                fact_type="light_level_drop",
                relation_type="environment_light_drop",
                target_environment_id="env_lamp",
            ).model_dump(),
        )
    )

    projected = [
        message
        for message in outbound
        if message.get("message_type") == "authority_event"
        and message.get("payload", {}).get("event_type") == "siming.visual_observability_request"
    ]
    assert len(projected) == 1
    payload = projected[0]["payload"]
    assert payload["payload"]["established_fact_id"].startswith("visual_fact:300:char_c:light_level_drop")
    assert payload["payload"]["presentation_hint"] == "increase observability for established light change"


def test_non_visual_siming_events_are_not_returned_to_websocket() -> None:
    main.reset_runtime_state()

    outbound = main._handle_envelope(
        Envelope(
            message_type="visual_fact_event",
            payload=VisualFactEvent(
                actor_id="char_c",
                room_id="room_demo",
                scene_id="scene_demo",
                zone_id="zone_focus",
                producer_ts=301,
                fact_type="actor_looks_at_object",
                relation_type="fixed_gaze_on_target",
                target_object_id="obj_letter",
            ).model_dump(),
        )
    )

    assert all(message.get("message_type") != "authority_event" for message in outbound)
