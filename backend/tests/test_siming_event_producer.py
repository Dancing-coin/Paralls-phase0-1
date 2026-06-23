import pytest

from app.models.siming_event import SimingOutput
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.siming_event_producer import SimingEventProducer


def make_output(**overrides: object) -> SimingOutput:
    payload = {
        "output_type": "dispatch_intent",
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "causation_id": "visual_fact:300",
        "correlation_id": "visual_fact:300",
        "producer_ts": 304,
        "selected_path": "environment_change_path",
        "intervention_band": "environment_request",
        "payload": {
            "target_environment_id": "env_lamp",
            "request_kind": "attention_catalyst",
        },
    }
    payload.update(overrides)
    return SimingOutput.model_validate(payload)


def test_producer_maps_environment_request_without_claiming_success() -> None:
    bus = InMemoryAuthorityEventBus()
    SimingEventProducer(bus).publish_outputs([make_output()])

    event = bus.list_events(event_type="siming.environment_request")[0]
    assert event.routing.target_ids == ["esm"]
    assert "physical_success" not in event.payload


def test_producer_rejects_forbidden_dispatch_requested_event_family() -> None:
    output = make_output(payload={"event_type": "siming.dispatch_requested"})

    with pytest.raises(ValueError, match="forbidden Siming event family"):
        SimingEventProducer(InMemoryAuthorityEventBus()).publish_outputs([output])


def test_producer_rejects_physical_success_claims() -> None:
    output = make_output(payload={"target_environment_id": "env_lamp", "physical_success": True})

    with pytest.raises(ValueError, match="physical_success"):
        SimingEventProducer(InMemoryAuthorityEventBus()).publish_outputs([output])


def test_producer_maps_character_input_path_to_target_actor_id() -> None:
    bus = InMemoryAuthorityEventBus()
    output = make_output(
        selected_path="character_input_path",
        intervention_band="fact_reveal",
        payload={"target_actor_id": "char_b", "target_object_id": "obj_letter"},
    )

    SimingEventProducer(bus).publish_outputs([output])

    event = bus.list_events(event_type="siming.fact_reveal")[0]
    assert event.routing.target_ids == ["char_b"]


def test_producer_rejects_character_input_path_without_target_actor_id() -> None:
    output = make_output(
        selected_path="character_input_path",
        intervention_band="fact_reveal",
        payload={"target_object_id": "obj_letter"},
    )

    with pytest.raises(ValueError, match="character_input_path requires target_actor_id"):
        SimingEventProducer(InMemoryAuthorityEventBus()).publish_outputs([output])


def test_producer_rejects_character_input_path_with_blank_target_actor_id() -> None:
    output = make_output(
        selected_path="character_input_path",
        intervention_band="fact_reveal",
        payload={"target_actor_id": "   ", "target_object_id": "obj_letter"},
    )

    with pytest.raises(ValueError, match="character_input_path requires target_actor_id"):
        SimingEventProducer(InMemoryAuthorityEventBus()).publish_outputs([output])
