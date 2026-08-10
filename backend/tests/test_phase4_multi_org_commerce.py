from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.phase4_commerce import (
    CommerceCommitment,
    CommerceAuthority,
    DeliveryResult,
    LaborContractRef,
)
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry, ItemDefinition
from app.gameplay.contract_runtime import ContractAuthorityService, ContractTermsDefinition, ContractTermsRegistry


def _commitment() -> CommerceCommitment:
    return CommerceCommitment(
        commitment_ref="commitment:flour:bakery-a",
        quote_ref="quote:flour:a",
        order_ref="order:bakery:a",
        buyer_organization_ref="organization:bakery-a",
        seller_organization_ref="organization:supplier",
        account_obligation_refs=("obligation:account:flour",),
        inventory_custody_refs=("reservation:supplier:flour",),
        delivery_window_ref="delivery-window:1",
        quality_evidence_refs=("evidence:quality:standard",),
        organization_grant_refs=("grant:bakery-a:procurement",),
        budget_reservation_refs=("reservation:bakery-a:budget",),
        capacity_reservation_refs=("capacity:supplier:delivery:1",),
        labor_contract=LaborContractRef(
            contract_ref="contract:labor:counter",
            employing_organization_ref="organization:bakery-a",
            worker_ref="character:char-c",
            wage_obligation_ref="obligation:wage:counter",
            work_evidence_refs=("evidence:work:counter:1",),
            wage_amount_minor=5,
            wage_policy_revision="policy:wage:v1",
        ),
        policy_revision="policy:commerce:v1",
        revision_vector={
            "gameplay:organization:organization:bakery-a": 0,
            "gameplay:organization:organization:supplier": 0,
            "gameplay:economy": 0,
            "gameplay:inventory:organization:supplier": 0,
            "gameplay:economy:wage:character:char-c": 0,
        },
    )


def _authorized_commitment(*, seller: str = "organization:supplier") -> CommerceCommitment:
    commitment = _commitment().model_copy(update={"seller_organization_ref": seller})
    vector = dict(commitment.revision_vector)
    vector["gameplay:organization:organization:bakery-a"] = 1
    vector["gameplay:economy"] = 2
    vector["gameplay:inventory:organization:supplier"] = 5
    vector["gameplay:contracts"] = 1
    if seller != "organization:supplier":
        vector.pop("gameplay:organization:organization:supplier")
        vector.pop("gameplay:inventory:organization:supplier")
        vector[f"gameplay:organization:{seller}"] = 0
        vector[f"gameplay:inventory:{seller}"] = 5
    return commitment.model_copy(update={"revision_vector": vector})


def _inventory_owner_facts(store: GameplayEventStore, *, actor_ref: str = "organization:supplier") -> InventoryDefinitionRegistry:
    registry = InventoryDefinitionRegistry()
    registry.register_item(ItemDefinition("item:flour", "v1", 1, 1))
    inventory = InventoryAuthorityService(store=store, registry=registry)
    inventory.create_container(command_id=f"p4b:{actor_ref}:container", actor_ref=actor_ref, spec=ContainerSpec(f"container:{actor_ref}", 100, 100, 10), idempotency_key="container", causation_id="test", correlation_id="test")
    inventory.instantiate(command_id=f"p4b:{actor_ref}:flour", actor_ref=actor_ref, item_id=f"item:flour:{actor_ref}", definition_id="item:flour", quantity=6, container_id=f"container:{actor_ref}", idempotency_key="flour", causation_id="test", correlation_id="test")
    inventory.reserve_item(command_id=f"p4b:{actor_ref}:reservation", actor_ref=actor_ref, item_id=f"item:flour:{actor_ref}", reservation_ref="reservation:supplier:flour", quantity=4, idempotency_key="reservation", causation_id="test", correlation_id="test")
    inventory.reserve_commerce_capacity(command_id=f"p4b:{actor_ref}:capacity", actor_ref=actor_ref, capacity_reservation_ref="capacity:supplier:delivery:1", available_quantity=4, idempotency_key="capacity", causation_id="test", correlation_id="test")
    return registry


def _labor_contract_owner_facts(store: GameplayEventStore) -> None:
    terms = ContractTermsRegistry()
    terms.register(ContractTermsDefinition("terms:labor:counter", "simple_service", 2, "service-completed"))
    ContractAuthorityService(store=store, terms_registry=terms, policy_authorities={"actor_gameplay.organization_domain"}).create_contract(
        command_id="p4b:labor-contract",
        contract_id="contract:labor:counter",
        contract_type="simple_service",
        terms_ref="terms:labor:counter",
        party_refs=("organization:bakery-a", "character:char-c"),
        idempotency_key="p4b:labor-contract",
        causation_id="test",
        correlation_id="test",
    )


