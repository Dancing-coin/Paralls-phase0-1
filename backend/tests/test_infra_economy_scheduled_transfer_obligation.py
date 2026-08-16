import pytest

from app.gameplay.economy_runtime import EconomyAuthorityService, EconomyProjector, EconomyRuntimeError
from app.gameplay.event_store import GameplayEventStore
from app.world_runtime.obligations import (
    ObligationLifecycleProjection,
    ObligationSettlementCoordinator,
)


POLICY = "policy:economy_scheduled_account_transfer@1"


def _service_with_accounts() -> tuple[GameplayEventStore, EconomyAuthorityService]:
    store = GameplayEventStore()
    service = EconomyAuthorityService(store=store)
    assert service.open_account(
        command_id="scheduled-transfer:open:alice",
        account_id="account:alice",
        owner_ref="actor:alice",
        currency_ref="currency:coin",
        initial_balance=10,
        idempotency_key="scheduled-transfer:open:alice",
        causation_id="cause:scheduled-transfer:open:alice",
        correlation_id="corr:scheduled-transfer:open:alice",
        expected_revision=0,
    ).committed
    assert service.open_account(
        command_id="scheduled-transfer:open:bob",
        account_id="account:bob",
        owner_ref="actor:bob",
        currency_ref="currency:coin",
        initial_balance=0,
        idempotency_key="scheduled-transfer:open:bob",
        causation_id="cause:scheduled-transfer:open:bob",
        correlation_id="corr:scheduled-transfer:open:bob",
        expected_revision=1,
    ).committed
    return store, service


def test_economy_scheduled_transfer_due_settles_account_truth_and_obligation_in_one_batch() -> None:
    store, service = _service_with_accounts()
    opened = service.open_scheduled_account_transfer_obligation(
        command_id="scheduled-transfer:open",
        transfer_ref="scheduled-transfer:alice-to-bob:1",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=4,
        due_tick=8,
        idempotency_key="scheduled-transfer:open",
        causation_id="cause:scheduled-transfer:open",
        correlation_id="corr:scheduled-transfer:open",
        expected_revision=2,
    )
    assert opened.committed and opened.obligation is not None
    due = opened.obligation.model_copy(update={"status": "due"})

    coordinator = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(service.scheduled_account_transfer_obligation_registration(),),
    )
    plan = coordinator.plan_settle(
        obligation=due,
        fragments=(service.build_scheduled_account_transfer_settlement_fragment(obligation=due),),
        principal_ref=EconomyAuthorityService._PRINCIPAL,
    )

    assert plan.ready and plan.owner_commit_batch is not None
    result = service.commit_obligation_batch(plan.owner_commit_batch)
    assert result.committed
    assert [event.event_type for event in store.read_events()][-3:] == [
        "gameplay.economy.account_debited",
        "gameplay.economy.account_credited",
        "gameplay.economy.scheduled_transfer_obligation_settled",
    ]
    assert EconomyProjector().rebuild(store.read_events()).balances == {
        "account:alice": 6,
        "account:bob": 4,
    }
    assert ObligationLifecycleProjection(
        (service.scheduled_account_transfer_obligation_registration(),)
    ).rebuild(store.read_events()).terminal[due.obligation_id].status == "settled"


