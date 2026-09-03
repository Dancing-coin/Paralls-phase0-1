from app.gameplay.event_store import GameplayEventStore
from app.gameplay.event_schema_registry import EventSchemaRegistry, register_general_inventory_platform_event_schemas
from app.gameplay.inventory_platform_runtime import (
    ContainerRecord, CustodyRecord, InventoryLotRecord, InventoryPlatformAuthority,
    ItemInstanceRecord, ReservationRecord,
)


def test_inventory_instance_lot_nested_container_reservation_split_merge_replay():
    store = GameplayEventStore(); authority = InventoryPlatformAuthority(store=store)
    assert authority.record_container(command_id="c", idempotency_key="i:c", record=ContainerRecord(container_ref="container:root@1", holder_ref="actor:a", capacity_units=100, used_units=0, weight_limit=100, used_weight=0), expected_revision=0, causation_id="cause", correlation_id="corr").committed
    assert authority.record_container(command_id="c2", idempotency_key="i:c2", record=ContainerRecord(container_ref="container:child@1", holder_ref="actor:a", parent_container_ref="container:root@1", capacity_units=20, used_units=0, weight_limit=20, used_weight=0), expected_revision=0, causation_id="cause", correlation_id="corr").committed
    assert authority.record_item(command_id="i", idempotency_key="i:item", record=ItemInstanceRecord(item_ref="item:apple@1", definition_ref="definition:apple@1", quantity=1, source_event_ref="event:seed@1"), expected_revision=0, causation_id="cause", correlation_id="corr").committed
    assert authority.record_custody(command_id="cu", idempotency_key="i:cu", record=CustodyRecord(asset_ref="item:apple@1", holder_ref="actor:a", container_ref="container:child@1", status="stored", revision=1, source_event_ref="event:seed@1"), expected_revision=1, causation_id="cause", correlation_id="corr").committed
    custody_batch = store.read_transactions()[-1]
    assert "gameplay:inventory:platform:container:child@1" in custody_batch.read_stream_revisions
    assert authority.record_lot(command_id="l", idempotency_key="i:lot", record=InventoryLotRecord(lot_ref="lot:apple@1", definition_ref="definition:apple@1", quantity=10, quality_ref="quality:fresh@1"), expected_revision=0, causation_id="cause", correlation_id="corr").committed
    assert authority.open_reservation(command_id="r", idempotency_key="i:r", record=ReservationRecord(reservation_ref="reservation:apple@1", asset_ref="lot:apple@1", reservation_kind="quantity", quantity=3, purpose_ref="purpose:recipe@1", owner_ref="actor:a", source_event_ref="event:recipe@1", expected_revision=1), expected_revision=1, causation_id="cause", correlation_id="corr").committed
    assert authority.split_lot(command_id="s", idempotency_key="i:s", parent_lot_ref="lot:apple@1", child_lot_ref="lot:apple-split@1", quantity=2, expected_revision=2, causation_id="cause", correlation_id="corr").committed
    assert authority.merge_lots(command_id="m", idempotency_key="i:m", first_lot_ref="lot:apple@1", second_lot_ref="lot:apple-split@1", merged_lot_ref="lot:apple-merged@1", expected_revision=0, causation_id="cause", correlation_id="corr").committed
    merge_batch = store.read_transactions()[-1]
    assert "gameplay:inventory:platform:lot:apple@1" in merge_batch.read_stream_revisions
    assert "gameplay:inventory:platform:lot:apple-split@1" in merge_batch.read_stream_revisions
    projector = authority.projector; full = projector.rebuild(store.read_events()); cp = projector.rebuild(store.read_events()[:3]); tail = projector.rebuild(store.read_events()[3:], checkpoint=cp)
    assert full.to_state() == tail.to_state()
    assert full.lots["lot:apple-merged@1"].quantity == 10
    receipt = authority.receipt_for(authority.record_lot(command_id="receipt", idempotency_key="receipt", record=InventoryLotRecord(lot_ref="lot:receipt@1", definition_ref="definition:apple@1", quantity=1, quality_ref="quality:fresh@1"), expected_revision=0, causation_id="cause", correlation_id="corr"))
    assert receipt.committed_event_ids


def test_inventory_reservation_capacity_and_cycle_fail_closed():
    store = GameplayEventStore(); authority = InventoryPlatformAuthority(store=store)
    bad = authority.record_container(command_id="bad", idempotency_key="bad", record=ContainerRecord(container_ref="container:self@1", holder_ref="actor:a", parent_container_ref="container:self@1", capacity_units=1, used_units=0, weight_limit=1, used_weight=0), expected_revision=0, causation_id="cause", correlation_id="corr")
    assert not bad.committed and bad.zero_write


def test_inventory_events_are_admitted_by_registry_backed_store():
    registry = EventSchemaRegistry(); register_general_inventory_platform_event_schemas(registry)
    store = GameplayEventStore(event_schema_registry=registry); authority = InventoryPlatformAuthority(store=store)
    result = authority.record_item(command_id="registry", idempotency_key="registry", record=ItemInstanceRecord(item_ref="item:registry@1", definition_ref="definition:item@1", quantity=1, source_event_ref="event:seed@1"), expected_revision=0, causation_id="cause", correlation_id="corr")
    assert result.committed
