# INF-2 Time, Obligation, And Cross-Domain Settlement Implementation Plan

> **Evidence status:** The historical clock/coordinator vertical below is independently verified. It is a prerequisite, not completion of August INF-2.

**Goal:** Complete the documented caller-driven owner-authorized obligation settlement vertical without adding a runtime or scheduler.

**Architecture:** Keep `SimulationClock` pure; model lifecycle and activation locks in shared contracts; let domain authorities emit fragments and let the existing settlement adapter assemble one batch and receipt.

**Tech Stack:** Python, Pydantic, pytest, existing GameplayEventStore/replay/Harness.

---

### Task 1: Lock obligation lifecycle with tests

**Files:** Modify `backend/tests/test_simulation_clock.py`; modify `backend/app/gameplay/shared_contracts.py`.

- [x] Added focused lifecycle coverage for illegal `closed -> due` and deterministic `open -> due -> settling -> closed` behavior.
- [x] Added typed lifecycle validation plus idempotency, expected-revision, and visibility fields to `ScheduledObligation`.
- [x] Focused clock tests pass.

### Task 2: Implement owner-only due settlement

**Files:** Create `backend/app/world_runtime/obligations.py`; create `backend/tests/test_infra_time_obligation.py`.

- [x] Added zero-write tests for unowned fragments and stale revisions.
- [x] Implemented an owner-authorized coordinator that assembles one existing atomic batch and appends once.
- [x] Added append-derived `SettlementReceipt` coverage for duplicate replay, revisions, and event IDs.
- [x] Focused INF-2 tests pass.

### Task 3: Add activation lock and pending merge

**Files:** Modify `backend/app/population_continuity/activation.py`; modify `backend/app/population_continuity/models.py`; add focused tests.

- [x] Added active-profile deferral and held-revision fixture coverage.
- [~] Historical lock/release evidence exists; it does not establish a generic
  event-derived pending queue or ScheduledObligation integration. INF-4C later
  added one separately verified `schedule_gated_supply` row.
- [x] Verified stale release and unauthorized scope are structured zero-write failures.

### Task 4: Prove three owner vertical slices

**Files:** Modify only existing economy, survival, and production owner modules/tests identified during implementation.

- [x] Added historical caller-driven, no-background-mutation fragment tests for
  named economy, survival, and production fixtures.
- [~] These fixtures do not establish general owner lifecycle coverage; formal
  INF-2 closure still requires registered event-derived rows and policy maps.

### Task 5: Harness, status, and evidence

**Files:** Modify `.harness/profiles/infra-time-obligation.json`; modify `scripts/verification/verify_infra_time_obligation.py`; modify August guidance status and this plan/spec as required.

- [x] Mapped each capability to a separate pytest selector and report boolean.
- [x] Preserved `.harness/verification/infra-time-obligation-report.json`.
- [x] Ran `git diff --check` and the full suite (`2504 passed`; one pre-existing pytest-asyncio configuration deprecation warning).

## Verification

```powershell
python -m pytest backend/tests/test_infra_time_obligation.py -q
python scripts/verification/harness.py --profile infra-time-obligation
git diff --check
```

The historical INF-2 vertical is verified. August INF-2 is not complete: its
event-derived cross-domain lifecycle, complete status matrix, and generic
activation-pending integration remain separate work.
