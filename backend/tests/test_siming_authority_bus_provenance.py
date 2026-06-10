from pathlib import Path

import app.main as main
from app.ws_protocol import Envelope


def _messages_of_type(messages: list[dict[str, object]], message_type: str) -> list[dict[str, object]]:
    return [message for message in messages if message.get("message_type") == message_type]


def test_visual_fact_siming_output_is_projected_from_authority_event() -> None:
    main.reset_runtime_state()

    outbound = main._handle_envelope(
        Envelope(
            message_type="visual_fact_event",
            payload={
                "actor_id": "char_c",
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "producer_ts": 151,
                "fact_type": "light_level_drop",
                "relation_type": "environment_light_drop",
                "target_environment_id": "env_lamp",
            },
        )
    )

    siming_outputs = _messages_of_type(outbound, "siming_output")
    visual_output = next(
        output
        for output in siming_outputs
        if output["payload"]["authority_event_type"] == "siming.visual_observability_request"  # type: ignore[index]
    )
    authority_event_id = visual_output["payload"]["authority_event_id"]  # type: ignore[index]
    bus_events = main.authority_event_bus.list_events(room_id="room_demo")
    bus_event_by_id = {event.event_id: event for event in bus_events}

    assert "visual_fact:151:char_c:light_level_drop" in bus_event_by_id
    assert authority_event_id in bus_event_by_id
    projected_event = bus_event_by_id[authority_event_id]
    assert projected_event.event_type == "siming.visual_observability_request"
    assert projected_event.source.system == "siming.dispatcher"
    assert visual_output["payload"]["target_environment_id"] == projected_event.payload["target_environment_id"]  # type: ignore[index]
    assert visual_output["payload"]["causation_id"] == projected_event.causation_id  # type: ignore[index]
    assert visual_output["payload"]["correlation_id"] == projected_event.correlation_id  # type: ignore[index]


def test_interact_success_siming_outputs_are_projected_from_authority_bus() -> None:
    main.reset_runtime_state()

    outbound = main._handle_envelope(
        Envelope(
            message_type="player_input",
            payload={
                "player_id": "p1",
                "room_id": "room_demo",
                "actor_id": "char_c",
                "intent_type": "interact_intent",
                "producer_ts": 456,
                "target_object_id": "obj_letter",
                "interaction_type": "inspect",
            },
        )
    )

    siming_outputs = _messages_of_type(outbound, "siming_output")
    bus_events = main.authority_event_bus.list_events(room_id="room_demo")
    bus_event_by_id = {event.event_id: event for event in bus_events}

    assert {event.event_type for event in bus_events} >= {"esm_result_event", "conversation_resolution_event", "siming.fact_reveal"}
    assert siming_outputs
    for output in siming_outputs:
        payload = output["payload"]
        authority_event_id = payload["authority_event_id"]  # type: ignore[index]
        assert authority_event_id in bus_event_by_id
        authority_event = bus_event_by_id[authority_event_id]
        assert payload["authority_event_type"] == authority_event.event_type  # type: ignore[index]
        assert payload["causation_id"] == authority_event.causation_id  # type: ignore[index]
        assert payload["correlation_id"] == authority_event.correlation_id  # type: ignore[index]


def test_runtime_mainline_does_not_call_legacy_siming_service() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    runtime_sources = [
        backend_root / "app" / "main.py",
        backend_root / "app" / "services" / "fact_handlers" / "visual_fact_handler.py",
    ]

    forbidden_tokens = [
        "SimingService",
        "siming_service",
        "evaluate_world_event",
        "evaluate_candidate_relationship",
        "evaluate_visual_fact",
        "context.siming_service",
    ]
    combined_source = "\n".join(path.read_text(encoding="utf-8") for path in runtime_sources)

    for token in forbidden_tokens:
        assert token not in combined_source