def test_economy_scheduled_transfer_cancellation_is_terminal_without_moving_account_truth() -> None:
    store, service = _service_with_accounts()
    opened = service.open_scheduled_account_transfer_obligation(
        command_id="scheduled-transfer:cancel:open",
        transfer_ref="scheduled-transfer:cancel:1",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=4,
        due_tick=8,
        idempotency_key="scheduled-transfer:cancel:open",
        causation_id="cause:scheduled-transfer:cancel:open",
        correlation_id="corr:scheduled-transfer:cancel:open",
        expected_revision=2,
    )
    assert opened.obligation is not None

    coordinator = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(service.scheduled_account_transfer_obligation_registration(),),
    )
    plan = coordinator.plan_cancel(
        obligation=opened.obligation,
        fragment=service.build_scheduled_account_transfer_cancellation_fragment(
            obligation=opened.obligation,
            reason_ref="reason:buyer-cancelled",
        ),
        principal_ref=EconomyAuthorityService._PRINCIPAL,
        reason_ref="reason:buyer-cancelled",
    )

    assert plan.ready and plan.owner_commit_batch is not None
    result = service.commit_obligation_batch(plan.owner_commit_batch)
    assert result.committed
    assert store.read_events()[-1].event_type == "gameplay.economy.scheduled_transfer_obligation_cancelled"
    assert EconomyProjector().rebuild(store.read_events()).balances == {
        "account:alice": 10,
        "account:bob": 0,
    }
    assert ObligationLifecycleProjection(
        (service.scheduled_account_transfer_obligation_registration(),)
    ).rebuild(store.read_events()).terminal[opened.obligation.obligation_id].status == "cancelled"


def test_economy_scheduled_transfer_expiry_is_terminal_without_moving_account_truth() -> None:
    store, service = _service_with_accounts()
    opened = service.open_scheduled_account_transfer_obligation(
        command_id="scheduled-transfer:expire:open",
        transfer_ref="scheduled-transfer:expire:1",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=4,
        due_tick=8,
        idempotency_key="scheduled-transfer:expire:open",
        causation_id="cause:scheduled-transfer:expire:open",
        correlation_id="corr:scheduled-transfer:expire:open",
        expected_revision=2,
    )
    assert opened.obligation is not None
    due = opened.obligation.model_copy(update={"status": "due"})

    coordinator = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(service.scheduled_account_transfer_obligation_registration(),),
    )
    plan = coordinator.plan_expire(
        obligation=due,
        fragment=service.build_scheduled_account_transfer_expiry_fragment(
            obligation=due,
            reason_ref="reason:expired",
        ),
        principal_ref=EconomyAuthorityService._PRINCIPAL,
        reason_ref="reason:expired",
    )

    assert plan.ready and plan.owner_commit_batch is not None
    result = service.commit_obligation_batch(plan.owner_commit_batch)
    assert result.committed
    assert store.read_events()[-1].event_type == "gameplay.economy.scheduled_transfer_obligation_expired"
    assert EconomyProjector().rebuild(store.read_events()).balances == {
        "account:alice": 10,
        "account:bob": 0,
    }
    assert ObligationLifecycleProjection(
        (service.scheduled_account_transfer_obligation_registration(),)
    ).rebuild(store.read_events()).terminal[due.obligation_id].status == "expired"


def test_economy_scheduled_transfer_open_replays_exact_duplicate_without_second_event() -> None:
    store, service = _service_with_accounts()
    first = service.open_scheduled_account_transfer_obligation(
        command_id="scheduled-transfer:duplicate:open",
        transfer_ref="scheduled-transfer:duplicate:1",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=4,
        due_tick=8,
        idempotency_key="scheduled-transfer:duplicate:open",
        causation_id="cause:scheduled-transfer:duplicate:open",
        correlation_id="corr:scheduled-transfer:duplicate:open",
        expected_revision=2,
    )
    before = store.export_snapshot()

    replayed = service.open_scheduled_account_transfer_obligation(
        command_id="scheduled-transfer:duplicate:open",
        transfer_ref="scheduled-transfer:duplicate:1",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=4,
        due_tick=8,
        idempotency_key="scheduled-transfer:duplicate:open",
        causation_id="cause:scheduled-transfer:duplicate:open",
        correlation_id="corr:scheduled-transfer:duplicate:open",
        expected_revision=2,
    )

    assert first.committed and replayed.committed
    assert replayed.append_result.idempotency_status == "duplicate_replayed"
    assert store.export_snapshot() == before


