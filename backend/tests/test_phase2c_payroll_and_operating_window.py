from __future__ import annotations

import pytest

from app.gameplay.econ1_economy_runtime import EconomyAuthority, OperatingWindow, WageAccrual
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.economy_runtime import EconomyAuthorityService, EconomyProjector


def test_only_verified_completed_evidence_accrues_wage_and_window_commands_are_explicit() -> None:
    store = GameplayEventStore(); authority = EconomyAuthority(store=store)
    window = authority.open_window(OperatingWindow(window_ref="window:1", organization_ref="org:bakery", opens_at_tick=1, closes_at_tick=5, policy_revision="policy:1", source_revision="source:1"), command_id="window:open", idempotency_key="window:open", causation_id="cause", correlation_id="corr")
    assert window.committed
    accrual = WageAccrual(accrual_ref="accrual:1", organization_ref="org:bakery", payee_actor_ref="character:char_b", work_evidence_refs=("evidence:verified",), wage_policy_revision="wage:1", amount=10, status="accrued")
    result = authority.accrue_wage(accrual, completed_evidence_refs={"evidence:verified"}, command_id="wage:accrue", idempotency_key="wage:accrue", causation_id="cause", correlation_id="corr")
    assert result.committed
    assert authority.close_window(
        OperatingWindow(window_ref="window:1", organization_ref="org:bakery", opens_at_tick=1, closes_at_tick=5, policy_revision="policy:1", source_revision="source:1", status="open"),
        command_id="window:close", idempotency_key="window:close", causation_id="cause", correlation_id="corr",
    ).committed
    with pytest.raises(ValueError, match="operating_window_closed"):
        authority.close_window(
            OperatingWindow(window_ref="window:1", organization_ref="org:bakery", opens_at_tick=1, closes_at_tick=5, policy_revision="policy:1", source_revision="source:1", status="open"),
            command_id="window:close:duplicate", idempotency_key="window:close:duplicate", causation_id="cause", correlation_id="corr",
        )


def test_unverified_evidence_and_insufficient_funds_preserve_zero_write_or_overdue() -> None:
    store = GameplayEventStore(); authority = EconomyAuthority(store=store)
    accrual = WageAccrual(accrual_ref="accrual:bad", organization_ref="org:bakery", payee_actor_ref="character:char_b", work_evidence_refs=("evidence:actor",), wage_policy_revision="wage:1", amount=10)
    with pytest.raises(ValueError, match="work_evidence_invalid"):
        authority.accrue_wage(accrual, completed_evidence_refs=set(), command_id="bad", idempotency_key="bad", causation_id="cause", correlation_id="corr")
    assert store.read_events() == []
    overdue = authority.mark_overdue(accrual, command_id="wage:overdue", idempotency_key="wage:overdue", causation_id="cause", correlation_id="corr")
    assert overdue.committed


def test_verified_wage_payment_commits_account_transfer_and_paid_fact_atomically() -> None:
    store = GameplayEventStore()
    accounts = EconomyAuthorityService(store=store)
    for account_id, owner_ref, balance in (("account:bakery", "org:bakery", 100), ("account:char_b", "character:char_b", 0)):
        assert accounts.open_account(
            command_id=f"open:{account_id}", account_id=account_id, owner_ref=owner_ref,
            currency_ref="currency:coin", initial_balance=balance,
            idempotency_key=f"open:{account_id}", causation_id="cause", correlation_id="corr",
        ).committed
    authority = EconomyAuthority(store=store)
    accrual = WageAccrual(
        accrual_ref="accrual:paid", organization_ref="org:bakery", payee_actor_ref="character:char_b",
        work_evidence_refs=("evidence:verified",), wage_policy_revision="wage:1", amount=10,
    )
    result = authority.pay_wage(
        accrual, payer_account_id="account:bakery", payee_account_id="account:char_b",
        command_id="wage:pay", idempotency_key="wage:pay", causation_id="cause", correlation_id="corr",
    )
    assert result.committed
    projection = EconomyProjector().rebuild(store.read_events())
    assert projection.balances["account:bakery"] == 90
    assert projection.balances["account:char_b"] == 10
    assert [event.event_type for event in store.read_events() if event.event_type == "gameplay.economy.wage_paid"] == ["gameplay.economy.wage_paid"]


def test_wage_payment_insufficient_funds_is_zero_write_and_can_become_overdue() -> None:
    store = GameplayEventStore()
    accounts = EconomyAuthorityService(store=store)
    for account_id, owner_ref in (("account:bakery", "org:bakery"), ("account:char_b", "character:char_b")):
        assert accounts.open_account(
            command_id=f"open:{account_id}", account_id=account_id, owner_ref=owner_ref,
            currency_ref="currency:coin", initial_balance=0,
            idempotency_key=f"open:{account_id}", causation_id="cause", correlation_id="corr",
        ).committed
    authority = EconomyAuthority(store=store)
    accrual = WageAccrual(
        accrual_ref="accrual:overdue", organization_ref="org:bakery", payee_actor_ref="character:char_b",
        work_evidence_refs=("evidence:verified",), wage_policy_revision="wage:1", amount=10,
    )
    before = len(store.read_events())
    with pytest.raises(ValueError, match="economy_insufficient_funds"):
        authority.pay_wage(
            accrual, payer_account_id="account:bakery", payee_account_id="account:char_b",
            command_id="wage:pay-fail", idempotency_key="wage:pay-fail", causation_id="cause", correlation_id="corr",
        )
    assert len(store.read_events()) == before
    assert authority.mark_overdue(
        accrual, command_id="wage:overdue", idempotency_key="wage:overdue", causation_id="cause", correlation_id="corr",
    ).committed
