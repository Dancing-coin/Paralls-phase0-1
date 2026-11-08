from app.models.fact_type import FACT_TYPE_REGISTRY, FactType
from app.models.authority_event import AuthorityEvent
from app.services.siming_event_consumer import SimingEventConsumer


def test_fact_type_registry_maps_gameplay_schema_events_to_domains():
    ref = FACT_TYPE_REGISTRY.from_event_type("gameplay.inventory.item_instantiated@1")
    assert ref is not None
    assert ref.value == "gameplay.inventory.item_instantiated@1"
    assert FACT_TYPE_REGISTRY.domain_for(ref) == "inventory"
    assert FactType.from_event_type("world_fact_event") is FactType.WORLD_FACT


def test_fact_type_registry_rejects_unregistered_gameplay_event():
    assert FACT_TYPE_REGISTRY.from_event_type("gameplay.inventory.future_unlisted_event") is None


def test_siming_event_consumer_filters_through_fact_type_registry():
    consumer = SimingEventConsumer()
    assert consumer.handle_event(AuthorityEvent.model_validate({
        "event_id": "evt:fact-type",
        "event_type": "world_fact_event",
        "producer_ts": 1,
        "room_id": "room",
        "scene_id": "scene",
        "zone_id": "zone",
        "source": {"layer": "world", "system": "test", "actor_id": ""},
        "routing": {"audience_mode": "broadcast", "routing_mode": "domain", "target_ids": []},
        "priority": "p2",
        "durability": "replayable",
        "causation_id": "cause",
        "correlation_id": "corr",
        "payload": {},
    }))
