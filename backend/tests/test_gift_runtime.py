from __future__ import annotations

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.gift_runtime import GiftAuthorityService, GiftProjector, GiftRuntimeError
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry, InventoryProjector, ItemDefinition
from app.gameplay.ownership_runtime import OwnershipAuthorityService, OwnershipProjector


DONOR = "actor:donor"
RECIPIENT = "actor:recipient"
ASSET = "asset:field-notes"
ITEM = "item:field-notes:1"


def _setup(*, recipient_slots: int = 2) -> tuple[GameplayEventStore, InventoryDefinitionRegistry, GiftAuthorityService]:
    store = GameplayEventStore()
    registry = InventoryDefinitionRegistry()
    registry.register_item(ItemDefinition("item:field-notes", "1", 1, 1))
    inventory = InventoryAuthorityService(store=store, registry=registry)
    inventory.create_container(command_id="cmd:donor-container", actor_ref=DONOR, spec=ContainerSpec("container:donor", 10, 10, 2), idempotency_key="donor-container", causation_id="cause", correlation_id="corr")
    inventory.create_container(command_id="cmd:recipient-container", actor_ref=RECIPIENT, spec=ContainerSpec("container:recipient", 10, 10, recipient_slots), idempotency_key="recipient-container", causation_id="cause", correlation_id="corr")
    inventory.instantiate(command_id="cmd:item", actor_ref=DONOR, item_id=ITEM, definition_id="item:field-notes", quantity=1, container_id="container:donor", idempotency_key="item", causation_id="cause", correlation_id="corr")
    OwnershipAuthorityService(store=store).grant_initial_title(command_id="cmd:title", asset_ref=ASSET, holder_ref=DONOR, right_id="right:field-notes", idempotency_key="title", causation_id="cause", correlation_id="corr")
    return store, registry, GiftAuthorityService(store=store, inventory_registry=registry)


def _gift(service: GiftAuthorityService, *, command_id: str = "cmd:gift", idempotency_key: str = "gift"):
    return service.gift_asset(
        command_id=command_id,
        donor_ref=DONOR,
        recipient_ref=RECIPIENT,
        asset_ref=ASSET,
        right_id="right:field-notes",
        item_id=ITEM,
        source_container_id="container:donor",
        destination_container_id="container:recipient",
        idempotency_key=idempotency_key,
        causation_id="cause",
        correlation_id="corr",
    )


def test_gift_atomically_moves_item_title_and_zero_consideration_record() -> None:
    store, registry, service = _setup()
    result = _gift(service)
    assert result.committed
    transaction = store.read_transactions()[-1]
    assert len(transaction.events) == 4
    assert [event.event_type for event in transaction.events] == [
        "gameplay.inventory.item_transferred_out",
        "gameplay.inventory.item_transferred_in",
        "gameplay.ownership.right_transferred",
        "gameplay.commerce.gift_settled",
    ]
    assert InventoryProjector(registry).rebuild(DONOR, store.read_events()).locations == {}
    assert InventoryProjector(registry).rebuild(RECIPIENT, store.read_events()).locations == {ITEM: "container:recipient"}
    assert OwnershipProjector().rebuild(store.read_events()).rights["right:field-notes"].holder_ref == RECIPIENT
    record = GiftProjector().rebuild(store.read_events()).gifts["gift:cmd:gift"]
    assert record.settlement_transaction_id == result.transaction_id
    assert record.consideration_amount == 0


def test_wrong_title_holder_or_full_destination_writes_nothing() -> None:
    store, _, service = _setup()
    OwnershipAuthorityService(store=store).transfer_title(command_id="cmd:title-away", asset_ref=ASSET, right_id="right:field-notes", from_holder_ref=DONOR, to_holder_ref="actor:other", idempotency_key="title-away", causation_id="cause", correlation_id="corr")
    before = store.read_events()
    with pytest.raises(GiftRuntimeError, match="ownership_right_holder_mismatch"):
        _gift(service, command_id="cmd:wrong-title", idempotency_key="wrong-title")
    assert store.read_events() == before

    full_store, registry, full_service = _setup(recipient_slots=1)
    InventoryAuthorityService(store=full_store, registry=registry).instantiate(command_id="cmd:recipient-junk", actor_ref=RECIPIENT, item_id="item:recipient-junk", definition_id="item:field-notes", quantity=1, container_id="container:recipient", idempotency_key="recipient-junk", causation_id="cause", correlation_id="corr")
    full_before = full_store.read_events()
    with pytest.raises(GiftRuntimeError, match="inventory_capacity_exceeded"):
        _gift(full_service, command_id="cmd:full", idempotency_key="full")
    assert full_store.read_events() == full_before


def test_gift_retry_returns_original_transaction_without_second_transfer() -> None:
    store, _, service = _setup()
    first = _gift(service)
    replay = _gift(service)
    assert first.committed and replay.committed
    assert replay.idempotency_status == "duplicate_replayed"
    assert len([event for event in store.read_events() if event.event_type == "gameplay.ownership.right_transferred"]) == 1
