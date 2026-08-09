from __future__ import annotations

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry, InventoryProjector, InventoryReservation, InventoryRuntimeError, ItemDefinition


ACTOR = "actor:inventory"
STREAM_ID = f"gameplay:inventory:{ACTOR}"


def _service() -> tuple[GameplayEventStore, InventoryDefinitionRegistry, InventoryAuthorityService]:
    store = GameplayEventStore()
    registry = InventoryDefinitionRegistry()
    registry.register_item(ItemDefinition("item:stone", "1", 2, 1))
    return store, registry, InventoryAuthorityService(store=store, registry=registry)


def _create(service: InventoryAuthorityService, container_id: str) -> None:
    result = service.create_container(
        command_id=f"cmd:{container_id}",
        actor_ref=ACTOR,
        spec=ContainerSpec(container_id, 10, 10, 2),
        idempotency_key=container_id,
        causation_id="cause",
        correlation_id="corr",
    )
    assert result.committed


def _append(store: GameplayEventStore, *, command_id: str, event_type: str, payload: dict[str, object]) -> None:
    result = store.append_batch(
        {
            "transaction_id": f"tx:{command_id}",
            "command_id": command_id,
            "expected_stream_revisions": {STREAM_ID: store.get_stream_head(STREAM_ID)},
            "pinned_revisions": {},
            "events": [
                {
                    "event_id": f"evt:{command_id}:inventory:1",
                    "event_type": event_type,
                    "schema_version": 1,
                    "stream_id": STREAM_ID,
                    "stream_revision": 0,
                    "global_sequence": 0,
                    "transaction_id": f"tx:{command_id}",
                    "command_id": command_id,
                    "causation_id": command_id,
                    "correlation_id": "corr:inventory",
                    "visibility_policy": "authority_only",
                    "payload": payload,
                }
            ],
            "idempotency_record": {
                "principal_ref": "inventory-test-authority",
                "idempotency_key": command_id,
                "payload_digest": f"sha256:{command_id}",
            },
            "outbox_entries": [],
            "result_digest": f"sha256:{command_id}",
            "projection_refresh_hints": [],
        }
    )
    assert result.committed is True


def test_reservation_lifecycle_rebuilds_remaining_quantity_and_is_idempotent() -> None:
    store, registry, service = _service()
    _create(service, "container:bag")
    service.instantiate(
        command_id="cmd:item",
        actor_ref=ACTOR,
        item_id="item:stone:1",
        definition_id="item:stone",
        quantity=5,
        container_id="container:bag",
        idempotency_key="item",
        causation_id="cause",
        correlation_id="corr",
    )

    reserve = service.reserve_item(
        command_id="cmd:reserve",
        actor_ref=ACTOR,
        item_id="item:stone:1",
        reservation_ref="reservation:flour",
        quantity=3,
        idempotency_key="reserve",
        causation_id="cause",
        correlation_id="corr",
    )
    assert reserve.committed
    replayed = service.reserve_item(
        command_id="cmd:reserve",
        actor_ref=ACTOR,
        item_id="item:stone:1",
        reservation_ref="reservation:flour",
        quantity=3,
        idempotency_key="reserve",
        causation_id="cause",
        correlation_id="corr",
    )
    assert replayed.idempotency_status == "duplicate_replayed"

    projection = InventoryProjector(registry).rebuild(ACTOR, store.read_events())
    item = projection.items["item:stone:1"]
    assert item.reserved_quantity == 3
    assert item.remaining_quantity == 2
    assert projection.reservations["reservation:flour"] == InventoryReservation("reservation:flour", "item:stone:1", 3, "evt:cmd:reserve:inventory:1")

    duplicate_before = len(store.read_events())
    with pytest.raises(InventoryRuntimeError, match="inventory_reservation_duplicate"):
        service.reserve_item(
            command_id="cmd:duplicate",
            actor_ref=ACTOR,
            item_id="item:stone:1",
            reservation_ref="reservation:flour",
            quantity=1,
            idempotency_key="duplicate",
            causation_id="cause",
            correlation_id="corr",
        )
    assert len(store.read_events()) == duplicate_before

    release = service.release_reservation(
        command_id="cmd:release",
        actor_ref=ACTOR,
        reservation_ref="reservation:flour",
        idempotency_key="release",
        causation_id="cause",
        correlation_id="corr",
    )
    assert release.committed
    released = InventoryProjector(registry).rebuild(ACTOR, store.read_events())
    assert released.items["item:stone:1"].remaining_quantity == 5
    assert released.items["item:stone:1"].reserved_quantity == 0
    assert released.reservations == {}

    consume_reserve = service.reserve_item(
        command_id="cmd:reserve:consume",
        actor_ref=ACTOR,
        item_id="item:stone:1",
        reservation_ref="reservation:consume",
        quantity=2,
        idempotency_key="reserve:consume",
        causation_id="cause",
        correlation_id="corr",
    )
    assert consume_reserve.committed
    consumed = service.consume_reservation(
        command_id="cmd:consume",
        actor_ref=ACTOR,
        reservation_ref="reservation:consume",
        idempotency_key="consume",
        causation_id="cause",
        correlation_id="corr",
    )
    assert consumed.committed
    final = InventoryProjector(registry).rebuild(ACTOR, store.read_events())
    assert final.items["item:stone:1"].quantity == 3
    assert final.items["item:stone:1"].remaining_quantity == 3
    assert final.reservations == {}

    with pytest.raises(InventoryRuntimeError, match="inventory_reservation_unknown"):
        service.consume_reservation(
            command_id="cmd:consume:again",
            actor_ref=ACTOR,
            reservation_ref="reservation:consume",
            idempotency_key="consume:again",
            causation_id="cause",
            correlation_id="corr",
        )


