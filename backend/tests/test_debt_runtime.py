from __future__ import annotations

import pytest

from app.gameplay.debt_runtime import DebtAuthorityService, DebtProjector, DebtRuntimeError
from app.gameplay.economy_runtime import EconomyAuthorityService, EconomyProjector
from app.gameplay.event_store import GameplayEventStore


CREDITOR = "actor:creditor"
DEBTOR = "actor:debtor"
CONTRACT = "contract:bridge-loan"
DEBT = "debt:bridge-loan"


def _setup() -> tuple[GameplayEventStore, DebtAuthorityService]:
    store = GameplayEventStore()
    accounts = EconomyAuthorityService(store=store)
    accounts.open_account(command_id="cmd:creditor-account", account_id="account:creditor", owner_ref=CREDITOR, currency_ref="coin", initial_balance=20, idempotency_key="creditor-account", causation_id="cause", correlation_id="corr")
    accounts.open_account(command_id="cmd:debtor-account", account_id="account:debtor", owner_ref=DEBTOR, currency_ref="coin", initial_balance=1, idempotency_key="debtor-account", causation_id="cause", correlation_id="corr")
    return store, DebtAuthorityService(store=store)


def _issue(service: DebtAuthorityService, *, command_id: str = "cmd:issue", idempotency_key: str = "issue"):
    return service.issue_simple_debt(
        command_id=command_id,
        contract_id=CONTRACT,
        debt_id=DEBT,
        creditor_ref=CREDITOR,
        debtor_ref=DEBTOR,
        creditor_account_id="account:creditor",
        debtor_account_id="account:debtor",
        currency_ref="coin",
        principal_amount=8,
        idempotency_key=idempotency_key,
        causation_id="cause",
        correlation_id="corr",
    )


def _pay(service: DebtAuthorityService, amount: int, *, command_id: str, idempotency_key: str):
    return service.pay_debt(
        command_id=command_id,
        debt_id=DEBT,
        debtor_account_id="account:debtor",
        creditor_account_id="account:creditor",
        amount=amount,
        idempotency_key=idempotency_key,
        causation_id="cause",
        correlation_id="corr",
    )


def test_debt_issue_delivers_principal_with_contract_claim_and_record_in_one_batch() -> None:
    store, service = _setup()
    result = _issue(service)
    assert result.committed
    transaction = store.read_transactions()[-1]
    assert [event.event_type for event in transaction.events] == [
        "gameplay.economy.account_debited",
        "gameplay.economy.account_credited",
        "gameplay.contract.simple_debt_created",
        "gameplay.debt.claim_issued",
        "gameplay.commerce.debt_issued_settled",
    ]
    assert EconomyProjector().rebuild(store.read_events()).balances == {"account:creditor": 12, "account:debtor": 9}
    projection = DebtProjector().rebuild(store.read_events())
    assert projection.contracts[CONTRACT].status == "active"
    assert projection.claims[DEBT].outstanding_amount == 8
    assert projection.transactions["debt-issue:cmd:issue"].settlement_transaction_id == result.transaction_id


def test_partial_then_full_debt_payment_updates_outstanding_and_settles_contract() -> None:
    store, service = _setup()
    _issue(service)
    partial = _pay(service, 3, command_id="cmd:partial", idempotency_key="partial")
    assert partial.committed
    after_partial = DebtProjector().rebuild(store.read_events())
    assert after_partial.claims[DEBT].outstanding_amount == 5
    assert after_partial.claims[DEBT].status == "active"
    assert after_partial.contracts[CONTRACT].status == "active"

    final = _pay(service, 5, command_id="cmd:final", idempotency_key="final")
    assert final.committed
    transaction = store.read_transactions()[-1]
    assert [event.event_type for event in transaction.events] == [
        "gameplay.economy.account_debited",
        "gameplay.economy.account_credited",
        "gameplay.debt.payment_applied",
        "gameplay.debt.claim_satisfied",
        "gameplay.contract.simple_debt_fulfilled",
        "gameplay.commerce.debt_payment_settled",
    ]
    settled = DebtProjector().rebuild(store.read_events())
    assert settled.claims[DEBT].outstanding_amount == 0
    assert settled.claims[DEBT].status == "satisfied"
    assert settled.contracts[CONTRACT].status == "fulfilled"


def test_overpayment_writes_nothing_and_retry_does_not_double_pay() -> None:
    store, service = _setup()
    _issue(service)
    before = store.read_events()
    with pytest.raises(DebtRuntimeError, match="economy_payment_exceeds_outstanding"):
        _pay(service, 9, command_id="cmd:too-much", idempotency_key="too-much")
    assert store.read_events() == before

    first = _pay(service, 4, command_id="cmd:pay", idempotency_key="pay")
    replay = _pay(service, 4, command_id="cmd:pay", idempotency_key="pay")
    assert first.committed and replay.committed
    assert replay.idempotency_status == "duplicate_replayed"
    assert DebtProjector().rebuild(store.read_events()).claims[DEBT].outstanding_amount == 4


