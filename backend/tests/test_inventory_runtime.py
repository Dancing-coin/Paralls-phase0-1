from __future__ import annotations

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry, InventoryProjector, InventoryRuntimeError, ItemDefinition


ACTOR = "actor:inventory"


def _service() -> tuple[GameplayEventStore, InventoryDefinitionRegistry, InventoryAuthorityService]:
    store = GameplayEventStore()
    registry = InventoryDefinitionRegistry()
    registry.register_item(ItemDefinition("item:stone", "1", 2, 1))
    return store, registry, InventoryAuthorityService(store=store, registry=registry)


def _create(service: InventoryAuthorityService, container_id: str, slots: int = 2, sealed: bool = False) -> None:
    result = service.create_container(command_id=f"cmd:{container_id}", actor_ref=ACTOR, spec=ContainerSpec(container_id, 10, 10, slots, sealed), idempotency_key=container_id, causation_id="cause", correlation_id="corr")
    assert result.committed


def test_instantiation_and_move_are_event_derived_and_atomic() -> None:
    store, registry, service = _service()
    _create(service, "container:bag")
    _create(service, "container:hand")
    result = service.instantiate(command_id="cmd:item", actor_ref=ACTOR, item_id="item:stone:1", definition_id="item:stone", quantity=1, container_id="container:bag", idempotency_key="item", causation_id="cause", correlation_id="corr")
    assert result.committed
    moved = service.move(command_id="cmd:move", actor_ref=ACTOR, item_id="item:stone:1", from_container_id="container:bag", to_container_id="container:hand", idempotency_key="move", causation_id="cause", correlation_id="corr")
    assert moved.committed
    projection = InventoryProjector(registry).rebuild(ACTOR, store.read_events())
    assert projection.locations == {"item:stone:1": "container:hand"}
    assert [event.event_type for event in store.read_events()][-1] == "gameplay.inventory.item_moved"


def test_generic_inventory_exact_retry_rejects_corrupt_receipt_without_writes() -> None:
    store, _, service = _service()
    _create(service, "container:bag")
    _create(service, "container:hand")
    assert service.instantiate(
        command_id="cmd:item", actor_ref=ACTOR, item_id="item:stone:1", definition_id="item:stone",
        quantity=1, container_id="container:bag", idempotency_key="item", causation_id="cause",
        correlation_id="corr",
    ).committed
    first = service.move(
        command_id="cmd:move", actor_ref=ACTOR, item_id="item:stone:1", from_container_id="container:bag",
        to_container_id="container:hand", idempotency_key="move", causation_id="cause", correlation_id="corr",
    )
    assert first.committed
    exact = service.move(
        command_id="cmd:move", actor_ref=ACTOR, item_id="item:stone:1", from_container_id="container:bag",
        to_container_id="container:hand", idempotency_key="move", causation_id="cause", correlation_id="corr",
    )
    assert exact.committed and exact.idempotency_status == "duplicate_replayed"
    key = (service._PRINCIPAL, f"{ACTOR}:move")
    store._idempotency_results[key] = first.model_copy(
        update={"committed_event_ids": [*first.committed_event_ids, "missing:event"]}, deep=True
    )
    before = store.export_snapshot()
    duplicate = service.move(
        command_id="cmd:move", actor_ref=ACTOR, item_id="item:stone:1", from_container_id="container:bag",
        to_container_id="container:hand", idempotency_key="move", causation_id="cause", correlation_id="corr",
    )
    assert not duplicate.committed and duplicate.failure is not None
    assert duplicate.failure.error_code == "inventory_idempotency_receipt_invalid"
    assert store.export_snapshot() == before


def test_sealed_and_capacity_fail_before_event_append() -> None:
    store, _, service = _service()
    _create(service, "container:sealed", sealed=True)
    before = store.read_events()
    with pytest.raises(InventoryRuntimeError, match="inventory_access_denied"):
        service.instantiate(command_id="cmd:sealed", actor_ref=ACTOR, item_id="item:stone:1", definition_id="item:stone", quantity=1, container_id="container:sealed", idempotency_key="sealed", causation_id="cause", correlation_id="corr")
    assert store.read_events() == before
    _create(service, "container:tiny", slots=1)
    service.instantiate(command_id="cmd:first", actor_ref=ACTOR, item_id="item:stone:1", definition_id="item:stone", quantity=1, container_id="container:tiny", idempotency_key="first", causation_id="cause", correlation_id="corr")
    event_count = len(store.read_events())
    with pytest.raises(InventoryRuntimeError, match="inventory_capacity_exceeded"):
        service.instantiate(command_id="cmd:second", actor_ref=ACTOR, item_id="item:stone:2", definition_id="item:stone", quantity=1, container_id="container:tiny", idempotency_key="second", causation_id="cause", correlation_id="corr")
    assert len(store.read_events()) == event_count


def test_exact_container_retry_replays_without_event_append() -> None:
    store, _, service = _service()
    _create(service, "container:bag")
    event_count = len(store.read_events())
    duplicate = service.create_container(
        command_id="cmd:container:bag", actor_ref=ACTOR,
        spec=ContainerSpec("container:bag", 10, 10, 2, False),
        idempotency_key="container:bag", causation_id="cause", correlation_id="corr",
    )
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == event_count


def test_encumbrance_is_a_read_projection_of_carried_container_contents() -> None:
    store, registry, service = _service()
    _create(service, "container:bag")
    service.instantiate(command_id="cmd:item", actor_ref=ACTOR, item_id="item:stone:1", definition_id="item:stone", quantity=2, container_id="container:bag", idempotency_key="item", causation_id="cause", correlation_id="corr")
    projection = InventoryProjector(registry).rebuild(ACTOR, store.read_events())
    encumbrance = InventoryProjector(registry).rebuild_encumbrance(projection, carrier_ref=ACTOR, carried_container_ids=("container:bag",))
    assert encumbrance.carried_weight == 4
    assert encumbrance.carried_volume == 2
    assert encumbrance.source_breakdown == {"item:stone:1": 4}
