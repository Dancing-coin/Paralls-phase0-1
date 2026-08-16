from __future__ import annotations

from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry, ItemDefinition
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.gameplay.phase4_commerce import CommerceAuthority, CommerceCommitment, DeliveryResult
from app.gameplay.shared_contracts import SettlementReceipt


def _commitment(*, economy_revision: int, inventory_revision: int) -> CommerceCommitment:
    return CommerceCommitment(
        commitment_ref="commitment:payment:1",
        quote_ref="quote:payment:1",
        order_ref="order:payment:1",
        buyer_organization_ref="organization:buyer",
        seller_organization_ref="organization:seller",
        account_obligation_refs=("obligation:payment:1",),
        inventory_custody_refs=("reservation:seller:payment",),
        organization_grant_refs=("grant:buyer:payment",),
        budget_reservation_refs=("reservation:buyer:payment",),
        capacity_reservation_refs=("capacity:seller:payment",),
        delivery_window_ref="delivery-window:payment",
        quality_evidence_refs=("evidence:quality:payment",),
        policy_revision="policy:commerce:payment:v1",
        revision_vector={
            "gameplay:organization:organization:buyer": 1,
            "gameplay:organization:organization:seller": 0,
            "gameplay:economy": economy_revision,
            "gameplay:inventory:organization:seller": inventory_revision,
        },
    )


def _delivered_fixture() -> tuple[GameplayEventStore, EconomyAuthorityService, object]:
    store = GameplayEventStore()
    OrganizationAuthority(store=store).grant_commerce_budget(
        command_id="command:payment:grant",
        organization_ref="organization:buyer",
        grant_ref="grant:buyer:payment",
        budget_reservation_ref="reservation:buyer:payment",
        amount_minor=32,
        policy_revision="policy:commerce:payment:v1",
        idempotency_key="idem:payment:grant",
        causation_id="cause:payment",
        correlation_id="corr:payment",
    )
    registry = InventoryDefinitionRegistry()
    registry.register_item(ItemDefinition("item:payment", "v1", 1, 1))
    inventory = InventoryAuthorityService(store=store, registry=registry)
    inventory.create_container(
        command_id="command:payment:container",
        actor_ref="organization:seller",
        spec=ContainerSpec("container:payment", 100, 100, 10),
        idempotency_key="idem:payment:container",
        causation_id="cause:payment",
        correlation_id="corr:payment",
    )
    inventory.instantiate(
        command_id="command:payment:item",
        actor_ref="organization:seller",
        item_id="item:payment:1",
        definition_id="item:payment",
        quantity=2,
        container_id="container:payment",
        idempotency_key="idem:payment:item",
        causation_id="cause:payment",
        correlation_id="corr:payment",
    )
    inventory.reserve_item(
        command_id="command:payment:reserve-item",
        actor_ref="organization:seller",
        item_id="item:payment:1",
        reservation_ref="reservation:seller:payment",
        quantity=1,
        idempotency_key="idem:payment:reserve-item",
        causation_id="cause:payment",
        correlation_id="corr:payment",
    )
    inventory.reserve_commerce_capacity(
        command_id="command:payment:capacity",
        actor_ref="organization:seller",
        capacity_reservation_ref="capacity:seller:payment",
        available_quantity=1,
        idempotency_key="idem:payment:capacity",
        causation_id="cause:payment",
        correlation_id="corr:payment",
    )
    economy = EconomyAuthorityService(store=store)
    economy.open_account(
        command_id="command:payment:buyer-account",
        account_id="account:buyer",
        owner_ref="organization:buyer",
        currency_ref="currency:local",
        initial_balance=64,
        idempotency_key="idem:payment:buyer-account",
        causation_id="cause:payment",
        correlation_id="corr:payment",
    )
    economy.open_account(
        command_id="command:payment:seller-account",
        account_id="account:seller",
        owner_ref="organization:seller",
        currency_ref="currency:local",
        initial_balance=0,
        idempotency_key="idem:payment:seller-account",
        causation_id="cause:payment",
        correlation_id="corr:payment",
    )
    economy.reserve_budget(
        command_id="command:payment:reserve-budget",
        reservation_ref="reservation:buyer:payment",
        account_id="account:buyer",
        amount_minor=32,
        idempotency_key="idem:payment:reserve-budget",
        causation_id="cause:payment",
        correlation_id="corr:payment",
    )
    commitment = _commitment(
        economy_revision=store.get_stream_head("gameplay:economy"),
        inventory_revision=store.get_stream_head("gameplay:inventory:organization:seller"),
    )
    accepted = CommerceAuthority(store=store, inventory_registry=registry).accept_commitment(
        commitment,
        idempotency_key="idem:payment:commitment",
    )
    assert accepted.committed
    delivered = CommerceAuthority(store=store, inventory_registry=registry).record_delivery(
        commitment,
        DeliveryResult(
            delivery_ref="delivery:payment:1",
            commitment_ref=commitment.commitment_ref,
            status="delivered",
            delivered_quantity=1,
            quality_evidence_ref="evidence:quality:payment",
            delivery_window_ref=commitment.delivery_window_ref,
            revision_vector={
                "gameplay:inventory:organization:seller": store.get_stream_head("gameplay:inventory:organization:seller"),
                "gameplay:economy": store.get_stream_head("gameplay:economy"),
            },
        ),
        idempotency_key="idem:payment:delivered",
    )
    assert delivered.committed
    return store, economy, store.read_stream("gameplay:inventory:organization:seller")[-1]


