# Task 2 Report: Production/Organization Projection Source and Owner Adapter

## Changed files

- `backend/app/population_continuity/domain_projection_sources.py`
  - Added `production_work_population_projections(...)` for committed,
    revision-pinned Production evidence paired with an admitted Organization
    schedule projection.
- `backend/app/population_continuity/decision_surface.py`
  - Registered `population:organization-production-work-contribution:v1`
    with the fixed Organization Owner contract.
- `backend/app/population_continuity/owner_adapters.py`
  - Added `OrganizationProductionWorkContributionOwnerExecutor`; it derives
    the Organization stream, event family, canonical idempotency key and
    receipt from the existing `OrganizationAuthority` operation.
- `backend/tests/test_siming_population_production_owner_vertical.py`
  - Added five focused projection, routing, zero-write, replay and rejection
    tests.
- `backend/tests/test_siming_population_decision_planner.py`
  - Updated the default capability catalog assertion for the newly admitted
    production behavior.

## Verification

`python -m pytest -q backend/tests/test_siming_population_production_owner_vertical.py backend/tests/test_siming_population_decision_routing.py backend/tests/test_siming_population_replanning.py backend/tests/test_siming_population_capability.py`

```text
23 passed, 2 warnings in 2.99s
```

Additional regression:

`python -m pytest -q backend/tests/test_siming_population_production_owner_vertical.py backend/tests/test_siming_population_decision_routing.py backend/tests/test_siming_population_replanning.py backend/tests/test_siming_population_capability.py backend/tests/test_siming_population_decision_planner.py`

```text
29 passed, 2 warnings in 3.41s
```

`git diff --check`

```text
passed (no output)
```

## Commit

`b9063c3a27c7b841b7fb7dbf02fc22034e517aae` (`接入司命生产工作 Owner 纵切`)

Follow-up compatibility fix: `72ba277` (`兼容司命组织投影外层作用域`).

## Concerns

- The new source function is intentionally pure and is not wired into startup
  projection construction; runtime wiring remains the later integration task.
- The source requires an explicit Organization projection scope, schedule
  event pin and source revision vector. Missing or stale pins are zero-write
  rejections by design.
