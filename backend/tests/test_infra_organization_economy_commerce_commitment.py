from __future__ import annotations

import pytest

from app.gameplay.contract_runtime import ContractAuthorityService, ContractTermsDefinition, ContractTermsRegistry
from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry, ItemDefinition
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.gameplay.phase4_commerce import CommerceAuthority, CommerceCommitment, LaborContractRef
from app.gameplay.replay import GameplayProjectionReplay


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
            "gameplay:organization:organization:bakery-a": 1,
            "gameplay:organization:organization:supplier": 0,
            "gameplay:economy": 2,
            "gameplay:inventory:organization:supplier": 5,
            "gameplay:contracts": 1,
            "gameplay:economy:wage:character:char-c": 0,
        },
    )


def _authority() -> tuple[GameplayEventStore, CommerceAuthority, CommerceCommitment]:
    store = GameplayEventStore()
    OrganizationAuthority(store=store).grant_commerce_budget(
        command_id="inf2i:grant",
        organization_ref="organization:bakery-a",
        grant_ref="grant:bakery-a:procurement",
        budget_reservation_ref="reservation:bakery-a:budget",
        amount_minor=32,
        policy_revision="policy:commerce:v1",
        idempotency_key="inf2i:grant",
        causation_id="test",
        correlation_id="test",
    )
    registry = InventoryDefinitionRegistry()
    registry.register_item(ItemDefinition("item:flour", "v1", 1, 1))
    inventory = InventoryAuthorityService(store=store, registry=registry)
    inventory.create_container(
        command_id="inf2i:container", actor_ref="organization:supplier",
        spec=ContainerSpec("container:organization:supplier", 100, 100, 10),
        idempotency_key="inf2i:container", causation_id="test", correlation_id="test",
    )
    inventory.instantiate(
        command_id="inf2i:flour", actor_ref="organization:supplier",
        item_id="item:flour:organization:supplier", definition_id="item:flour", quantity=6,
        container_id="container:organization:supplier", idempotency_key="inf2i:flour",
        causation_id="test", correlation_id="test",
    )
    inventory.reserve_item(
        command_id="inf2i:reservation", actor_ref="organization:supplier",
        item_id="item:flour:organization:supplier", reservation_ref="reservation:supplier:flour",
        quantity=4, idempotency_key="inf2i:reservation", causation_id="test", correlation_id="test",
    )
    inventory.reserve_commerce_capacity(
        command_id="inf2i:capacity", actor_ref="organization:supplier",
        capacity_reservation_ref="capacity:supplier:delivery:1", available_quantity=4,
        idempotency_key="inf2i:capacity", causation_id="test", correlation_id="test",
    )
    terms = ContractTermsRegistry()
    terms.register(ContractTermsDefinition("terms:labor:counter", "simple_service", 2, "service-completed"))
    ContractAuthorityService(
        store=store, terms_registry=terms, policy_authorities={"actor_gameplay.organization_domain"},
    ).create_contract(
        command_id="inf2i:contract", contract_id="contract:labor:counter",
        contract_type="simple_service", terms_ref="terms:labor:counter",
        party_refs=("organization:bakery-a", "character:char-c"),
        idempotency_key="inf2i:contract", causation_id="test", correlation_id="test",
    )
    economy = EconomyAuthorityService(store=store)
    economy.open_account(
        command_id="inf2i:account", account_id="account:bakery-a", owner_ref="organization:bakery-a",
        currency_ref="currency:local", initial_balance=32, idempotency_key="inf2i:account",
        causation_id="test", correlation_id="test",
    )
    economy.reserve_budget(
        command_id="inf2i:budget", reservation_ref="reservation:bakery-a:budget",
        account_id="account:bakery-a", amount_minor=32, idempotency_key="inf2i:budget",
        causation_id="test", correlation_id="test",
    )
    return store, CommerceAuthority(store=store, inventory_registry=registry), _commitment()


def test_commitment_uses_one_owner_fragment_append() -> None:
    store, authority, commitment = _authority()

    result = authority.accept_commitment(commitment, idempotency_key="inf2i:commitment")

    assert result.committed and result.receipt is not None and result.settlement_plan is not None
    assert len(store.read_transactions()) == 9
    transaction = store.read_transactions()[-1]
    assert transaction.idempotency_record.principal_ref == "actor_gameplay.commerce_authority"
    assert set(transaction.expected_stream_revisions) == set(commitment.revision_vector)
    assert {event.event_type for event in transaction.events} >= {
        "gameplay.organization.commerce_commitment_accepted",
        "gameplay.economy.commerce_obligation_recorded",
    }


def test_commitment_receipt_is_derived_from_the_append_result() -> None:
    _, authority, commitment = _authority()
    result = authority.accept_commitment(commitment, idempotency_key="inf2i:receipt")
    receipt = authority.commerce_settlement_receipt_for(result=result.receipt, privacy_scope="authority")

    assert receipt.transaction_id == result.receipt.transaction_id
    assert receipt.committed_event_ids == tuple(result.receipt.committed_event_ids)
    assert receipt.zero_write is False