def _record_delivery(
    store: GameplayEventStore,
    *,
    status: str,
    delivery_ref: str,
    idempotency_key: str,
    reason: str,
) -> object:
    commitment = _commitment(
        economy_revision=store.get_stream_head("gameplay:economy"),
        inventory_revision=store.get_stream_head("gameplay:inventory:organization:seller"),
    )
    result = CommerceAuthority(store=store, inventory_registry=InventoryDefinitionRegistry()).record_delivery(
        commitment,
        DeliveryResult(
            delivery_ref=delivery_ref,
            commitment_ref=commitment.commitment_ref,
            status=status,
            delivered_quantity=1,
            quality_evidence_ref="evidence:quality:payment",
            delivery_window_ref=commitment.delivery_window_ref,
            revision_vector={
                "gameplay:inventory:organization:seller": store.get_stream_head("gameplay:inventory:organization:seller"),
                "gameplay:economy": store.get_stream_head("gameplay:economy"),
            },
            reason=reason,
        ),
        idempotency_key=idempotency_key,
    )
    assert result.committed
    return store.read_stream("gameplay:inventory:organization:seller")[-1]


def _settle(
    economy: EconomyAuthorityService,
    delivery_event: object,
    *,
    idempotency_key: str = "idem:payment:settle",
    expected_revision: int | None = None,
    seller_account_id: str = "account:seller",
    privacy_scope: str = "authority",
):
    if expected_revision is None:
        expected_revision = economy._store.get_stream_head("gameplay:economy")
    return economy.settle_commerce_delivery_payment(
        command_id="command:payment:settle",
        delivery_event_id=delivery_event.event_id,
        delivery_stream_id=delivery_event.stream_id,
        delivery_revision=delivery_event.stream_revision,
        commitment_ref="commitment:payment:1",
        budget_reservation_ref="reservation:buyer:payment",
        seller_account_id=seller_account_id,
        expected_economy_revision=expected_revision,
        idempotency_key=idempotency_key,
        causation_id="cause:payment:settle",
        correlation_id="corr:payment:settle",
        privacy_scope=privacy_scope,
    )