def test_economy_scheduled_transfer_due_rejects_stale_revision_without_write() -> None:
    store, service = _service_with_accounts()
    opened = service.open_scheduled_account_transfer_obligation(
        command_id="scheduled-transfer:stale:open",
        transfer_ref="scheduled-transfer:stale:1",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=4,
        due_tick=8,
        idempotency_key="scheduled-transfer:stale:open",
        causation_id="cause:scheduled-transfer:stale:open",
        correlation_id="corr:scheduled-transfer:stale:open",
        expected_revision=2,
    )
    assert opened.obligation is not None
    assert service.transfer(
        command_id="scheduled-transfer:stale:intervening-transfer",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=1,
        idempotency_key="scheduled-transfer:stale:intervening-transfer",
        causation_id="cause:scheduled-transfer:stale:intervening-transfer",
        correlation_id="corr:scheduled-transfer:stale:intervening-transfer",
        expected_revision=3,
    ).committed
    due = opened.obligation.model_copy(update={"status": "due"})
    before = store.export_snapshot()

    result = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(service.scheduled_account_transfer_obligation_registration(),),
    ).settle(
        obligation=due,
        fragments=(service.build_scheduled_account_transfer_settlement_fragment(obligation=due),),
        principal_ref=EconomyAuthorityService._PRINCIPAL,
    )

    assert not result.committed and result.error_code == "revision_conflict"
    assert store.export_snapshot() == before


def test_economy_scheduled_transfer_open_rejects_changed_duplicate_without_write() -> None:
    store, service = _service_with_accounts()
    assert service.open_scheduled_account_transfer_obligation(
        command_id="scheduled-transfer:changed-duplicate:open",
        transfer_ref="scheduled-transfer:changed-duplicate:1",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=4,
        due_tick=8,
        idempotency_key="scheduled-transfer:changed-duplicate:open",
        causation_id="cause:scheduled-transfer:changed-duplicate:open",
        correlation_id="corr:scheduled-transfer:changed-duplicate:open",
        expected_revision=2,
    ).committed
    before = store.export_snapshot()

    changed = service.open_scheduled_account_transfer_obligation(
        command_id="scheduled-transfer:changed-duplicate:open",
        transfer_ref="scheduled-transfer:changed-duplicate:1",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=5,
        due_tick=8,
        idempotency_key="scheduled-transfer:changed-duplicate:open",
        causation_id="cause:scheduled-transfer:changed-duplicate:open",
        correlation_id="corr:scheduled-transfer:changed-duplicate:open",
        expected_revision=2,
    )

    assert not changed.committed
    assert changed.append_result.failure is not None
    assert changed.append_result.failure.error_code == "idempotency_key_reused"
    assert store.export_snapshot() == before


def test_economy_scheduled_transfer_open_rejects_duplicate_transfer_source_without_write() -> None:
    store, service = _service_with_accounts()
    assert service.open_scheduled_account_transfer_obligation(
        command_id="scheduled-transfer:source-duplicate:open",
        transfer_ref="scheduled-transfer:source-duplicate:1",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=4,
        due_tick=8,
        idempotency_key="scheduled-transfer:source-duplicate:open",
        causation_id="cause:scheduled-transfer:source-duplicate:open",
        correlation_id="corr:scheduled-transfer:source-duplicate:open",
        expected_revision=2,
    ).committed
    before = store.export_snapshot()

    with pytest.raises(EconomyRuntimeError, match="economy_scheduled_transfer_duplicate"):
        service.open_scheduled_account_transfer_obligation(
            command_id="scheduled-transfer:source-duplicate:changed",
            transfer_ref="scheduled-transfer:source-duplicate:1",
            debit_account_id="account:alice",
            credit_account_id="account:bob",
            amount=4,
            due_tick=8,
            idempotency_key="scheduled-transfer:source-duplicate:changed",
            causation_id="cause:scheduled-transfer:source-duplicate:changed",
            correlation_id="corr:scheduled-transfer:source-duplicate:changed",
            expected_revision=3,
        )

    assert store.export_snapshot() == before


