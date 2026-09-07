# Task 4 Report: Inventory Custody Population Vertical

## Changed files

- `backend/app/population_continuity/inventory_owner_adapter.py`
  - Added `InventoryOutputCustodyOwnerExecutor` (库存输出保管 Owner 执行器).
  - Reuses `InventoryAuthorityService.settle_production_output_custody(...)` and returns its append-derived receipt.
  - Rejects caller-supplied holder, container, quantity, item, stream, family, and owner overrides.
- `backend/app/population_continuity/domain_projection_sources.py`
  - Added committed certified-output projection for `inventory_output_custody`.
  - Admits only `public` / `organization:summary` scopes and carries certification revision pins only.
- `backend/app/population_continuity/decision_surface.py`
  - Registered `population:inventory-output-custody:v1` with `actor_gameplay.inventory_domain` and `inf:inventory-production-output-custody@1`.
- `backend/app/population_continuity/batch.py`
  - Admitted inventory custody candidates to the existing owner-bound planning surface.
- `backend/app/population_continuity/seed_planner.py`
  - Allows a settled inventory receipt to gate a Character Core seed.
- `backend/app/services/siming_population_capability.py`
  - Keeps inventory Owner receipt before continuity seed dispatch.
- `backend/app/population_continuity/__init__.py`
  - Exported the adapter.
- `backend/tests/test_siming_population_inventory_vertical.py`
  - Added certified admission, Owner settlement, stale zero-write, changed duplicate replay, and receipt-before-seed tests.
- `backend/tests/test_siming_population_decision_planner.py`
  - Updated the capability catalog expectation for the admitted inventory behavior.

## Verification

Required focused command:

`python -m pytest -q backend/tests/test_siming_population_inventory_vertical.py backend/tests/test_production_output_custody_family.py`

```text
10 passed, 2 warnings in 1.78s
```

Decision-surface regression:

`python -m pytest -q backend/tests/test_siming_population_decision_planner.py backend/tests/test_siming_population_decision_routing.py backend/tests/test_siming_population_decision_contracts.py backend/tests/test_siming_population_contracts.py`

```text
25 passed, 2 warnings in 2.41s
```

`git diff --check`

```text
passed (no output)
```

## Commit

`ae83fef` (`接入司命库存保管 Owner 纵切`)

## Concerns

- Inventory holder/container/quantity remain derived by the existing Inventory family binding; the population candidate does not expose or override them.
- The existing untracked implementation-plan file was intentionally left outside this Task 4 commit.
