from __future__ import annotations

from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry, ItemDefinition
from app.gameplay.phase4_commerce import DeterministicClearing, DynamicCommerceAuthority, DynamicQuote, QuoteOrder


def _quote(*, quote_ref: str = "quote:flour:a", price: int = 7, quantity: int = 4) -> DynamicQuote:
    return DynamicQuote(
        quote_ref=quote_ref, issuer_ref="organization:supplier", item_ref="item:flour", quality_ref="quality:standard",
        side="sell", quantity_limit=quantity, unit_price_minor=price, currency_ref="currency:local", version=1,
        valid_from_tick=1, valid_until_tick=10, policy_revision="policy:commerce:v1",
        reservation_ref="reservation:supplier:flour", inventory_custody_ref="custody:supplier:flour",
        capacity_reservation_ref="capacity:supplier:delivery", delivery_policy_ref="policy:delivery:standard",
        cancellation_policy_ref="policy:cancel:standard", public_digest=f"sha256:{quote_ref}",
    )


def _order(*, order_ref: str = "order:bakery:a", quantity: int = 4, limit: int = 8, vector: dict[str, int] | None = None) -> QuoteOrder:
    return QuoteOrder(
        order_ref=order_ref, issuer_ref="organization:bakery-a", item_ref="item:flour", quality_ref="quality:standard",
        side="buy", quantity=quantity, limit_price_minor=limit, currency_ref="currency:local", created_tick=2,
        valid_from_tick=1, valid_until_tick=10, policy_revision="policy:commerce:v1",
        reservation_ref="reservation:bakery-a:budget", inventory_custody_ref="custody:bakery-a:incoming",
        capacity_reservation_ref="capacity:bakery-a:receive", delivery_policy_ref="policy:delivery:standard",
        cancellation_policy_ref="policy:cancel:standard", public_digest=f"sha256:{order_ref}",
        revision_vector=vector or {"gameplay:economy": 4, "gameplay:inventory:organization:supplier": 5, "gameplay:inventory:organization:bakery-a": 1},
    )


def _owner_backed_candidate(*, quote: DynamicQuote | None = None, order: QuoteOrder | None = None):
    store = GameplayEventStore()
    registry = InventoryDefinitionRegistry()
    registry.register_item(ItemDefinition("item:flour", "v1", 1, 1))
    inventory = InventoryAuthorityService(store=store, registry=registry)
    inventory.create_container(command_id="p4a:container", actor_ref="organization:supplier", spec=ContainerSpec("container:supplier", 100, 100, 10), idempotency_key="p4a:container", causation_id="test", correlation_id="test")
    inventory.instantiate(command_id="p4a:flour", actor_ref="organization:supplier", item_id="item:flour:lot-1", definition_id="item:flour", quantity=6, container_id="container:supplier", idempotency_key="p4a:flour", causation_id="test", correlation_id="test")
    inventory.reserve_item(command_id="p4a:supply", actor_ref="organization:supplier", item_id="item:flour:lot-1", reservation_ref="reservation:supplier:flour", quantity=4, idempotency_key="p4a:supply", causation_id="test", correlation_id="test")
    inventory.reserve_commerce_capacity(command_id="p4a:capacity", actor_ref="organization:supplier", capacity_reservation_ref="capacity:supplier:delivery", available_quantity=4, idempotency_key="p4a:capacity", causation_id="test", correlation_id="test")
    inventory.reserve_commerce_capacity(command_id="p4a:buyer-capacity", actor_ref="organization:bakery-a", capacity_reservation_ref="capacity:bakery-a:receive", available_quantity=4, idempotency_key="p4a:buyer-capacity", causation_id="test", correlation_id="test")
    economy = EconomyAuthorityService(store=store)
    economy.open_account(command_id="p4a:account", account_id="account:bakery-a", owner_ref="organization:bakery-a", currency_ref="currency:local", initial_balance=40, idempotency_key="p4a:account", causation_id="test", correlation_id="test")
    economy.reserve_budget(command_id="p4a:budget", reservation_ref="reservation:bakery-a:budget", account_id="account:bakery-a", amount_minor=32, idempotency_key="p4a:budget", causation_id="test", correlation_id="test")
    quote = quote or _quote()
    order = order or _order()
    economy.publish_dynamic_quote(command_id="p4a:quote", quote_payload=quote.model_dump(mode="json"), idempotency_key="p4a:quote", causation_id="test", correlation_id="test")
    economy.submit_dynamic_order(command_id="p4a:order", order_payload=order.model_dump(mode="json"), idempotency_key="p4a:order", causation_id="test", correlation_id="test")
    candidate = DeterministicClearing().clear(quotes=(quote,), orders=(order,), tick=2).candidates[0]
    return store, registry, inventory, economy, quote, order, candidate


def test_quote_contract_pins_public_terms_and_rejects_float_price() -> None:
    assert _quote().public_digest == "sha256:quote:flour:a"
    try:
        _quote(price=7.5)  # type: ignore[arg-type]
    except Exception as exc:
        assert "unit_price_minor" in str(exc)
    else:
        raise AssertionError("fixed-point quote price must reject floats")


def test_clearing_is_deterministic_and_returns_partial_reject_explanation() -> None:
    result = DeterministicClearing().clear(
        quotes=(_quote(quote_ref="quote:flour:b", quantity=2), _quote(quote_ref="quote:flour:a", quantity=3)),
        orders=(_order(order_ref="order:bakery:b"), _order(order_ref="order:bakery:a")), tick=2,
    )
    assert [(item.quote_ref, item.order_ref, item.quantity) for item in result.candidates] == [
        ("quote:flour:a", "order:bakery:a", 3), ("quote:flour:b", "order:bakery:a", 1), ("quote:flour:b", "order:bakery:b", 1),
    ]
    assert result.rejections == (("order:bakery:b", "quantity_exhausted"),)
    assert result.explanation_digest.startswith("sha256:")