def test_economy_scheduled_transfer_due_rejects_due_time_insufficient_funds_without_write() -> None:
    store, service = _service_with_accounts()
    opened = service.open_scheduled_account_transfer_obligation(
        command_id="scheduled-transfer:unfunded:open",
        transfer_ref="scheduled-transfer:unfunded:1",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=4,
        due_tick=8,
        idempotency_key="scheduled-transfer:unfunded:open",
        causation_id="cause:scheduled-transfer:unfunded:open",
        correlation_id="corr:scheduled-transfer:unfunded:open",
        expected_revision=2,
    )
    assert opened.obligation is not None
    assert service.transfer(
        command_id="scheduled-transfer:unfunded:intervening",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=7,
        idempotency_key="scheduled-transfer:unfunded:intervening",
        causation_id="cause:scheduled-transfer:unfunded:intervening",
        correlation_id="corr:scheduled-transfer:unfunded:intervening",
        expected_revision=3,
    ).committed
    due = service.scheduled_account_transfer_obligation_for(
        obligation_id=opened.obligation.obligation_id
    ).model_copy(update={"status": "due"})
    before = store.export_snapshot()

    with pytest.raises(EconomyRuntimeError, match="economy_scheduled_transfer_unfunded"):
        service.build_scheduled_account_transfer_settlement_fragment(obligation=due)

    assert store.export_snapshot() == before


def test_economy_scheduled_transfer_due_rejects_forged_owner_fragment_without_write() -> None:
    store, service = _service_with_accounts()
    opened = service.open_scheduled_account_transfer_obligation(
        command_id="scheduled-transfer:forged-owner:open",
        transfer_ref="scheduled-transfer:forged-owner:1",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=4,
        due_tick=8,
        idempotency_key="scheduled-transfer:forged-owner:open",
        causation_id="cause:scheduled-transfer:forged-owner:open",
        correlation_id="corr:scheduled-transfer:forged-owner:open",
        expected_revision=2,
    )
    assert opened.obligation is not None
    due = opened.obligation.model_copy(update={"status": "due"})
    forged = service.build_scheduled_account_transfer_settlement_fragment(
        obligation=due
    ).model_copy(update={"owner_principal_ref": "actor:forged"})
    before = store.export_snapshot()

    result = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(service.scheduled_account_transfer_obligation_registration(),),
    ).settle(
        obligation=due,
        fragments=(forged,),
        principal_ref=EconomyAuthorityService._PRINCIPAL,
    )

    assert not result.committed and result.error_code == "owner_fragment_mismatch"
    assert store.export_snapshot() == before


def test_economy_scheduled_transfer_due_rejects_forged_fragment_revision_without_write() -> None:
    store, service = _service_with_accounts()
    opened = service.open_scheduled_account_transfer_obligation(
        command_id="scheduled-transfer:forged-revision:open",
        transfer_ref="scheduled-transfer:forged-revision:1",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=4,
        due_tick=8,
        idempotency_key="scheduled-transfer:forged-revision:open",
        causation_id="cause:scheduled-transfer:forged-revision:open",
        correlation_id="corr:scheduled-transfer:forged-revision:open",
        expected_revision=2,
    )
    assert opened.obligation is not None
    due = opened.obligation.model_copy(update={"status": "due"})
    forged = service.build_scheduled_account_transfer_settlement_fragment(
        obligation=due
    ).model_copy(update={"expected_revisions": {"gameplay:economy": 0}})
    before = store.export_snapshot()

    result = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(service.scheduled_account_transfer_obligation_registration(),),
    ).settle(
        obligation=due,
        fragments=(forged,),
        principal_ref=EconomyAuthorityService._PRINCIPAL,
    )

    assert not result.committed and result.error_code == "obligation_fragment_revision_mismatch"
    assert store.export_snapshot() == before


