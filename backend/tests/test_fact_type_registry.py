from app.models.fact_type import FACT_TYPE_REGISTRY, FactType


def test_fact_type_registry_maps_gameplay_schema_events_to_domains():
    ref = FACT_TYPE_REGISTRY.from_event_type("gameplay.inventory.item_instantiated@1")
    assert ref is not None
    assert ref.value == "gameplay.inventory.item_instantiated@1"
    assert FACT_TYPE_REGISTRY.domain_for(ref) == "inventory"
    assert FactType.from_event_type("world_fact_event") is FactType.WORLD_FACT


def test_fact_type_registry_rejects_unregistered_gameplay_event():
    assert FACT_TYPE_REGISTRY.from_event_type("gameplay.inventory.future_unlisted_event") is None