def test_policy_cancellation_is_a_new_event_and_blocks_later_payment() -> None:
    store, service = _setup()
    _issue(service)
    before_balances = EconomyProjector().rebuild(store.read_events()).balances
    cancelled = service.cancel_debt_by_policy(
        command_id="cmd:cancel",
        debt_id=DEBT,
        authority_ref="authority:collections",
        reason="settlement_error",
        idempotency_key="cancel",
        causation_id="cause",
        correlation_id="corr",
    )
    assert cancelled.committed
    assert [event.event_type for event in store.read_transactions()[-1].events] == [
        "gameplay.debt.claim_cancelled",
        "gameplay.contract.simple_debt_cancelled",
        "gameplay.commerce.debt_cancelled_settled",
    ]
    projection = DebtProjector().rebuild(store.read_events())
    assert projection.claims[DEBT].status == "cancelled"
    assert projection.claims[DEBT].outstanding_amount == 0
    assert projection.contracts[CONTRACT].status == "cancelled"
    assert EconomyProjector().rebuild(store.read_events()).balances == before_balances
    with pytest.raises(DebtRuntimeError, match="economy_debt_not_active"):
        _pay(service, 1, command_id="cmd:after-cancel", idempotency_key="after-cancel")


def test_payment_correction_reverses_funds_and_restores_outstanding_once() -> None:
    store, service = _setup()
    _issue(service)
    _pay(service, 3, command_id="cmd:partial", idempotency_key="partial")
    corrected = service.correct_debt_payment_by_policy(
        command_id="cmd:correct",
        debt_id=DEBT,
        original_payment_record_id="debt-payment:cmd:partial",
        debtor_account_id="account:debtor",
        creditor_account_id="account:creditor",
        authority_ref="authority:collections",
        reason="duplicate_receipt",
        idempotency_key="correct",
        causation_id="cause",
        correlation_id="corr",
    )
    assert corrected.committed
    assert [event.event_type for event in store.read_transactions()[-1].events] == [
        "gameplay.economy.account_debited",
        "gameplay.economy.account_credited",
        "gameplay.debt.payment_corrected",
        "gameplay.commerce.debt_payment_corrected_settled",
    ]
    assert EconomyProjector().rebuild(store.read_events()).balances == {"account:creditor": 12, "account:debtor": 9}
    projection = DebtProjector().rebuild(store.read_events())
    assert projection.claims[DEBT].outstanding_amount == 8
    assert projection.claims[DEBT].status == "active"
    assert projection.corrections["debt-payment:cmd:partial"] == "debt-correction:cmd:correct"

    replay = service.correct_debt_payment_by_policy(command_id="cmd:correct", debt_id=DEBT, original_payment_record_id="debt-payment:cmd:partial", debtor_account_id="account:debtor", creditor_account_id="account:creditor", authority_ref="authority:collections", reason="duplicate_receipt", idempotency_key="correct", causation_id="cause", correlation_id="corr")
    assert replay.idempotency_status == "duplicate_replayed"
    before = store.read_events()
    with pytest.raises(DebtRuntimeError, match="economy_payment_already_corrected"):
        service.correct_debt_payment_by_policy(command_id="cmd:second-correct", debt_id=DEBT, original_payment_record_id="debt-payment:cmd:partial", debtor_account_id="account:debtor", creditor_account_id="account:creditor", authority_ref="authority:collections", reason="again", idempotency_key="second-correct", causation_id="cause", correlation_id="corr")
    assert store.read_events() == before