def _compensate(
    economy: EconomyAuthorityService,
    *,
    settled_delivery_event: object,
    compensation_event: object,
    idempotency_key: str = "idem:payment:compensate",
    expected_revision: int | None = None,
    privacy_scope: str = "authority",
):
    if expected_revision is None:
        expected_revision = economy._store.get_stream_head("gameplay:economy")
    return economy.compensate_commerce_delivery_payment(
        command_id="command:payment:compensate",
        settled_delivery_event_id=settled_delivery_event.event_id,
        compensation_event_id=compensation_event.event_id,
        compensation_stream_id=compensation_event.stream_id,
        compensation_revision=compensation_event.stream_revision,
        commitment_ref="commitment:payment:1",
        expected_economy_revision=expected_revision,
        idempotency_key=idempotency_key,
        causation_id="cause:payment:compensate",
        correlation_id="corr:payment:compensate",
        privacy_scope=privacy_scope,
    )


def test_commerce_delivery_payment_uses_committed_sources_and_one_economy_append() -> None:
    store, economy, delivery_event = _delivered_fixture()
    before_transactions = len(store.read_transactions())

    result = _settle(economy, delivery_event)

    assert result.committed
    assert result.committed_event_ids
    assert [store.get_event(event_id).event_type for event_id in result.committed_event_ids] == [
        "gameplay.economy.account_debited",
        "gameplay.economy.account_credited",
        "gameplay.economy.commerce_delivery_payment_settled",
    ]
    assert len(store.read_transactions()) == before_transactions + 1
    assert result.global_sequence_range is not None
    receipt = SettlementReceipt.from_append_result(
        result=result,
        audit_refs=(f"economy_transaction:{result.transaction_id}",),
    )
    assert receipt.zero_write is False
    assert receipt.committed_event_ids == tuple(result.committed_event_ids)
    accounts = economy._projector.rebuild(store.read_events()).accounts
    assert accounts["account:buyer"].balance == 32
    assert accounts["account:seller"].balance == 32
    settled_marker = store.get_event(result.committed_event_ids[-1])
    assert settled_marker.payload["buyer_account_id"] == "account:buyer"
    assert settled_marker.payload["seller_account_id"] == "account:seller"
    assert settled_marker.payload["amount_minor"] == 32
    outbox = [entry for entry in store.list_outbox() if entry.transaction_id == result.transaction_id]
    assert len(outbox) == 3
    assert {entry.audience for entry in outbox} == {"authority:economy"}
    projection = economy.commerce_delivery_payment_projection(scope="authority")
    assert projection["payments"][delivery_event.event_id]["status"] == "settled"
    assert projection["payments"][delivery_event.event_id]["amount_minor"] == 32


def test_commerce_delivery_payment_rejects_forged_source_account_currency_privacy_and_revision_without_write() -> None:
    store, economy, delivery_event = _delivered_fixture()
    economy.open_account(
        command_id="command:payment:seller-foreign-account",
        account_id="account:seller:foreign",
        owner_ref="organization:seller",
        currency_ref="currency:foreign",
        initial_balance=0,
        idempotency_key="idem:payment:seller-foreign-account",
        causation_id="cause:payment",
        correlation_id="corr:payment",
    )
    before = tuple(store.read_events())

    forged_source = economy.settle_commerce_delivery_payment(
        command_id="command:payment:forged-source",
        delivery_event_id="event:missing",
        delivery_stream_id=delivery_event.stream_id,
        delivery_revision=delivery_event.stream_revision,
        commitment_ref="commitment:payment:1",
        budget_reservation_ref="reservation:buyer:payment",
        seller_account_id="account:seller",
        expected_economy_revision=store.get_stream_head("gameplay:economy"),
        idempotency_key="idem:payment:forged-source",
        causation_id="cause:payment",
        correlation_id="corr:payment",
    )
    wrong_owner = _settle(economy, delivery_event, idempotency_key="idem:payment:wrong-owner", seller_account_id="account:buyer")
    wrong_currency = _settle(
        economy,
        delivery_event,
        idempotency_key="idem:payment:wrong-currency",
        seller_account_id="account:seller:foreign",
    )
    wrong_privacy = _settle(
        economy,
        delivery_event,
        idempotency_key="idem:payment:wrong-privacy",
        privacy_scope="public",
    )
    stale = _settle(economy, delivery_event, idempotency_key="idem:payment:stale", expected_revision=store.get_stream_head("gameplay:economy") - 1)

    assert forged_source.failure.error_code == "commerce_payment_source_missing"
    assert wrong_owner.failure.error_code == "commerce_payment_seller_account_invalid"
    assert wrong_currency.failure.error_code == "commerce_payment_seller_account_invalid"
    assert wrong_privacy.failure.error_code == "commerce_payment_privacy_denied"
    assert stale.failure.error_code == "revision_conflict"
    assert tuple(store.read_events()) == before


