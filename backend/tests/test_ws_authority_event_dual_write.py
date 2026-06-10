import app.main as main
from app.models.player_input import InteractIntent
from app.models.visual_fact import VisualFactEvent
from app.ws_protocol import Envelope


def test_visual_fact_handler_dual_writes_authority_and_siming_events_without_changing_outbound_messages() -> None:
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

    assert outbound[0]["message_type"] == "ack"
    event_types = [event.event_type for event in main.authority_event_bus.list_events()]
    assert "visual_fact_event" in event_types
    assert "siming.fairness_snapshot" in event_types
    assert "siming.visual_observability_request" in event_types
    assert main.siming_audit_writer.find_by_correlation(room_id="room_demo", correlation_id="visual_fact:300")


def test_failed_interaction_dual_writes_constraint_state_event() -> None:
    main.reset_runtime_state()
    main._handle_envelope(
        Envelope(
            message_type="player_input",
            payload={
                "player_id": "p1",
                "room_id": "room_demo",
                "actor_id": "char_c",
                "intent_type": "move_intent",
                "producer_ts": 455,
                "move_mode": "locomotion",
                "target_point": [0.0, 0.0, 20.0],
            },
        )
    )

    outbound = main._handle_envelope(
        Envelope(
            message_type="player_input",
            payload=InteractIntent(
                player_id="p1",
                room_id="room_demo",
                actor_id="char_c",
                intent_type="interact_intent",
                producer_ts=456,
                target_object_id="obj_letter",
                interaction_type="inspect",
            ).model_dump(),
        )
    )

    assert outbound[1]["message_type"] == "action_request"
    assert outbound[2]["message_type"] == "world_result"
    event_types = [event.event_type for event in main.authority_event_bus.list_events()]
    assert "constraint_state_event" in event_types
    assert any(
        audit.status == "esm_rejected"
        for audit in main.siming_audit_writer.find_by_correlation(room_id="room_demo", correlation_id="interact:456")
    )