def _economy_budget_owner_facts(store: GameplayEventStore) -> None:
    economy = EconomyAuthorityService(store=store)
    economy.open_account(
        command_id="p4b:bakery-a-account",
        account_id="account:bakery-a",
        owner_ref="organization:bakery-a",
        currency_ref="currency:local",
        initial_balance=32,
        idempotency_key="p4b:bakery-a-account",
        causation_id="test",
        correlation_id="test",
    )
    economy.reserve_budget(
        command_id="p4b:bakery-a-budget",
        reservation_ref="reservation:bakery-a:budget",
        account_id="account:bakery-a",
        amount_minor=32,
        idempotency_key="p4b:bakery-a-budget",
        causation_id="test",
        correlation_id="test",
    )


def test_commitment_references_domain_facts_without_shadow_warehouse_or_payroll() -> None:
    commitment = _commitment()

    assert commitment.account_obligation_refs == ("obligation:account:flour",)
    assert commitment.inventory_custody_refs == ("reservation:supplier:flour",)
    assert "warehouse" not in commitment.model_dump(mode="json")
    assert "payroll" not in commitment.model_dump(mode="json")


def test_organization_grant_budget_and_capacity_refs_are_typed() -> None:
    try:
        CommerceCommitment(**_commitment().model_dump(mode="python") | {"capacity_reservation_refs": ("not-a-capacity-ref",)})
    except Exception as exc:
        assert "capacity_reservation_ref_invalid" in str(exc)
    else:
        raise AssertionError("capacity refs must retain their owner-specific prefix")


def test_multi_org_commit_is_one_atomic_batch_with_complete_revision_vector() -> None:
    store = GameplayEventStore()
    OrganizationAuthority(store=store).grant_commerce_budget(
        command_id="p4b:grant",
        organization_ref="organization:bakery-a",
        grant_ref="grant:bakery-a:procurement",
        budget_reservation_ref="reservation:bakery-a:budget",
        amount_minor=32,
        policy_revision="policy:commerce:v1",
        idempotency_key="p4b:grant",
        causation_id="test",
        correlation_id="test",
    )

    registry = _inventory_owner_facts(store)
    _labor_contract_owner_facts(store)
    _economy_budget_owner_facts(store)
    commitment = _authorized_commitment()
    result = CommerceAuthority(store=store, inventory_registry=registry).accept_commitment(commitment, idempotency_key="p4b:accept")

    assert result.committed
    assert result.settlement_plan is not None
    assert result.settlement_plan.expected_revision_vector == commitment.revision_vector
    assert store.read_transactions()[-1].expected_stream_revisions["gameplay:contracts"] == 1
    assert len(result.receipt.committed_event_ids) == 5
    assert result.receipt is not None
    assert store.read_transactions()[-1].owner_fragments
    assert any(event.event_type == "gameplay.economy.wage_accrued" for event in store.read_events())


def test_commitment_requires_economy_owned_budget_reservation_without_writing() -> None:
    store = GameplayEventStore()
    OrganizationAuthority(store=store).grant_commerce_budget(
        command_id="p4b:grant-without-economy-budget",
        organization_ref="organization:bakery-a",
        grant_ref="grant:bakery-a:procurement",
        budget_reservation_ref="reservation:bakery-a:budget",
        amount_minor=32,
        policy_revision="policy:commerce:v1",
        idempotency_key="p4b:grant-without-economy-budget",
        causation_id="test",
        correlation_id="test",
    )
    registry = _inventory_owner_facts(store)
    _labor_contract_owner_facts(store)
    before = tuple(store.read_events())

    rejected = CommerceAuthority(store=store, inventory_registry=registry).accept_commitment(
        _authorized_commitment().model_copy(
            update={"revision_vector": _authorized_commitment().revision_vector | {"gameplay:economy": 0}}
        ),
        idempotency_key="p4b:missing-economy-budget",
    )

    assert rejected.zero_write
    assert rejected.error_code == "commerce_budget_reservation_missing"
    assert tuple(store.read_events()) == before