def test_final_payment_correction_reopens_claim_and_contract_once() -> None:
    store, service = _setup()
    _issue(service)
    _pay(service, 8, command_id="cmd:final", idempotency_key="final")

    corrected = service.correct_debt_payment_by_policy(
        command_id="cmd:correct-final",
        debt_id=DEBT,
        original_payment_record_id="debt-payment:cmd:final",
        debtor_account_id="account:debtor",
        creditor_account_id="account:creditor",
        authority_ref="authority:collections",
        reason="payment_reversed",
        idempotency_key="correct-final",
        causation_id="cause",
        correlation_id="corr",
    )

    assert corrected.committed
    assert [event.event_type for event in store.read_transactions()[-1].events] == [
        "gameplay.economy.account_debited",
        "gameplay.economy.account_credited",
        "gameplay.contract.simple_debt_reopened",
        "gameplay.debt.claim_reopened",
        "gameplay.debt.payment_corrected",
        "gameplay.commerce.debt_payment_corrected_settled",
    ]
    assert EconomyProjector().rebuild(store.read_events()).balances == {
        "account:creditor": 12,
        "account:debtor": 9,
    }
    projection = DebtProjector().rebuild(store.read_events())
    assert projection.contracts[CONTRACT].status == "active"
    assert projection.claims[DEBT].status == "active"
    assert projection.claims[DEBT].outstanding_amount == 8
    assert projection.corrections["debt-payment:cmd:final"] == "debt-correction:cmd:correct-final"

    replay = service.correct_debt_payment_by_policy(
        command_id="cmd:correct-final",
        debt_id=DEBT,
        original_payment_record_id="debt-payment:cmd:final",
        debtor_account_id="account:debtor",
        creditor_account_id="account:creditor",
        authority_ref="authority:collections",
        reason="payment_reversed",
        idempotency_key="correct-final",
        causation_id="cause",
        correlation_id="corr",
    )
    assert replay.idempotency_status == "duplicate_replayed"


def test_payment_correction_cannot_reopen_cancelled_debt() -> None:
    store, service = _setup()
    _issue(service)
    _pay(service, 3, command_id="cmd:partial", idempotency_key="partial")
    service.cancel_debt_by_policy(
        command_id="cmd:cancel",
        debt_id=DEBT,
        authority_ref="authority:collections",
        reason="waived",
        idempotency_key="cancel",
        causation_id="cause",
        correlation_id="corr",
    )

    before = store.read_events()
    with pytest.raises(DebtRuntimeError, match="economy_debt_not_active"):
        service.correct_debt_payment_by_policy(
            command_id="cmd:correct-cancelled",
            debt_id=DEBT,
            original_payment_record_id="debt-payment:cmd:partial",
            debtor_account_id="account:debtor",
            creditor_account_id="account:creditor",
            authority_ref="authority:collections",
            reason="late_error",
            idempotency_key="correct-cancelled",
            causation_id="cause",
            correlation_id="corr",
        )
    assert store.read_events() == before


def test_policy_cancellation_reversal_restores_pinned_outstanding_without_moving_funds() -> None:
    store, service = _setup()
    _issue(service)
    _pay(service, 3, command_id="cmd:partial", idempotency_key="partial")
    service.cancel_debt_by_policy(
        command_id="cmd:cancel",
        debt_id=DEBT,
        authority_ref="authority:collections",
        reason="waived",
        idempotency_key="cancel",
        causation_id="cause",
        correlation_id="corr",
    )
    balances_before = EconomyProjector().rebuild(store.read_events()).balances

    reversed_cancellation = service.reverse_debt_cancellation_by_policy(
        command_id="cmd:reverse-cancel",
        debt_id=DEBT,
        original_cancellation_record_id="debt-cancel:cmd:cancel",
        authority_ref="authority:collections",
        reason="waiver_revoked",
        idempotency_key="reverse-cancel",
        causation_id="cause",
        correlation_id="corr",
    )

    assert reversed_cancellation.committed
    assert [event.event_type for event in store.read_transactions()[-1].events] == [
        "gameplay.contract.simple_debt_cancellation_reversed",
        "gameplay.debt.claim_cancellation_reversed",
        "gameplay.commerce.debt_cancellation_reversed",
    ]
    assert EconomyProjector().rebuild(store.read_events()).balances == balances_before
    projection = DebtProjector().rebuild(store.read_events())
    assert projection.contracts[CONTRACT].status == "active"
    assert projection.claims[DEBT].status == "active"
    assert projection.claims[DEBT].outstanding_amount == 5
    assert projection.cancellation_reversals["debt-cancel:cmd:cancel"] == "debt-cancellation-reversal:cmd:reverse-cancel"

    replay = service.reverse_debt_cancellation_by_policy(
        command_id="cmd:reverse-cancel",
        debt_id=DEBT,
        original_cancellation_record_id="debt-cancel:cmd:cancel",
        authority_ref="authority:collections",
        reason="waiver_revoked",
        idempotency_key="reverse-cancel",
        causation_id="cause",
        correlation_id="corr",
    )
    assert replay.idempotency_status == "duplicate_replayed"
    before_second_reversal = store.read_events()
    with pytest.raises(DebtRuntimeError, match="economy_cancellation_already_reversed"):
        service.reverse_debt_cancellation_by_policy(
            command_id="cmd:second-reverse",
            debt_id=DEBT,
            original_cancellation_record_id="debt-cancel:cmd:cancel",
            authority_ref="authority:collections",
            reason="again",
            idempotency_key="second-reverse",
            causation_id="cause",
            correlation_id="corr",
        )
    assert store.read_events() == before_second_reversal
