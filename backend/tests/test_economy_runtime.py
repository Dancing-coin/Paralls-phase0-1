from __future__ import annotations

import pytest

from app.gameplay.economy_runtime import EconomyAuthorityService, EconomyProjector, EconomyRuntimeError
from app.gameplay.event_store import GameplayEventStore


def test_transfer_preserves_balances_in_one_batch() -> None:
    store = GameplayEventStore()
    service = EconomyAuthorityService(store=store)
    service.open_account(command_id="cmd:alice", account_id="account:alice", owner_ref="actor:alice", currency_ref="coin", initial_balance=10, idempotency_key="alice", causation_id="cause", correlation_id="corr")
    service.open_account(command_id="cmd:bob", account_id="account:bob", owner_ref="actor:bob", currency_ref="coin", initial_balance=0, idempotency_key="bob", causation_id="cause", correlation_id="corr")
    result = service.transfer(command_id="cmd:pay", debit_account_id="account:alice", credit_account_id="account:bob", amount=4, idempotency_key="pay", causation_id="cause", correlation_id="corr")
    assert result.committed
    balances = EconomyProjector().rebuild(store.read_events()).balances
    assert balances == {"account:alice": 6, "account:bob": 4}


def test_insufficient_balance_writes_nothing() -> None:
    store = GameplayEventStore()
    service = EconomyAuthorityService(store=store)
    service.open_account(command_id="cmd:alice", account_id="account:alice", owner_ref="actor:alice", currency_ref="coin", initial_balance=1, idempotency_key="alice", causation_id="cause", correlation_id="corr")
    service.open_account(command_id="cmd:bob", account_id="account:bob", owner_ref="actor:bob", currency_ref="coin", initial_balance=0, idempotency_key="bob", causation_id="cause", correlation_id="corr")
    before = store.read_events()
    with pytest.raises(EconomyRuntimeError, match="economy_insufficient_funds"):
        service.transfer(command_id="cmd:pay", debit_account_id="account:alice", credit_account_id="account:bob", amount=2, idempotency_key="pay", causation_id="cause", correlation_id="corr")
    assert store.read_events() == before


def test_transfer_idempotency_does_not_double_debit() -> None:
    store = GameplayEventStore()
    service = EconomyAuthorityService(store=store)
    service.open_account(command_id="cmd:alice", account_id="account:alice", owner_ref="actor:alice", currency_ref="coin", initial_balance=5, idempotency_key="alice", causation_id="cause", correlation_id="corr")
    service.open_account(command_id="cmd:bob", account_id="account:bob", owner_ref="actor:bob", currency_ref="coin", initial_balance=0, idempotency_key="bob", causation_id="cause", correlation_id="corr")
    first = service.transfer(command_id="cmd:pay", debit_account_id="account:alice", credit_account_id="account:bob", amount=2, idempotency_key="pay", causation_id="cause", correlation_id="corr")
    replay = service.transfer(command_id="cmd:pay", debit_account_id="account:alice", credit_account_id="account:bob", amount=2, idempotency_key="pay", causation_id="cause", correlation_id="corr")
    assert first.committed and replay.committed
    assert replay.idempotency_status == "duplicate_replayed"
    assert EconomyProjector().rebuild(store.read_events()).balances == {"account:alice": 3, "account:bob": 2}