def test_commerce_delivery_payment_rejects_uncommitted_reservation_and_source_revision_or_head_mismatch_without_write() -> None:
    store, economy, delivery_event = _delivered_fixture()
    economy.reserve_budget(
        command_id="command:payment:reserve-budget:alternate",
        reservation_ref="reservation:buyer:alternate",
        account_id="account:buyer",
        amount_minor=5,
        idempotency_key="idem:payment:reserve-budget:alternate",
        causation_id="cause:payment",
        correlation_id="corr:payment",
    )
    before = tuple(store.read_events())
    uncommitted_reservation = economy.settle_commerce_delivery_payment(
        command_id="command:payment:alternate-reservation",
        delivery_event_id=delivery_event.event_id,
        delivery_stream_id=delivery_event.stream_id,
        delivery_revision=delivery_event.stream_revision,
        commitment_ref="commitment:payment:1",
        budget_reservation_ref="reservation:buyer:alternate",
        seller_account_id="account:seller",
        expected_economy_revision=store.get_stream_head("gameplay:economy"),
        idempotency_key="idem:payment:alternate-reservation",
        causation_id="cause:payment",
        correlation_id="corr:payment",
    )
    assert uncommitted_reservation.failure.error_code == "commerce_payment_obligation_invalid"
    assert tuple(store.read_events()) == before
    stale_source_revision = economy.settle_commerce_delivery_payment(
        command_id="command:payment:stale-source-revision",
        delivery_event_id=delivery_event.event_id,
        delivery_stream_id=delivery_event.stream_id,
        delivery_revision=delivery_event.stream_revision - 1,
        commitment_ref="commitment:payment:1",
        budget_reservation_ref="reservation:buyer:payment",
        seller_account_id="account:seller",
        expected_economy_revision=store.get_stream_head("gameplay:economy"),
        idempotency_key="idem:payment:stale-source-revision",
        causation_id="cause:payment",
        correlation_id="corr:payment",
    )
    assert stale_source_revision.failure.error_code == "commerce_payment_source_invalid"
    assert tuple(store.read_events()) == before
    _record_delivery(
        store,
        status="rejected",
        delivery_ref="delivery:payment:advance-source",
        idempotency_key="idem:payment:advance-source",
        reason="advance_source_head",
    )
    advanced_source_head = _settle(
        economy,
        delivery_event,
        idempotency_key="idem:payment:advanced-source-head",
    )

    assert advanced_source_head.failure.error_code == "commerce_payment_source_invalid"
    assert tuple(store.read_events())[-1].event_id != delivery_event.event_id
    assert tuple(store.read_events())[: len(before)] == before


def test_commerce_delivery_payment_replays_exact_duplicate_and_rejects_changed_duplicate() -> None:
    store, economy, delivery_event = _delivered_fixture()
    expected_revision = store.get_stream_head("gameplay:economy")
    first = _settle(economy, delivery_event, expected_revision=expected_revision)
    duplicate = _settle(economy, delivery_event, expected_revision=expected_revision)
    changed = _settle(economy, delivery_event, seller_account_id="account:buyer")

    assert first.committed
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert changed.failure.error_code == "idempotency_key_reused"
    assert len(store.read_events()) == len({event.event_id for event in store.read_events()})


