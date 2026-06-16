import pytest
from pydantic import ValidationError

from app.models.authority_event import AuthorityEvent
from app.services.authority_event_bus import InMemoryAuthorityEventBus


def make_authority_event(**overrides: object) -> AuthorityEvent:
    payload = {
        "event_id": "evt:1",
        "event_type": "visual_fact_event",
        "producer_ts": 100,
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "source": {"layer": "L1", "system": "visual_fact", "actor_id": "char_c"},
        "routing": {"audience_mode": "room", "routing_mode": "event_type", "target_ids": ["siming"]},
        "priority": "p2",
        "ttl": 5000,
        "durability": "replayable",
        "causation_id": "visual_fact:100",
        "correlation_id": "visual_fact:100",
        "payload": {"fact_type": "light_level_drop"},
    }
    payload.update(overrides)
    return AuthorityEvent.model_validate(payload)


def test_authority_event_rejects_forbidden_public_envelope_fields() -> None:
    with pytest.raises(ValidationError, match="forbidden authority envelope"):
        make_authority_event(world_ts=100)


def test_authority_event_rejects_sim_tick_ts_public_envelope_field() -> None:
    with pytest.raises(ValidationError, match="forbidden authority envelope"):
        make_authority_event(sim_tick_ts=301)


def test_in_memory_bus_publishes_deep_copies_to_subscribers_and_store() -> None:
    bus = InMemoryAuthorityEventBus()
    seen: list[AuthorityEvent] = []
    bus.subscribe("visual_fact_event", seen.append)
    event = make_authority_event()

    bus.publish(event)
    event.payload["fact_type"] = "mutated"
    seen[0].payload["fact_type"] = "mutated_again"

    stored = bus.list_events()
    assert len(seen) == 1
    assert len(stored) == 1
    assert stored[0].payload["fact_type"] == "light_level_drop"


def test_in_memory_bus_filters_events_by_room_and_type() -> None:
    bus = InMemoryAuthorityEventBus()
    bus.publish(make_authority_event(event_id="evt:1", room_id="room_demo", event_type="visual_fact_event"))
    bus.publish(make_authority_event(event_id="evt:2", room_id="room_other", event_type="visual_fact_event"))
    bus.publish(make_authority_event(event_id="evt:3", room_id="room_demo", event_type="esm_result_event"))

    filtered = bus.list_events(room_id="room_demo", event_type="visual_fact_event")

    assert [event.event_id for event in filtered] == ["evt:1"]