def test_commitment_requires_grant_budget_capacity_and_routes_inventory_to_seller_owner() -> None:
    store = GameplayEventStore()
    OrganizationAuthority(store=store).grant_commerce_budget(
        command_id="p4b:grant-mill",
        organization_ref="organization:bakery-a",
        grant_ref="grant:bakery-a:procurement",
        budget_reservation_ref="reservation:bakery-a:budget",
        amount_minor=32,
        policy_revision="policy:commerce:v1",
        idempotency_key="p4b:grant-mill",
        causation_id="test",
        correlation_id="test",
    )
    registry = _inventory_owner_facts(store, actor_ref="organization:mill")
    _labor_contract_owner_facts(store)
    _economy_budget_owner_facts(store)
    commitment = _authorized_commitment(seller="organization:mill")

    result = CommerceAuthority(store=store, inventory_registry=registry).accept_commitment(commitment, idempotency_key="p4b:mill")

    assert result.committed
    assert {event.stream_id for event in store.read_events()} >= {"gameplay:inventory:organization:mill"}

    incomplete = commitment.model_copy(update={"revision_vector": {"gameplay:economy": 0}})
    rejected = CommerceAuthority(store=GameplayEventStore()).accept_commitment(incomplete, idempotency_key="p4b:incomplete")
    assert rejected.zero_write
    assert rejected.error_code == "revision_vector_incomplete"


def test_delivery_quality_reject_and_cancel_are_structured_zero_write_or_recoverable() -> None:
    store = GameplayEventStore()
    OrganizationAuthority(store=store).grant_commerce_budget(
        command_id="p4b:grant-delivery",
        organization_ref="organization:bakery-a",
        grant_ref="grant:bakery-a:procurement",
        budget_reservation_ref="reservation:bakery-a:budget",
        amount_minor=32,
        policy_revision="policy:commerce:v1",
        idempotency_key="p4b:grant-delivery",
        causation_id="test",
        correlation_id="test",
    )
    registry = _inventory_owner_facts(store)
    _labor_contract_owner_facts(store)
    _economy_budget_owner_facts(store)
    authority = CommerceAuthority(store=store, inventory_registry=registry)
    commitment = _authorized_commitment()
    accepted = authority.accept_commitment(commitment, idempotency_key="p4b:delivery-base")

    rejected = authority.record_delivery(
        commitment,
        DeliveryResult(
            delivery_ref="delivery:1",
            commitment_ref=commitment.commitment_ref,
            status="rejected",
            delivered_quantity=3,
            quality_evidence_ref="evidence:quality:failed",
            delivery_window_ref="delivery-window:1",
            revision_vector={
                "gameplay:inventory:organization:supplier": 6,
                    "gameplay:economy": 3,
            },
            reason="quality_below_contract",
        ),
        idempotency_key="p4b:delivery-reject",
    )

    assert accepted.committed
    assert rejected.committed
    assert rejected.error_code is None
    assert any(event.event_type.endswith("delivery_rejected") for event in store.read_events())
    cancelled = authority.record_delivery(
        commitment,
        DeliveryResult(
            delivery_ref="delivery:cancelled",
            commitment_ref=commitment.commitment_ref,
            status="cancelled",
            delivered_quantity=0,
            quality_evidence_ref="evidence:quality:cancelled",
            delivery_window_ref="delivery-window:1",
            revision_vector={
                "gameplay:inventory:organization:supplier": 7,
                    "gameplay:economy": 4,
            },
            reason="buyer_cancelled",
        ),
        idempotency_key="p4b:delivery-cancel",
    )
    assert cancelled.committed
    assert any(event.event_type.endswith("delivery_cancelled") for event in store.read_events())
    assert any(event.payload.get("recovery_obligation_ref") for event in store.read_events())


def test_stale_commitment_is_zero_write_and_privacy_view_redacts_private_refs() -> None:
    store = GameplayEventStore()
    OrganizationAuthority(store=store).grant_commerce_budget(
        command_id="p4b:grant-stale",
        organization_ref="organization:bakery-a",
        grant_ref="grant:bakery-a:procurement",
        budget_reservation_ref="reservation:bakery-a:budget",
        amount_minor=32,
        policy_revision="policy:commerce:v1",
        idempotency_key="p4b:grant-stale",
        causation_id="test",
        correlation_id="test",
    )
    registry = _inventory_owner_facts(store)
    _labor_contract_owner_facts(store)
    _economy_budget_owner_facts(store)
    authority = CommerceAuthority(store=store, inventory_registry=registry)
    commitment = _authorized_commitment()
    authority.accept_commitment(commitment, idempotency_key="p4b:stale-base")
    stale = authority.accept_commitment(commitment, idempotency_key="p4b:stale-again")

    assert not stale.committed
    assert stale.zero_write
    assert stale.error_code == "revision_conflict"
    public = authority.project_commitment(commitment, scope="public")
    assert "account_obligation_refs" not in public
    assert "inventory_custody_refs" not in public


def test_commitment_rejects_unissued_organization_grant_without_writing() -> None:
    store = GameplayEventStore()
    rejected = CommerceAuthority(store=store).accept_commitment(_commitment().model_copy(update={"labor_contract": None}), idempotency_key="p4b:missing-grant")
    assert rejected.zero_write
    assert rejected.error_code == "commerce_organization_grant_missing"
    assert store.read_events() == []