def test_reservation_rejects_missing_location_and_insufficient_quantity_without_writes() -> None:
    store, _, service = _service()
    _create(service, "container:bag")
    _append(
        store,
        command_id="cmd:unplaced",
        event_type="gameplay.inventory.item_instantiated",
        payload={"actor_ref": ACTOR, "item_id": "item:stone:unplaced", "definition_id": "item:stone", "quantity": 1},
    )
    before = store.read_events()
    with pytest.raises(InventoryRuntimeError, match="inventory_reservation_source_invalid"):
        service.reserve_item(
            command_id="cmd:reserve:unplaced",
            actor_ref=ACTOR,
            item_id="item:stone:unplaced",
            reservation_ref="reservation:unplaced",
            quantity=1,
            idempotency_key="reserve:unplaced",
            causation_id="cause",
            correlation_id="corr",
        )
    assert store.read_events() == before

    service.instantiate(
        command_id="cmd:item",
        actor_ref=ACTOR,
        item_id="item:stone:full",
        definition_id="item:stone",
        quantity=2,
        container_id="container:bag",
        idempotency_key="item:full",
        causation_id="cause",
        correlation_id="corr",
    )
    before = store.read_events()
    with pytest.raises(InventoryRuntimeError, match="inventory_reservation_insufficient"):
        service.reserve_item(
            command_id="cmd:reserve:too-much",
            actor_ref=ACTOR,
            item_id="item:stone:full",
            reservation_ref="reservation:too-much",
            quantity=3,
            idempotency_key="reserve:too-much",
            causation_id="cause",
            correlation_id="corr",
        )
    assert store.read_events() == before


def test_release_rejects_unknown_reservation_without_writes() -> None:
    store, _, service = _service()
    _create(service, "container:bag")
    service.instantiate(
        command_id="cmd:item",
        actor_ref=ACTOR,
        item_id="item:stone:1",
        definition_id="item:stone",
        quantity=1,
        container_id="container:bag",
        idempotency_key="item",
        causation_id="cause",
        correlation_id="corr",
    )
    before = store.read_events()
    with pytest.raises(InventoryRuntimeError, match="inventory_reservation_unknown"):
        service.release_reservation(
            command_id="cmd:release:missing",
            actor_ref=ACTOR,
            reservation_ref="reservation:missing",
            idempotency_key="release:missing",
            causation_id="cause",
            correlation_id="corr",
        )
    assert store.read_events() == before


def test_output_receipt_materializes_the_produced_item_in_inventory_projection() -> None:
    store, registry, service = _service()
    _create(service, "container:bag")
    registry.register_item(ItemDefinition("item:bread", "1", 1, 1))
    result = service.record_output_receipt(
        command_id="cmd:output",
        actor_ref=ACTOR,
        source_ref="run:bakery:1",
        item_ref="bread",
        item_id="item:bread:1",
        definition_id="item:bread",
        container_id="container:bag",
        quantity=1,
        idempotency_key="output",
        causation_id="cause",
        correlation_id="corr",
    )
    assert result.committed
    projection = InventoryProjector(registry).rebuild(ACTOR, store.read_events())
    assert projection.items["item:bread:1"].quantity == 1
    assert projection.locations["item:bread:1"] == "container:bag"
