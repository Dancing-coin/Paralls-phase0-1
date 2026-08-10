from __future__ import annotations

import sys

from common import repo_root

sys.path.insert(0, str(repo_root() / "backend"))

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry, ItemDefinition
from app.gameplay.contract_runtime import ContractAuthorityService, ContractTermsDefinition, ContractTermsRegistry
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.gameplay.phase4_commerce import CommerceAuthority, CommerceCommitment, DeliveryResult, LaborContractRef
from verify_phase4_common import replay_evidence, run_focused, write_report


def _commitment() -> CommerceCommitment:
    return CommerceCommitment(
        commitment_ref="commitment:verify:flour", quote_ref="quote:verify:flour", order_ref="order:verify:flour",
        buyer_organization_ref="organization:bakery-a", seller_organization_ref="organization:supplier",
        account_obligation_refs=("obligation:verify:flour",), inventory_custody_refs=("reservation:supplier:flour",),
        organization_grant_refs=("grant:bakery-a:procurement",), budget_reservation_refs=("reservation:bakery-a:budget",),
        capacity_reservation_refs=("capacity:supplier:delivery",), delivery_window_ref="delivery:verify:1",
        quality_evidence_refs=("evidence:quality:flour",),
        labor_contract=LaborContractRef(contract_ref="contract:verify:counter", employing_organization_ref="organization:bakery-a", worker_ref="character:counter", wage_obligation_ref="obligation:wage:counter", work_evidence_refs=("evidence:work:counter",), wage_amount_minor=5, wage_policy_revision="policy:wage:v1"),
        policy_revision="policy:commerce:v1",
        revision_vector={"gameplay:organization:organization:bakery-a": 1, "gameplay:organization:organization:supplier": 0, "gameplay:economy": 2, "gameplay:inventory:organization:supplier": 5, "gameplay:economy:wage:character:counter": 0, "gameplay:contracts": 1},
    )


ok, log = run_focused("backend/tests/test_phase4_multi_org_commerce.py", "backend/tests/test_owner_authorized_settlement_fragments.py")
store = GameplayEventStore()
OrganizationAuthority(store=store).grant_commerce_budget(command_id="verify:p4b:grant", organization_ref="organization:bakery-a", grant_ref="grant:bakery-a:procurement", budget_reservation_ref="reservation:bakery-a:budget", amount_minor=32, policy_revision="policy:commerce:v1", idempotency_key="grant", causation_id="verify", correlation_id="p4b")
accounts = EconomyAuthorityService(store=store)
accounts.open_account(command_id="verify:p4b:account", account_id="account:bakery-a", owner_ref="organization:bakery-a", currency_ref="currency:local", initial_balance=32, idempotency_key="account", causation_id="verify", correlation_id="p4b")
accounts.reserve_budget(command_id="verify:p4b:budget", reservation_ref="reservation:bakery-a:budget", account_id="account:bakery-a", amount_minor=32, idempotency_key="budget", causation_id="verify", correlation_id="p4b")
terms = ContractTermsRegistry()
terms.register(ContractTermsDefinition("terms:verify:counter", "simple_service", 2, "service-completed"))
ContractAuthorityService(store=store, terms_registry=terms, policy_authorities={"actor_gameplay.organization_domain"}).create_contract(command_id="verify:p4b:contract", contract_id="contract:verify:counter", contract_type="simple_service", terms_ref="terms:verify:counter", party_refs=("organization:bakery-a", "character:counter"), idempotency_key="contract", causation_id="verify", correlation_id="p4b")
registry = InventoryDefinitionRegistry()
registry.register_item(ItemDefinition("item:flour", "v1", 1, 1))
inventory = InventoryAuthorityService(store=store, registry=registry)
inventory.create_container(command_id="verify:p4b:container", actor_ref="organization:supplier", spec=ContainerSpec("container:supplier", 100, 100, 10), idempotency_key="container", causation_id="verify", correlation_id="p4b")
inventory.instantiate(command_id="verify:p4b:flour", actor_ref="organization:supplier", item_id="item:flour:lot", definition_id="item:flour", quantity=4, container_id="container:supplier", idempotency_key="flour", causation_id="verify", correlation_id="p4b")
inventory.reserve_item(command_id="verify:p4b:reservation", actor_ref="organization:supplier", item_id="item:flour:lot", reservation_ref="reservation:supplier:flour", quantity=4, idempotency_key="reservation", causation_id="verify", correlation_id="p4b")
inventory.reserve_commerce_capacity(command_id="verify:p4b:capacity", actor_ref="organization:supplier", capacity_reservation_ref="capacity:supplier:delivery", available_quantity=4, idempotency_key="capacity", causation_id="verify", correlation_id="p4b")
authority = CommerceAuthority(store=store, inventory_registry=registry)
commitment = _commitment()
procurement = authority.accept_commitment(commitment, idempotency_key="verify:p4b:procurement")
delivery = authority.record_delivery(commitment, DeliveryResult(delivery_ref="delivery:verify:failed", commitment_ref=commitment.commitment_ref, status="rejected", delivered_quantity=0, quality_evidence_ref="evidence:quality:failed", delivery_window_ref=commitment.delivery_window_ref, revision_vector={"gameplay:inventory:organization:supplier": 6, "gameplay:economy": 3}, reason="quality_below_contract"), idempotency_key="verify:p4b:delivery")
stale = authority.accept_commitment(commitment, idempotency_key="verify:p4b:stale")
public = authority.project_commitment(commitment, scope="public").model_dump(mode="json")
full, checkpoint_tail = replay_evidence(store.read_events())
raise SystemExit(write_report("phase4b-multi-organization-commerce", {
    "overall_passed": ok and procurement.committed and delivery.committed and stale.zero_write and full.succeeded and checkpoint_tail.succeeded and full.projection_hash == checkpoint_tail.projection_hash,
    "focused_log": log,
    "policy_quote_digest": commitment.policy_revision,
    "atomic_receipt": procurement.receipt.transaction_id if procurement.receipt else None,
    "revision_vector": procurement.revision_vector,
    "replay_hash": f"sha256:{full.projection_hash}",
    "checkpoint_tail_hash": f"sha256:{checkpoint_tail.projection_hash}",
    "privacy_redaction": {"view": public, "account_refs_excluded": not public["account_obligation_refs"], "custody_refs_excluded": not public["inventory_custody_refs"]},
    "failure_zero_write": stale.zero_write,
    "recovery_obligation": any(event.payload.get("recovery_obligation_ref") for event in store.read_events()),
}))
