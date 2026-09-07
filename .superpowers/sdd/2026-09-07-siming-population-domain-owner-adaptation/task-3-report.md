# Task 3 Report: Production Receipt Projection and Replanning

## Changed files

- `backend/app/population_continuity/domain_projection_sources.py`
  - Added a pure committed Production Owner receipt to next-population projection function.
  - Pins the projection to the receipt revision vector and rejects non-committed, stale, scope-mismatched, or unrelated output.
- `backend/app/population_continuity/seed_planner.py`
  - Admits the production contribution behavior as a settled Character Core seed.
- `backend/app/population_continuity/batch.py`
  - Admits the same production contribution behavior to the existing planner.
- `backend/app/services/siming_population_capability.py`
  - Builds receipt-driven read sets from explicit cadence payloads.
  - Replanning validates the Owner revision vector and receipt-only projection source.
  - Settled production receipts skip a second Owner append and feed Character Core continuity.
- `backend/app/services/siming_runtime.py`
  - Routes explicit receipt-driven cadence payloads through the existing `tick(...)` path and fails closed when no receipt projection is available.
- `backend/tests/test_siming_population_production_replanning.py`
  - Covers committed/rejected receipt projection, unrelated read-set rejection, and one-Owner-write/two-character-revision continuity.
- `scripts/verification/verify_siming_generalized_population_decision.py`
  - Adds a receipt projection boundary check to the generalized decision artifact.

## Verification

Required focused command:

`python -m pytest -q backend/tests/test_siming_population_production_replanning.py backend/tests/test_siming_led_population_seed_continuity.py`

```text
6 passed, 2 warnings in 3.26s
```

Additional regression:

`python -m pytest -q backend/tests/test_siming_population_production_replanning.py backend/tests/test_siming_population_production_owner_vertical.py backend/tests/test_siming_population_replanning.py backend/tests/test_siming_population_capability.py`

```text
23 passed, 2 warnings in 3.02s
```

`git diff --check`

```text
passed (no output)
```

The generalized verification script runs its new receipt projection check, but exits non-zero because the pre-existing predecessor artifact reports `siming-governed-three-actor-cohort-continuity-v1` as false.

## Commit

`b557e2f8ee02c0cc9c1942a840795e79947a1ea1` (`接通生产 Owner 回执群体重规划`)

## Concerns

- Replanning remains synchronous and explicit; no scheduler, background loop, event bus, or second store was added.
- The generalized verification predecessor failure is outside Task 3's receipt path and remains an existing harness prerequisite.
