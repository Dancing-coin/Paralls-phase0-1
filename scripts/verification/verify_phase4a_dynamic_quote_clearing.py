from __future__ import annotations

import sys

from common import repo_root

sys.path.insert(0, str(repo_root() / "backend"))

from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry, ItemDefinition
from app.gameplay.phase4_commerce import DeterministicClearing, DynamicCommerceAuthority, DynamicQuote, QuoteOrder
from verify_phase4_common import replay_evidence, run_focused, write_report


def _stage_result():
    store = GameplayEventStore()
    registry = InventoryDefinitionRegistry()
    registry.register_item(ItemDefinition("item:flour", "v1", 1, 1))
    inventory = InventoryAuthorityService(store=store, registry=registry)
    inventory.create_container(command_id="verify:p4a:container", actor_ref="organization:supplier", spec=ContainerSpec("container:supplier", 100, 100, 10), idempotency_key="container", causation_id="verify", correlation_id="p4a")
    inventory.instantiate(command_id="verify:p4a:flour", actor_ref="organization:supplier", item_id="item:flour:lot", definition_id="item:flour", quantity=4, container_id="container:supplier", idempotency_key="flour", causation_id="verify", correlation_id="p4a")
    inventory.reserve_item(command_id="verify:p4a:stock", actor_ref="organization:supplier", item_id="item:flour:lot", reservation_ref="reservation:supplier:flour", quantity=4, idempotency_key="stock", causation_id="verify", correlation_id="p4a")
    inventory.reserve_commerce_capacity(command_id="verify:p4a:seller-capacity", actor_ref="organization:supplier", capacity_reservation_ref="capacity:supplier:delivery", available_quantity=4, idempotency_key="seller-capacity", causation_id="verify", correlation_id="p4a")
    inventory.reserve_commerce_capacity(command_id="verify:p4a:buyer-capacity", actor_ref="organization:bakery-a", capacity_reservation_ref="capacity:bakery-a:receive", available_quantity=4, idempotency_key="buyer-capacity", causation_id="verify", correlation_id="p4a")
    economy = EconomyAuthorityService(store=store)
    economy.open_account(command_id="verify:p4a:account", account_id="account:bakery-a", owner_ref="organization:bakery-a", currency_ref="currency:local", initial_balance=32, idempotency_key="account", causation_id="verify", correlation_id="p4a")
    economy.reserve_budget(command_id="verify:p4a:budget", reservation_ref="reservation:bakery-a:budget", account_id="account:bakery-a", amount_minor=32, idempotency_key="budget", causation_id="verify", correlation_id="p4a")
    vector = {"gameplay:economy": 4, "gameplay:inventory:organization:supplier": 5, "gameplay:inventory:organization:bakery-a": 1}
    quote = DynamicQuote(quote_ref="quote:verify:flour", issuer_ref="organization:supplier", item_ref="item:flour", quality_ref="quality:standard", side="sell", quantity_limit=4, unit_price_minor=7, currency_ref="currency:local", version=1, valid_from_tick=1, valid_until_tick=10, policy_revision="policy:commerce:v1", reservation_ref="reservation:supplier:flour", inventory_custody_ref="custody:supplier:flour", capacity_reservation_ref="capacity:supplier:delivery", delivery_policy_ref="policy:delivery:standard", cancellation_policy_ref="policy:cancel:standard", public_digest="sha256:verify:quote")
    order = QuoteOrder(order_ref="order:verify:flour", issuer_ref="organization:bakery-a", item_ref="item:flour", quality_ref="quality:standard", side="buy", quantity=4, limit_price_minor=8, currency_ref="currency:local", created_tick=1, valid_from_tick=1, valid_until_tick=10, policy_revision="policy:commerce:v1", reservation_ref="reservation:bakery-a:budget", inventory_custody_ref="custody:bakery-a:incoming", capacity_reservation_ref="capacity:bakery-a:receive", delivery_policy_ref="policy:delivery:standard", cancellation_policy_ref="policy:cancel:standard", public_digest="sha256:verify:order", revision_vector=vector)
    economy.publish_dynamic_quote(command_id="verify:p4a:quote", quote_payload=quote.model_dump(mode="json"), idempotency_key="quote", causation_id="verify", correlation_id="p4a")
    economy.submit_dynamic_order(command_id="verify:p4a:order", order_payload=order.model_dump(mode="json"), idempotency_key="order", causation_id="verify", correlation_id="p4a")
    candidate = DeterministicClearing().clear(quotes=(quote,), orders=(order,), tick=2).candidates[0]
    authority = DynamicCommerceAuthority(store=store, inventory_registry=registry)
    result = authority.commit_candidate(candidate, tick=2, idempotency_key="clear")
    reject = authority.commit_candidate(candidate, tick=2, idempotency_key="stale")
    return store, quote, result, reject


ok, log = run_focused("backend/tests/test_phase4_dynamic_quote_clearing.py", "backend/tests/test_phase4_owner_backed_revalidation.py")
store, quote, result, reject = _stage_result()
full, checkpoint_tail = replay_evidence(store.read_events())
public_quote = {"quote_ref": quote.quote_ref, "issuer_ref": quote.issuer_ref, "public_digest": quote.public_digest}
raise SystemExit(write_report("phase4a-dynamic-quote-clearing", {
    "overall_passed": ok and result.committed and reject.zero_write and full.succeeded and checkpoint_tail.succeeded and full.projection_hash == checkpoint_tail.projection_hash,
    "focused_log": log,
    "policy_quote_digest": quote.public_digest,
    "atomic_receipt": result.receipt.transaction_id if result.receipt else None,
    "revision_vector": result.revision_vector,
    "replay_hash": f"sha256:{full.projection_hash}",
    "checkpoint_tail_hash": f"sha256:{checkpoint_tail.projection_hash}",
    "privacy_redaction": {"public_quote": public_quote, "reservation_ref_excluded": "reservation_ref" not in public_quote},
    "failure_zero_write": reject.zero_write,
}))
