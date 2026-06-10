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
        "causation_id": "evt_visual_1",
        "correlation_id": "visual_fact:100",
        "producer_ts": 101,
        "selected_path": "visual_fact_path",
        "intervention_band": "fact_reveal",
        "payload": {"established_fact_id": "evt_visual_1"},
    }
    payload.update(overrides)
    return SimingOutput.model_validate(payload)


def test_producer_maps_visual_fact_path_to_observability_event() -> None:
    bus = InMemoryAuthorityEventBus()
    producer = SimingEventProducer(bus)

    producer.publish_outputs([make_output()])

    events = bus.list_events()
    assert events[0].event_type == "siming.visual_observability_request"
    assert events[0].source.system == "siming.dispatcher"
    assert events[0].payload["established_fact_id"] == "evt_visual_1"


def test_producer_rejects_visual_observability_without_established_fact_id() -> None:
    bus = InMemoryAuthorityEventBus()
    producer = SimingEventProducer(bus)

    with pytest.raises(ValueError, match="established_fact_id"):
        producer.publish_outputs([make_output(payload={})])


def test_producer_maps_no_action_to_no_action_recorded() -> None:
    bus = InMemoryAuthorityEventBus()
    producer = SimingEventProducer(bus)
    output = make_output(
        output_type="no_action",
        selected_path="no_action",
        intervention_band="none",
        payload={"reason": "no eligible intervention"},
    )

    producer.publish_outputs([output])

    assert bus.list_events()[0].event_type == "siming.no_action_recorded"


def test_producer_never_publishes_internal_dispatch_requested_label() -> None:
    bus = InMemoryAuthorityEventBus()
    producer = SimingEventProducer(bus)
    output = make_output(payload={"event_type": "siming.dispatch_requested", "established_fact_id": "evt_visual_1"})

    producer.publish_outputs([output])

    assert all(event.event_type != "siming.dispatch_requested" for event in bus.list_events())
