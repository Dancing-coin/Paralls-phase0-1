from __future__ import annotations

import pytest

from app.gameplay.economy_runtime import EconomyAuthorityService, EconomyProjector
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.fixed_offer_purchase import FixedOfferAuthorityService, FixedOfferProjector, PurchaseRuntimeError
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry, InventoryProjector, ItemDefinition
from app.gameplay.ownership_runtime import OwnershipAuthorityService, OwnershipProjector


BUYER = "actor:buyer"
SELLER = "actor:seller"
ASSET = "asset:brass-compass"
ITEM = "item:brass-compass:1"
OFFER = "offer:brass-compass"


def _setup(*, buyer_balance: int = 10, buyer_slots: int = 3) -> tuple[GameplayEventStore, InventoryDefinitionRegistry, FixedOfferAuthorityService]:
    store = GameplayEventStore()
    registry = InventoryDefinitionRegistry()
    registry.register_item(ItemDefinition("item:brass-compass", "1", 1, 1))
    inventory = InventoryAuthorityService(store=store, registry=registry)
    inventory.create_container(command_id="cmd:seller-container", actor_ref=SELLER, spec=ContainerSpec("container:seller", 10, 10, 3), idempotency_key="seller-container", causation_id="cause", correlation_id="corr")
    inventory.create_container(command_id="cmd:buyer-container", actor_ref=BUYER, spec=ContainerSpec("container:buyer", 10, 10, buyer_slots), idempotency_key="buyer-container", causation_id="cause", correlation_id="corr")
    inventory.instantiate(command_id="cmd:item", actor_ref=SELLER, item_id=ITEM, definition_id="item:brass-compass", quantity=1, container_id="container:seller", idempotency_key="item", causation_id="cause", correlation_id="corr")
    ownership = OwnershipAuthorityService(store=store)
    ownership.grant_initial_title(command_id="cmd:title", asset_ref=ASSET, holder_ref=SELLER, right_id="right:brass-compass", idempotency_key="title", causation_id="cause", correlation_id="corr")
    economy = EconomyAuthorityService(store=store)
    economy.open_account(command_id="cmd:buyer-account", account_id="account:buyer", owner_ref=BUYER, currency_ref="coin", initial_balance=buyer_balance, idempotency_key="buyer-account", causation_id="cause", correlation_id="corr")
    economy.open_account(command_id="cmd:seller-account", account_id="account:seller", owner_ref=SELLER, currency_ref="coin", initial_balance=0, idempotency_key="seller-account", causation_id="cause", correlation_id="corr")
    service = FixedOfferAuthorityService(store=store, inventory_registry=registry)
    assert service.publish_offer(command_id="cmd:offer", offer_id=OFFER, seller_ref=SELLER, asset_ref=ASSET, right_id="right:brass-compass", item_id=ITEM, source_container_id="container:seller", price_amount=4, currency_ref="coin", idempotency_key="offer", causation_id="cause", correlation_id="corr").committed
    return store, registry, service


def _purchase(service: FixedOfferAuthorityService, *, command_id: str = "cmd:purchase", idempotency_key: str = "purchase"):
    offer = service.offer_projection().offers[OFFER]
    return service.purchase(
        command_id=command_id,
        offer_id=OFFER,
        expected_offer_revision=offer.offer_revision,
        buyer_ref=BUYER,
        buyer_account_id="account:buyer",
        seller_account_id="account:seller",
        destination_container_id="container:buyer",
        accepted_amount=4,
        accepted_currency_ref="coin",
        idempotency_key=idempotency_key,
        causation_id="cause",
        correlation_id="corr",
    )


def test_fixed_offer_purchase_settles_money_item_title_and_audit_in_one_batch() -> None:
    store, registry, service = _setup()
    before = len(store.read_events())
    result = _purchase(service)
    assert result.committed
    transaction = store.read_transactions()[-1]
    assert len(transaction.events) == 7
    assert {event.stream_id for event in transaction.events} == {"gameplay:economy", "gameplay:ownership", f"gameplay:inventory:{SELLER}", f"gameplay:inventory:{BUYER}", "gameplay:commerce"}
    assert len(store.read_events()) == before + 7
    assert EconomyProjector().rebuild(store.read_events()).balances == {"account:buyer": 6, "account:seller": 4}
    assert OwnershipProjector().rebuild(store.read_events()).rights["right:brass-compass"].holder_ref == BUYER
    assert InventoryProjector(registry).rebuild(SELLER, store.read_events()).locations == {}
    assert InventoryProjector(registry).rebuild(BUYER, store.read_events()).locations == {ITEM: "container:buyer"}
    commerce = FixedOfferProjector().rebuild(store.read_events())
    assert commerce.offers[OFFER].consumed
    record = commerce.transactions["purchase:cmd:purchase"]
    assert record.amount == 4
    assert record.settlement_transaction_id == result.transaction_id


def test_insufficient_funds_changes_no_domain_stream() -> None:
    store, _, service = _setup(buyer_balance=3)
    before = store.read_events()
    with pytest.raises(PurchaseRuntimeError, match="economy_insufficient_funds"):
        _purchase(service)
    assert store.read_events() == before


def test_stale_offer_or_wrong_seller_title_changes_nothing() -> None:
    store, _, service = _setup()
    before = store.read_events()
    with pytest.raises(PurchaseRuntimeError, match="economy_offer_stale"):
        service.purchase(command_id="cmd:stale", offer_id=OFFER, expected_offer_revision=999, buyer_ref=BUYER, buyer_account_id="account:buyer", seller_account_id="account:seller", destination_container_id="container:buyer", accepted_amount=4, accepted_currency_ref="coin", idempotency_key="stale", causation_id="cause", correlation_id="corr")
    assert store.read_events() == before

    OwnershipAuthorityService(store=store).transfer_title(command_id="cmd:other-title", asset_ref=ASSET, right_id="right:brass-compass", from_holder_ref=SELLER, to_holder_ref="actor:other", idempotency_key="other-title", causation_id="cause", correlation_id="corr")
    after_transfer = store.read_events()
    with pytest.raises(PurchaseRuntimeError, match="ownership_right_holder_mismatch"):
        _purchase(service, command_id="cmd:bad-title", idempotency_key="bad-title")
    assert store.read_events() == after_transfer


def test_full_destination_container_changes_no_domain_stream() -> None:
    store, registry, service = _setup(buyer_slots=1)
    InventoryAuthorityService(store=store, registry=registry).instantiate(
        command_id="cmd:buyer-junk",
        actor_ref=BUYER,
        item_id="item:buyer-junk",
        definition_id="item:brass-compass",
        quantity=1,
        container_id="container:buyer",
        idempotency_key="buyer-junk",
        causation_id="cause",
        correlation_id="corr",
    )
    before = store.read_events()
    with pytest.raises(PurchaseRuntimeError, match="inventory_capacity_exceeded"):
        _purchase(service, command_id="cmd:full", idempotency_key="full")
    assert store.read_events() == before


def test_purchase_retry_returns_original_result_without_second_debit_or_transfer() -> None:
    store, _, service = _setup()
    first = _purchase(service)
    replay = _purchase(service)
    assert first.committed and replay.committed
    assert replay.idempotency_status == "duplicate_replayed"
    assert EconomyProjector().rebuild(store.read_events()).balances == {"account:buyer": 6, "account:seller": 4}
    assert len([event for event in store.read_events() if event.event_type == "gameplay.ownership.right_transferred"]) == 1