def test_expired_cancelled_and_stale_policy_quotes_do_not_clear() -> None:
    assert DeterministicClearing().clear(quotes=(_quote().model_copy(update={"status": "cancelled"}),), orders=(_order(),), tick=2).candidates == ()
    stale_policy = DeterministicClearing().clear(quotes=(_quote().model_copy(update={"policy_revision": "policy:commerce:v2"}),), orders=(_order(),), tick=2)
    assert stale_policy.rejections == (("order:bakery:a", "policy_revision_stale"),)


def test_candidate_commit_requires_owner_facts_and_is_zero_write_when_absent() -> None:
    candidate = DeterministicClearing().clear(quotes=(_quote(),), orders=(_order(),), tick=2).candidates[0]
    registry = InventoryDefinitionRegistry()
    registry.register_item(ItemDefinition("item:flour", "v1", 1, 1))
    store = GameplayEventStore()
    outcome = DynamicCommerceAuthority(store=store, inventory_registry=registry).commit_candidate(candidate, tick=2, idempotency_key="p4a:no-owner-facts")
    assert outcome.zero_write
    assert outcome.error_code == "quote_owner_fact_missing"
    assert store.read_events() == []


def test_authority_rebuilds_owner_facts_and_commits_one_atomic_receipt() -> None:
    store, registry, _, _, _, _, candidate = _owner_backed_candidate()
    outcome = DynamicCommerceAuthority(store=store, inventory_registry=registry).commit_candidate(candidate, tick=2, idempotency_key="p4a:one")
    assert outcome.committed and outcome.receipt is not None and outcome.settlement_plan is not None
    assert outcome.receipt.committed_event_ids[-1].startswith("event:p4a:clear:")
    assert outcome.revision_vector == outcome.receipt.resulting_stream_revisions


def test_current_owner_quote_cancellation_and_stock_race_reject_without_a_write() -> None:
    store, registry, inventory, economy, quote, _, candidate = _owner_backed_candidate()
    economy.publish_dynamic_quote(command_id="p4a:cancel", quote_payload=quote.model_copy(update={"version": 2, "status": "cancelled"}).model_dump(mode="json"), idempotency_key="p4a:cancel", causation_id="test", correlation_id="test")
    cancelled = DynamicCommerceAuthority(store=store, inventory_registry=registry).commit_candidate(candidate, tick=2, idempotency_key="p4a:cancel-attempt")
    assert cancelled.zero_write and cancelled.error_code == "quote_version_stale"
    store, registry, inventory, _, _, _, candidate = _owner_backed_candidate()
    inventory.reserve_item(command_id="p4a:stock-race", actor_ref="organization:supplier", item_id="item:flour:lot-1", reservation_ref="reservation:raced", quantity=2, idempotency_key="p4a:stock-race", causation_id="test", correlation_id="test")
    raced = DynamicCommerceAuthority(store=store, inventory_registry=registry).commit_candidate(candidate, tick=2, idempotency_key="p4a:stock-race-commit")
    assert raced.zero_write and raced.error_code == "revision_conflict"


def test_idempotent_retry_returns_original_receipt_before_revalidation() -> None:
    store, registry, _, _, _, _, candidate = _owner_backed_candidate()
    authority = DynamicCommerceAuthority(store=store, inventory_registry=registry)
    first = authority.commit_candidate(candidate, tick=2, idempotency_key="p4a:retry")
    replay = authority.commit_candidate(candidate, tick=2, idempotency_key="p4a:retry")
    assert first.committed and replay.committed
    assert replay.receipt is not None and replay.receipt.idempotency_status == "duplicate_replayed"


def test_owner_revision_race_between_revalidation_and_append_is_zero_write() -> None:
    store, registry, _, _, _, _, candidate = _owner_backed_candidate()
    original_append = store.append_batch

    def advance_inventory_then_append(batch):
        original_append({
            "transaction_id": "tx:p4a:append-race",
            "command_id": "p4a:append-race",
            "expected_stream_revisions": {"gameplay:inventory:organization:supplier": 5},
            "pinned_revisions": {"inventory": 5},
            "events": [{
                "event_id": "event:p4a:append-race",
                "event_type": "gameplay.inventory.commerce_capacity_reserved",
                "schema_version": 1,
                "stream_id": "gameplay:inventory:organization:supplier",
                "stream_revision": 0,
                "global_sequence": 0,
                "transaction_id": "tx:p4a:append-race",
                "command_id": "p4a:append-race",
                "causation_id": "test",
                "correlation_id": "test",
                "visibility_policy": "authority_only",
                "payload": {"actor_ref": "organization:supplier", "capacity_reservation_ref": "capacity:supplier:raced", "available_quantity": 1},
            }],
            "idempotency_record": {"principal_ref": "actor_gameplay.inventory_domain", "idempotency_key": "p4a:append-race", "payload_digest": "sha256:p4a:append-race"},
            "outbox_entries": [],
            "result_digest": "sha256:p4a:append-race",
            "projection_refresh_hints": [],
        })
        return original_append(batch)

    store.append_batch = advance_inventory_then_append  # type: ignore[method-assign]
    result = DynamicCommerceAuthority(store=store, inventory_registry=registry).commit_candidate(
        candidate, tick=2, idempotency_key="p4a:append-race",
    )

    assert result.zero_write
    assert result.error_code == "revision_conflict"
