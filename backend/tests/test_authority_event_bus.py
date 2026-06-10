from app.models.authority_event import AuthorityEvent
from app.services.authority_event_bus import InMemoryAuthorityEventBus

from tests.test_authority_event import valid_event_dict


def make_event(event_id: str, event_type: str = "visual_fact_event") -> AuthorityEvent:
    payload = valid_event_dict()
    payload["event_id"] = event_id
    payload["event_type"] = event_type
    return AuthorityEvent.model_validate(payload)


def test_in_memory_bus_preserves_publish_order() -> None:
    bus = InMemoryAuthorityEventBus()
    bus.publish(make_event("evt_1"))
    bus.publish(make_event("evt_2", "esm_result_event"))

    assert [event.event_id for event in bus.list_events()] == ["evt_1", "evt_2"]


def test_in_memory_bus_returns_deep_copies() -> None:
    bus = InMemoryAuthorityEventBus()
    bus.publish(make_event("evt_1"))

    first_read = bus.list_events()[0]
    first_read.payload["fact_type"] = "mutated"

    second_read = bus.list_events()[0]
    assert second_read.payload["fact_type"] == "light_level_drop"


def test_in_memory_bus_filters_by_room_and_event_type() -> None:
    bus = InMemoryAuthorityEventBus()
    bus.publish(make_event("evt_1", "visual_fact_event"))
    bus.publish(make_event("evt_2", "esm_result_event"))

    assert [event.event_id for event in bus.list_events(event_type="esm_result_event")] == ["evt_2"]
    assert [event.event_id for event in bus.list_events(room_id="room_demo")] == ["evt_1", "evt_2"]


def test_in_memory_bus_invokes_exact_event_type_subscribers() -> None:
    bus = InMemoryAuthorityEventBus()
    received: list[str] = []
    bus.subscribe("visual_fact_event", lambda event: received.append(event.event_id))

    bus.publish(make_event("evt_1", "visual_fact_event"))
    bus.publish(make_event("evt_2", "esm_result_event"))

    assert received == ["evt_1"]