def test_exact_duplicate_replays_the_original_append_without_writing() -> None:
    store, authority, commitment = _authority()
    first = authority.accept_commitment(commitment, idempotency_key="inf2i:duplicate")
    before_events, before_outbox = store.read_events(), store.list_outbox()

    duplicate = authority.accept_commitment(commitment, idempotency_key="inf2i:duplicate")

    assert first.committed
    assert duplicate.committed and duplicate.receipt is not None
    assert duplicate.receipt.idempotency_status == "duplicate_replayed"
    assert duplicate.zero_write
    assert store.read_events() == before_events and store.list_outbox() == before_outbox


def test_changed_duplicate_is_rejected_before_stale_revision_checks_without_writing() -> None:
    store, authority, commitment = _authority()
    assert authority.accept_commitment(commitment, idempotency_key="inf2i:changed").committed
    before_events, before_outbox = store.read_events(), store.list_outbox()

    changed = authority.accept_commitment(
        commitment.model_copy(update={"quote_ref": "quote:flour:changed"}),
        idempotency_key="inf2i:changed",
    )

    assert changed.zero_write and changed.error_code == "idempotency_key_reused"
    assert store.read_events() == before_events and store.list_outbox() == before_outbox


def _assert_stale_owner_revision_is_zero_write(stream: str) -> None:
    store, authority, commitment = _authority()
    stale_vector = dict(commitment.revision_vector)
    stale_vector[stream] -= 1
    before_events, before_outbox = store.read_events(), store.list_outbox()

    result = authority.accept_commitment(
        commitment.model_copy(update={"revision_vector": stale_vector}),
        idempotency_key=f"inf2i:stale:{stream}",
    )

    assert result.zero_write and result.error_code == "revision_conflict"
    assert store.read_events() == before_events and store.list_outbox() == before_outbox


def test_stale_organization_revision_is_zero_write() -> None:
    _assert_stale_owner_revision_is_zero_write("gameplay:organization:organization:bakery-a")


def test_stale_economy_revision_is_zero_write() -> None:
    _assert_stale_owner_revision_is_zero_write("gameplay:economy")


def test_missing_economy_reservation_is_zero_write() -> None:
    store, authority, commitment = _authority()
    before_events, before_outbox = store.read_events(), store.list_outbox()

    result = authority.accept_commitment(
        commitment.model_copy(update={"budget_reservation_refs": ("reservation:missing",)}),
        idempotency_key="inf2i:missing-reservation",
    )

    assert result.zero_write and result.error_code == "commerce_budget_reservation_missing"
    assert store.read_events() == before_events and store.list_outbox() == before_outbox


def test_public_projection_redacts_account_private_values() -> None:
    store, authority, commitment = _authority()
    assert authority.accept_commitment(commitment, idempotency_key="inf2i:privacy").committed
    public = authority.project_commitment(commitment, scope="public").model_dump(mode="json")

    assert public["account_obligation_refs"] == []
    assert public["budget_reservation_refs"] == []


def test_commitment_outbox_redacts_account_private_values() -> None:
    store, authority, commitment = _authority()
    assert authority.accept_commitment(commitment, idempotency_key="inf2i:outbox").committed
    outbox_payloads = [
        entry.payload_projection
        for entry in store.list_outbox()
        if entry.transaction_id == "transaction:p4b:commit:commitment:flour:bakery-a"
    ]

    assert len(outbox_payloads) == 5
    assert all("amount" not in payload and "account_id" not in payload and "owner_ref" not in payload for payload in outbox_payloads)


def test_full_and_checkpoint_tail_replay_match_for_commitment_batch() -> None:
    store, authority, commitment = _authority()
    checkpoint_events = store.read_events()
    assert authority.accept_commitment(commitment, idempotency_key="inf2i:replay").committed
    replay = GameplayProjectionReplay(projector_id="infra-commerce", projector_version="1")
    full = replay.full_replay(store.read_events())
    checkpoint = replay.create_checkpoint(checkpoint_events)
    tail = replay.checkpoint_plus_tail_replay(checkpoint, store.read_events()[len(checkpoint_events):])

    assert full.succeeded and tail.succeeded
    assert full.projection_hash == tail.projection_hash


def test_receipt_scope_rejection_is_zero_write() -> None:
    store, authority, commitment = _authority()
    result = authority.accept_commitment(commitment, idempotency_key="inf2i:receipt-scope")
    before_events, before_outbox = store.read_events(), store.list_outbox()

    with pytest.raises(ValueError, match="commerce_settlement_receipt_scope_denied"):
        authority.commerce_settlement_receipt_for(result=result.receipt, privacy_scope="public")

    assert store.read_events() == before_events and store.list_outbox() == before_outbox