def test_commerce_delivery_payment_compensation_reverses_exact_accounts_and_rejects_duplicate_without_write() -> None:
    store, economy, delivery_event = _delivered_fixture()
    settled = _settle(economy, delivery_event)
    compensation_event = _record_delivery(
        store,
        status="rejected",
        delivery_ref="delivery:payment:rejected",
        idempotency_key="idem:payment:rejected",
        reason="quality_failed",
    )
    before_duplicate = tuple(store.read_events())

    compensated = _compensate(
        economy,
        settled_delivery_event=delivery_event,
        compensation_event=compensation_event,
    )
    after_compensated = tuple(store.read_events())
    duplicate = _compensate(
        economy,
        settled_delivery_event=delivery_event,
        compensation_event=compensation_event,
        idempotency_key="idem:payment:compensate:duplicate",
    )

    assert settled.committed
    assert compensated.committed
    assert [store.get_event(event_id).event_type for event_id in compensated.committed_event_ids] == [
        "gameplay.economy.account_debited",
        "gameplay.economy.account_credited",
        "gameplay.economy.commerce_delivery_payment_compensated",
    ]
    accounts = economy._projector.rebuild(store.read_events()).accounts
    assert accounts["account:buyer"].balance == 64
    assert accounts["account:seller"].balance == 0
    compensated_marker = store.get_event(compensated.committed_event_ids[-1])
    assert compensated_marker.payload["settled_delivery_event_id"] == delivery_event.event_id
    assert compensated_marker.payload["compensation_event_id"] == compensation_event.event_id
    assert compensated_marker.payload["buyer_account_id"] == "account:buyer"
    assert compensated_marker.payload["seller_account_id"] == "account:seller"
    assert compensated_marker.payload["amount_minor"] == 32
    assert duplicate.failure.error_code == "commerce_payment_already_compensated"
    assert tuple(store.read_events()) == after_compensated


def test_commerce_delivery_payment_compensation_rejects_insufficient_seller_funds_without_write() -> None:
    store, economy, delivery_event = _delivered_fixture()
    assert _settle(economy, delivery_event).committed
    economy.transfer(
        command_id="command:payment:drain-seller",
        debit_account_id="account:seller",
        credit_account_id="account:buyer",
        amount=32,
        idempotency_key="idem:payment:drain-seller",
        causation_id="cause:payment",
        correlation_id="corr:payment",
    )
    compensation_event = _record_delivery(
        store,
        status="cancelled",
        delivery_ref="delivery:payment:cancelled",
        idempotency_key="idem:payment:cancelled",
        reason="buyer_cancelled",
    )
    before = tuple(store.read_events())

    result = _compensate(
        economy,
        settled_delivery_event=delivery_event,
        compensation_event=compensation_event,
    )

    assert result.failure.error_code == "commerce_payment_compensation_insufficient_funds"
    assert tuple(store.read_events()) == before


def test_commerce_delivery_payment_scope_and_checkpoint_tail_replay_are_authority_only() -> None:
    store, economy, delivery_event = _delivered_fixture()
    settled = _settle(economy, delivery_event)
    assert settled.committed
    checkpoint_at = settled.global_sequence_range[1]
    settled_checkpoint = economy.commerce_delivery_payment_projection(scope="authority", checkpoint_at=checkpoint_at)
    assert settled_checkpoint["payments"][delivery_event.event_id]["status"] == "settled"
    compensation_event = _record_delivery(
        store,
        status="rejected",
        delivery_ref="delivery:payment:projection",
        idempotency_key="idem:payment:projection",
        reason="projection_quality_failed",
    )
    assert _compensate(
        economy,
        settled_delivery_event=delivery_event,
        compensation_event=compensation_event,
        idempotency_key="idem:payment:projection:compensate",
    ).committed

    authority = economy.commerce_delivery_payment_projection(scope="authority")
    public = economy.commerce_delivery_payment_projection(scope="public")
    tail = economy.commerce_delivery_payment_projection(scope="authority", checkpoint_at=checkpoint_at)

    assert authority["payments"]
    assert authority["payments"][delivery_event.event_id]["status"] == "compensated"
    assert public["payments"] == {}
    assert tail["payments"][delivery_event.event_id]["status"] == "compensated"
    assert tail["projection_hash"] == authority["projection_hash"]