def test_economy_scheduled_transfer_due_rejects_forged_due_identity_without_write() -> None:
    store, service = _service_with_accounts()
    opened = service.open_scheduled_account_transfer_obligation(
        command_id="scheduled-transfer:forged-due:open",
        transfer_ref="scheduled-transfer:forged-due:1",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=4,
        due_tick=8,
        idempotency_key="scheduled-transfer:forged-due:open",
        causation_id="cause:scheduled-transfer:forged-due:open",
        correlation_id="corr:scheduled-transfer:forged-due:open",
        expected_revision=2,
    )
    assert opened.obligation is not None
    forged_due = opened.obligation.model_copy(update={"due_tick": 9, "status": "due"})
    before = store.export_snapshot()

    with pytest.raises(EconomyRuntimeError, match="economy_scheduled_transfer_obligation_invalid"):
        service.build_scheduled_account_transfer_settlement_fragment(obligation=forged_due)

    assert store.export_snapshot() == before


def test_economy_scheduled_transfer_receipt_and_outbox_are_authority_scoped() -> None:
    store, service = _service_with_accounts()
    opened = service.open_scheduled_account_transfer_obligation(
        command_id="scheduled-transfer:privacy-replay:open",
        transfer_ref="scheduled-transfer:privacy-replay:1",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=4,
        due_tick=8,
        idempotency_key="scheduled-transfer:privacy-replay:open",
        causation_id="cause:scheduled-transfer:privacy-replay:open",
        correlation_id="corr:scheduled-transfer:privacy-replay:open",
        expected_revision=2,
    )
    assert opened.obligation is not None
    due = opened.obligation.model_copy(update={"status": "due"})
    coordinator = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(service.scheduled_account_transfer_obligation_registration(),),
    )
    plan = coordinator.plan_settle(
        obligation=due,
        fragments=(service.build_scheduled_account_transfer_settlement_fragment(obligation=due),),
        principal_ref=EconomyAuthorityService._PRINCIPAL,
    )
    assert plan.ready and plan.owner_commit_batch is not None
    result = service.commit_obligation_batch(plan.owner_commit_batch)
    receipt = coordinator._receipt(result, due)
    assert result.committed
    assert receipt.committed_event_ids == tuple(result.committed_event_ids)
    assert receipt.audit_refs == (f"obligation:{due.obligation_id}",)
    assert {entry.audience for entry in store.list_outbox()[-3:]} == {"authority_only"}
    assert all(entry.payload_projection == {"obligation_id": due.obligation_id, "owner_ref": EconomyAuthorityService._PRINCIPAL} for entry in store.list_outbox()[-3:])
    assert coordinator.project_receipt(scope="public")["audit_refs"] == ()


def test_economy_scheduled_transfer_full_and_checkpoint_tail_replay_match() -> None:
    store, service = _service_with_accounts()
    opened = service.open_scheduled_account_transfer_obligation(
        command_id="scheduled-transfer:replay:open",
        transfer_ref="scheduled-transfer:replay:1",
        debit_account_id="account:alice",
        credit_account_id="account:bob",
        amount=4,
        due_tick=8,
        idempotency_key="scheduled-transfer:replay:open",
        causation_id="cause:scheduled-transfer:replay:open",
        correlation_id="corr:scheduled-transfer:replay:open",
        expected_revision=2,
    )
    assert opened.obligation is not None
    checkpoint = store.export_snapshot()
    due = opened.obligation.model_copy(update={"status": "due"})
    coordinator = ObligationSettlementCoordinator(
        store=store,
        lifecycle_registrations=(service.scheduled_account_transfer_obligation_registration(),),
    )
    plan = coordinator.plan_settle(
        obligation=due,
        fragments=(service.build_scheduled_account_transfer_settlement_fragment(obligation=due),),
        principal_ref=EconomyAuthorityService._PRINCIPAL,
    )
    assert plan.ready and plan.owner_commit_batch is not None
    assert service.commit_obligation_batch(plan.owner_commit_batch).committed
    tail_store = GameplayEventStore.from_snapshot(checkpoint)
    assert tail_store.append_batch(store.read_transactions()[-1]).committed

    assert EconomyProjector().rebuild(store.read_events()).balances == EconomyProjector().rebuild(
        tail_store.read_events()
    ).balances == {"account:alice": 6, "account:bob": 4}
    assert coordinator.replay().projection_hash == coordinator.replay(checkpoint_at=3).projection_hash
