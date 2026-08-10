from __future__ import annotations

from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import (
    ContainerSpec,
    InventoryAuthorityService,
    InventoryDefinitionRegistry,
    ItemDefinition,
)
from app.gameplay.phase4_commerce import (
    DeterministicClearing,
    DynamicCommerceAuthority,
    DynamicQuote,
    QuoteOrder,
)


def test_clearing_rebuilds_current_owner_facts_instead_of_trusting_a_caller_witness() -> None:
    """P4A accepts only a candidate that matches owner-persisted facts."""
    store = GameplayEventStore()
    registry = InventoryDefinitionRegistry()
    registry.register_item(ItemDefinition("item:flour", "v1", 1, 1))
    inventory = InventoryAuthorityService(store=store, registry=registry)
    inventory.create_container(
        command_id="p4a:container", actor_ref="organization:supplier",
        spec=ContainerSpec("container:supplier", 100, 100, 10),
        idempotency_key="p4a:container", causation_id="test", correlation_id="test",
    )
    inventory.instantiate(
        command_id="p4a:flour", actor_ref="organization:supplier", item_id="item:flour:lot-1",
        definition_id="item:flour", quantity=6, container_id="container:supplier",
        idempotency_key="p4a:flour", causation_id="test", correlation_id="test",
    )
    inventory.reserve_item(
        command_id="p4a:supply", actor_ref="organization:supplier", item_id="item:flour:lot-1",
        reservation_ref="reservation:supplier:flour", quantity=4,
        idempotency_key="p4a:supply", causation_id="test", correlation_id="test",
    )
    inventory.reserve_commerce_capacity(
        command_id="p4a:capacity", actor_ref="organization:supplier",
        capacity_reservation_ref="capacity:supplier:delivery", available_quantity=4,
        idempotency_key="p4a:capacity", causation_id="test", correlation_id="test",
    )
    inventory.reserve_commerce_capacity(
        command_id="p4a:buyer-capacity", actor_ref="organization:bakery-a",
        capacity_reservation_ref="capacity:bakery-a:receive", available_quantity=4,
        idempotency_key="p4a:buyer-capacity", causation_id="test", correlation_id="test",
    )

    economy = EconomyAuthorityService(store=store)
    economy.open_account(
        command_id="p4a:buyer-account", account_id="account:bakery-a",
        owner_ref="organization:bakery-a", currency_ref="currency:local", initial_balance=40,
        idempotency_key="p4a:buyer-account", causation_id="test", correlation_id="test",
    )
    economy.reserve_budget(
        command_id="p4a:buyer-budget", reservation_ref="reservation:bakery-a:budget",
        account_id="account:bakery-a", amount_minor=32,
        idempotency_key="p4a:buyer-budget", causation_id="test", correlation_id="test",
    )

    vector = {
        "gameplay:economy": 4,
        "gameplay:inventory:organization:supplier": 5,
        "gameplay:inventory:organization:bakery-a": 1,
    }
    quote = DynamicQuote(
        quote_ref="quote:flour:a", issuer_ref="organization:supplier", item_ref="item:flour",
        quality_ref="quality:standard", side="sell", quantity_limit=4, unit_price_minor=7,
        currency_ref="currency:local", version=1, valid_from_tick=1, valid_until_tick=10,
        policy_revision="policy:commerce:v1", reservation_ref="reservation:supplier:flour",
        inventory_custody_ref="custody:supplier:flour", capacity_reservation_ref="capacity:supplier:delivery",
        delivery_policy_ref="policy:delivery:standard", cancellation_policy_ref="policy:cancel:standard",
        public_digest="sha256:quote:flour:a",
    )
    order = QuoteOrder(
        order_ref="order:bakery:a", issuer_ref="organization:bakery-a", item_ref="item:flour",
        quality_ref="quality:standard", side="buy", quantity=4, limit_price_minor=8,
        currency_ref="currency:local", created_tick=2, valid_from_tick=1, valid_until_tick=10,
        policy_revision="policy:commerce:v1", reservation_ref="reservation:bakery-a:budget",
        inventory_custody_ref="custody:bakery-a:incoming", capacity_reservation_ref="capacity:bakery-a:receive",
        delivery_policy_ref="policy:delivery:standard", cancellation_policy_ref="policy:cancel:standard",
        public_digest="sha256:order:bakery:a", revision_vector=vector,
    )
    economy.publish_dynamic_quote(
        command_id="p4a:quote", quote_payload=quote.model_dump(mode="json"),
        idempotency_key="p4a:quote", causation_id="test", correlation_id="test",
    )
    economy.submit_dynamic_order(
        command_id="p4a:order", order_payload=order.model_dump(mode="json"),
        idempotency_key="p4a:order", causation_id="test", correlation_id="test",
    )

    candidate = DeterministicClearing().clear(quotes=(quote,), orders=(order,), tick=2).candidates[0]
    result = DynamicCommerceAuthority(store=store, inventory_registry=registry).commit_candidate(
        candidate, tick=2, idempotency_key="p4a:owner-backed",
    )

    assert result.committed
    assert result.settlement_plan is not None
    assert store.read_events()[-1].event_type == "gameplay.economy.clearing_revalidated"
