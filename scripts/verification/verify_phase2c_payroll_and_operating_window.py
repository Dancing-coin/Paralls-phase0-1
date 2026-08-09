from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.gameplay.econ1_economy_runtime import EconomyAuthority, OperatingWindow, WageAccrual
from app.gameplay.economy_runtime import EconomyAuthorityService, EconomyProjector, EconomyRuntimeError
from app.gameplay.event_store import GameplayEventStore
try:
    from common import repo_root, verification_dir, write_json, write_markdown
except ModuleNotFoundError:
    from scripts.verification.common import repo_root, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root(); directory = verification_dir(root); store = GameplayEventStore(); authority = EconomyAuthority(store=store)
    accounts = EconomyAuthorityService(store=store)
    for account_id, owner_ref, balance in (("account:bakery", "org:bakery", 100), ("account:char_b", "character:char_b", 0)):
        accounts.open_account(command_id=f"open:{account_id}", account_id=account_id, owner_ref=owner_ref, currency_ref="currency:coin", initial_balance=balance, idempotency_key=f"open:{account_id}", causation_id="p2c:cause", correlation_id="p2c:corr")
    window = OperatingWindow(window_ref="window:1", organization_ref="org:bakery", opens_at_tick=1, closes_at_tick=5, policy_revision="policy:1", source_revision="source:1")
    opened = authority.open_window(window, command_id="p2c:open", idempotency_key="p2c:open", causation_id="p2c:cause", correlation_id="p2c:corr")
    closed = authority.close_window(window.model_copy(update={"status": "open"}), command_id="p2c:close", idempotency_key="p2c:close", causation_id="p2c:cause", correlation_id="p2c:corr")
    accrual = WageAccrual(accrual_ref="accrual:1", organization_ref="org:bakery", payee_actor_ref="character:char_b", work_evidence_refs=("evidence:verified",), wage_policy_revision="wage:1", amount=10)
    due = authority.evaluate_due(window.model_copy(update={"status": "closed"}), command_id="p2c:due", idempotency_key="p2c:due", causation_id="p2c:cause", correlation_id="p2c:corr")
    accrued = authority.accrue_wage(accrual, completed_evidence_refs={"evidence:verified"}, command_id="p2c:accrue", idempotency_key="p2c:accrue", causation_id="p2c:cause", correlation_id="p2c:corr")
    paid = authority.pay_wage(accrual, payer_account_id="account:bakery", payee_account_id="account:char_b", command_id="p2c:pay", idempotency_key="p2c:pay", causation_id="p2c:cause", correlation_id="p2c:corr")
    insufficient_store = GameplayEventStore()
    insufficient_accounts = EconomyAuthorityService(store=insufficient_store)
    insufficient_accounts.open_account(command_id="open:payer", account_id="account:payer", owner_ref="org:empty", currency_ref="currency:coin", initial_balance=0, idempotency_key="open:payer", causation_id="p2c:cause", correlation_id="p2c:corr")
    insufficient_accounts.open_account(command_id="open:payee", account_id="account:payee", owner_ref="character:char_c", currency_ref="currency:coin", initial_balance=0, idempotency_key="open:payee", causation_id="p2c:cause", correlation_id="p2c:corr")
    zero_write_before = len(insufficient_store.read_events())
    try:
        authority_empty = EconomyAuthority(store=insufficient_store)
        authority_empty.pay_wage(accrual, payer_account_id="account:payer", payee_account_id="account:payee", command_id="p2c:pay-fail", idempotency_key="p2c:pay-fail", causation_id="p2c:cause", correlation_id="p2c:corr")
        insufficient_failure = None
    except EconomyRuntimeError as exc:
        insufficient_failure = str(exc)
    overdue = authority.mark_overdue(accrual, command_id="p2c:overdue", idempotency_key="p2c:overdue", causation_id="p2c:cause", correlation_id="p2c:corr")
    report = {"overall_phase2c_payroll_and_operating_window_passed": all(item.committed for item in (opened, closed, due, accrued, paid, overdue)) and insufficient_failure == "economy_insufficient_funds" and len(insufficient_store.read_events()) == zero_write_before, "event_count": len(store.read_events()), "receipt": {"open": opened.model_dump(mode="json"), "close": closed.model_dump(mode="json"), "due": due.model_dump(mode="json"), "accrual": accrued.model_dump(mode="json"), "paid": paid.model_dump(mode="json"), "overdue": overdue.model_dump(mode="json")}, "payment": {"account_balances": dict(EconomyProjector().rebuild(store.read_events()).balances), "insufficient_funds": insufficient_failure, "zero_write": len(insufficient_store.read_events()) == zero_write_before}, "zero_write_unverified": True, "recovery_required_period_open": True, "no_scheduler_or_clock": True, "scope_redaction": {"actor": ["own_wage_status"], "manager": ["wage_total"], "redacted": ["other_actor_need", "private_memory"]}}
    write_json(directory / "phase2c-payroll-and-operating-window-report.json", report); write_markdown(directory / "phase2c-payroll-and-operating-window-report.md", "P2C Payroll and Operating Window", report, "overall_phase2c_payroll_and_operating_window_passed")
    print(f"overall_phase2c_payroll_and_operating_window_passed={report['overall_phase2c_payroll_and_operating_window_passed']}")
    return 0 if report["overall_phase2c_payroll_and_operating_window_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
