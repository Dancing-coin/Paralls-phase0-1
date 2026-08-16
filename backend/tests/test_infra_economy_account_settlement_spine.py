from __future__ import annotations

import pytest

from app.gameplay.economy_privacy_views import EconomyPrivacyQueryService, EconomyPrivacyViewError
from app.gameplay.economy_runtime import EconomyAuthorityService, EconomyProjector, EconomyRuntimeError
from app.gameplay.event_store import GameplayEventStore


def _service() -> tuple[GameplayEventStore, EconomyAuthorityService]:
    store = GameplayEventStore()
    return store, EconomyAuthorityService(store=store)


def _open_accounts(service: EconomyAuthorityService) -> None:
    service.open_account(
        command_id="cmd:open:alice", account_id="account:alice", owner_ref="actor:alice",
        currency_ref="currency:coin", initial_balance=10, idempotency_key="open:alice",
        causation_id="cause:open", correlation_id="corr:open", expected_revision=0,
    )
    service.open_account(
        command_id="cmd:open:bob", account_id="account:bob", owner_ref="actor:bob",
        currency_ref="currency:coin", initial_balance=0, idempotency_key="open:bob",
        causation_id="cause:open", correlation_id="corr:open", expected_revision=1,
    )


def _transfer(service: EconomyAuthorityService) -> object:
    return service.transfer(
        command_id="cmd:transfer", debit_account_id="account:alice", credit_account_id="account:bob",
        amount=4, idempotency_key="transfer", causation_id="cause:transfer",
        correlation_id="corr:transfer", expected_revision=2,
    )


def test_account_transfer_uses_formal_command_envelope_settlement_plan_and_one_append_batch() -> None:
    store, service = _service()
    _open_accounts(service)
    result = _transfer(service)
    assert result.committed
    transaction = store.read_transactions()[-1]
    assert transaction.command_id == "cmd:transfer"
    assert transaction.transaction_id == "transaction:cmd:transfer"
    assert transaction.idempotency_record.principal_ref == "actor_gameplay.economy_domain"
    assert transaction.expected_stream_revisions == {"gameplay:economy": 2}
    assert transaction.read_stream_revisions == {"gameplay:economy": 2}
    assert [event.visibility_policy for event in transaction.events] == ["authority_only", "authority_only"]


def test_account_transfer_outbox_is_authority_scoped_and_redacted() -> None:
    store, service = _service()
    _open_accounts(service)
    _transfer(service)
    assert [entry.audience for entry in store.list_outbox()[-2:]] == ["authority:economy", "authority:economy"]
    assert all("amount" not in entry.payload_projection for entry in store.list_outbox()[-2:])


def test_budget_reservation_uses_formal_spine_and_redacted_authority_outbox() -> None:
    store, service = _service()
    _open_accounts(service)
    result = service.reserve_budget(
        command_id="cmd:reserve", reservation_ref="reservation:alice:materials",
        account_id="account:alice", amount_minor=3, idempotency_key="reserve",
        causation_id="cause:reserve", correlation_id="corr:reserve", expected_revision=2,
    )
    transaction = store.read_transactions()[-1]
    outbox = store.list_outbox()[-1]

    assert result.committed
    assert transaction.transaction_id == "transaction:cmd:reserve"
    assert transaction.expected_stream_revisions == {"gameplay:economy": 2}
    assert transaction.read_stream_revisions == {"gameplay:economy": 2}
    assert [event.event_type for event in transaction.events] == ["gameplay.economy.budget_reserved"]
    assert outbox.audience == "authority:economy"
    assert outbox.payload_projection == {"account_id": "account:alice", "event_type": "gameplay.economy.budget_reserved"}


def test_account_transfer_receipt_is_derived_from_the_append_result() -> None:
    _, service = _service()
    _open_accounts(service)
    result = _transfer(service)
    receipt = service.account_settlement_receipt_for(result=result, privacy_scope="authority")
    assert receipt.transaction_id == result.transaction_id
    assert receipt.committed_event_ids == tuple(result.committed_event_ids)
    assert receipt.zero_write is False


