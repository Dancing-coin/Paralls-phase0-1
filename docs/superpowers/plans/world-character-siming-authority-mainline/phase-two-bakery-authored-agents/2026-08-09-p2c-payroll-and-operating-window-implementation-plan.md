# P2C Payroll and Operating Window Implementation Plan

Status: `implemented-and-verified; closed`

## Goal and dependency gate

Add evidence-driven wage accrual/payment-or-overdue and explicit operating-window close. P2A and
P2B focused tests/Harness plus P1D fresh-green are hard prerequisites; no global clock is permitted.

## Exact files and order

1. Add `backend/tests/test_phase2c_payroll_and_operating_window.py` for completed-evidence-only accrual, payment, insufficient funds,
   due/overdue transitions, explicit open/close and duplicate/stale/window-out-of-scope rejection;
   include the invariant that `mark_overdue` leaves the existing business period recovery-required
   and does not submit `BusinessPeriod.closed=true`.
2. Extend existing `backend/app/gameplay/econ1_economy_runtime.py`,
   `backend/app/gameplay/economy_runtime.py`, `backend/app/gameplay/debt_runtime.py` and
   `backend/app/gameplay/organization_government_runtime.py` only where P2C spec maps a reference; do
   not create a payroll service or scheduler.
3. Use existing `EconomicObligation`, account/journal and pure `SettlementPlan` composition from
   `backend/app/gameplay/settlement_plan.py`; commit all affected
   streams with `GameplayEventStore.append_batch()` and complete expected revisions.
4. Added full/checkpoint-tail replay, outbox and actor/manager/Godot scope tests to
   `backend/tests/test_gameplay_event_replay.py` and
   `backend/tests/test_gameplay_shared_replay_and_permission.py`. Future profile files are exact:
   `.harness/profiles/phase2c-payroll-operating-window.json` and
   `scripts/verification/verify_phase2c_payroll_and_operating_window.py`.

## Verification commands

```powershell
python -m pytest -q backend/tests/test_econ1_economy_models.py backend/tests/test_econ1_authority_settlement.py backend/tests/test_econ1_period_obligation_guard.py backend/tests/test_econ1_period_close.py backend/tests/test_gameplay_event_store_contract.py backend/tests/test_gameplay_event_replay.py backend/tests/test_gameplay_shared_replay_and_permission.py
python scripts/verification/harness.py --profile phase1d-econ1-bakery
python scripts/verification/harness.py --profile phase2c-payroll-operating-window
```

## Handoff

P2D started only after P2C evidence was fresh-green. Payment success and insufficient-funds zero-write
overdue paths are covered. Payment failure never marks paid; any future need for background wakeup,
generic SimulationClock, dynamic wage market, or second settlement path requires a new approved spec.
