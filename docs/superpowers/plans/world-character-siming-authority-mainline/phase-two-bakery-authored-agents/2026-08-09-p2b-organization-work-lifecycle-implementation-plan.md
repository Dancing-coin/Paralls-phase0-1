# P2B Organization Work Lifecycle Implementation Plan

Status: `implemented-and-verified; closed`

## Goal and dependency gate

Extend the existing Organization `RoleAssignment` lifecycle to shifts, bounded work orders and
evidence, while preserving Production/Inventory/Skill/Survival owners. P2A focused green and P1D
fresh-green are mandatory prerequisites.

## Exact files and order

1. Add `backend/tests/test_phase2b_organization_work_lifecycle.py` for assignment authorization, offer lifecycle, work lifecycle,
   attendance/completion evidence and profile-backed refs.
2. Extend `backend/app/gameplay/organization_government_runtime.py` and its existing models only;
   do not add `EmployeeState`, `NpcState` or a coordinator.
3. Add typed reference plumbing to `backend/app/gameplay/construction_production_runtime.py` and
   `backend/app/gameplay/inventory_runtime.py` without copying canonical facts.
4. Extended the pure composition boundary in `backend/app/gameplay/settlement_plan.py` and
   `backend/app/gameplay/models.py`; add multi-stream `SettlementPlan`/`AtomicEventBatch` tests for organization+production+inventory,
   including slot/reservation conflict and zero-partial-write assertions.
5. Add replay/checkpoint-tail, outbox, actor/manager/mirror scope tests to
   `backend/tests/test_gameplay_event_replay.py` and
   `backend/tests/test_gameplay_shared_replay_and_permission.py`. Future profile files are exact:
   `.harness/profiles/phase2b-organization-work-lifecycle.json` and
   `scripts/verification/verify_phase2b_organization_work_lifecycle.py`.

## Test and evidence order

Run unit tests for each owner, then cross-domain atomic tests, then replay/permission tests. Persist
event owner diff, stream revision vector, receipt, failure envelope and projection digests under
`.harness/verification/`.

## Verification commands

```powershell
python -m pytest -q backend/tests/test_organization_government_models.py backend/tests/test_organization_government_operations.py backend/tests/test_construction_production_start.py backend/tests/test_construction_production_finish.py backend/tests/test_inventory_reservation.py backend/tests/test_gameplay_event_store_contract.py backend/tests/test_gameplay_event_replay.py backend/tests/test_gameplay_shared_replay_and_permission.py
python scripts/verification/harness.py --profile phase1d-econ1-bakery
python scripts/verification/harness.py --profile phase2b-organization-work-lifecycle
```

## Dependency handoff and prohibitions

P2C started only after fresh P2B evidence. Any requirement for a second store, bus, scheduler,
implicit tick, or direct foreign-owner write remains a plan failure and requires spec revision.