def test_account_transfer_duplicate_replays_without_double_debit() -> None:
    store, service = _service()
    _open_accounts(service)
    first = _transfer(service)
    duplicate = service.transfer(
        command_id="cmd:transfer", debit_account_id="account:alice", credit_account_id="account:bob",
        amount=4, idempotency_key="transfer", causation_id="cause:transfer",
        correlation_id="corr:transfer", expected_revision=2,
    )
    assert first.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert EconomyProjector().rebuild(store.read_events()).balances == {"account:alice": 6, "account:bob": 4}


def test_account_transfer_changed_duplicate_is_zero_write() -> None:
    store, service = _service()
    _open_accounts(service)
    _transfer(service)
    before_events, before_outbox = store.read_events(), store.list_outbox()
    changed = service.transfer(
        command_id="cmd:transfer:changed", debit_account_id="account:alice", credit_account_id="account:bob",
        amount=3, idempotency_key="transfer", causation_id="cause:transfer",
        correlation_id="corr:transfer", expected_revision=4,
    )

    assert not changed.committed and changed.failure is not None
    assert changed.failure.error_code == "idempotency_key_reused"
    assert store.read_events() == before_events and store.list_outbox() == before_outbox


def test_stale_account_revision_is_zero_write() -> None:
    store, service = _service()
    _open_accounts(service)
    before_events, before_outbox = store.read_events(), store.list_outbox()
    stale = service.transfer(
        command_id="cmd:stale", debit_account_id="account:alice", credit_account_id="account:bob",
        amount=1, idempotency_key="stale", causation_id="cause:stale",
        correlation_id="corr:stale", expected_revision=1,
    )
    assert not stale.committed and stale.failure is not None
    assert stale.failure.error_code == "revision_conflict"
    assert store.read_events() == before_events and store.list_outbox() == before_outbox


def test_insufficient_account_funds_are_zero_write() -> None:
    store, service = _service()
    _open_accounts(service)
    before_events, before_outbox = store.read_events(), store.list_outbox()
    with pytest.raises(EconomyRuntimeError, match="economy_insufficient_funds"):
        service.transfer(
            command_id="cmd:insufficient", debit_account_id="account:alice", credit_account_id="account:bob",
            amount=11, idempotency_key="insufficient", causation_id="cause:insufficient",
            correlation_id="corr:insufficient", expected_revision=2,
        )
    assert store.read_events() == before_events and store.list_outbox() == before_outbox


def test_account_projection_full_and_checkpoint_tail_replay_match() -> None:
    store, service = _service()
    _open_accounts(service)
    checkpoint_snapshot = store.export_snapshot()
    service.transfer(
        command_id="cmd:transfer", debit_account_id="account:alice", credit_account_id="account:bob",
        amount=4, idempotency_key="transfer", causation_id="cause:transfer",
        correlation_id="corr:transfer", expected_revision=2,
    )
    tail_store = GameplayEventStore.from_snapshot(checkpoint_snapshot)
    tail_result = tail_store.append_batch(store.read_transactions()[-1])
    assert tail_result.committed
    assert EconomyProjector().rebuild(store.read_events()).balances == EconomyProjector().rebuild(
        tail_store.read_events()
    ).balances == {"account:alice": 6, "account:bob": 4}



def test_account_projection_is_visible_only_to_owner_or_authority() -> None:
    store, service = _service()
    _open_accounts(service)
    _transfer(service)
    views = EconomyPrivacyQueryService(store=store, authority_principals={"authority:economy"})
    assert views.account_balance_view(account_id="account:alice", principal_ref="actor:alice").balance == 6
    assert views.account_balance_view(account_id="account:alice", principal_ref="authority:economy").balance == 6
    with pytest.raises(EconomyPrivacyViewError, match="economy_account_visibility_denied"):
        views.account_balance_view(account_id="account:alice", principal_ref="actor:eve")


def test_account_receipt_rejects_non_authority_scope_without_writes() -> None:
    store, service = _service()
    _open_accounts(service)
    _transfer(service)
    before_events, before_outbox = store.read_events(), store.list_outbox()
    with pytest.raises(EconomyRuntimeError, match="economy_account_receipt_scope_denied"):
        service.account_settlement_receipt_for(
            result=store.get_by_idempotency("actor_gameplay.economy_domain", "transfer"),
            privacy_scope="public",
        )
    assert store.read_events() == before_events and store.list_outbox() == before_outbox
