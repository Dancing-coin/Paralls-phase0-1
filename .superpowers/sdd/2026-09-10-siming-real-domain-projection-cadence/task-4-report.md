# Task 4 Report

## Outcome

Added real Inventory and public Social cadence fixtures in
`test_siming_population_authorized_cadence_publication.py`.

- Inventory setup uses the production Package Registry, Construction Owner,
  production certification, and an output container created through the
  existing Inventory Owner. The authorized organization cadence reaches
  `authority_event_bus -> SimingEventPipeline -> SimingRuntime.tick` and the
  registered Inventory adapter commits `gameplay.inventory.production_output_received@1`.
- Social setup uses the active `population_signal_materialization@1` binding to
  commit a public signal. The cadence reaches the registered Social adapter;
  replay is zero-write and preserves one committed public signal event.
- A private Social source cannot authorize a cadence and publishes no cadence
  event or candidate.

## Runtime seam

The generic population path now accepts a non-empty projection revision vector
as a current subset of the authorized cadence vector. It still rejects stale,
empty, duplicate, or scope-invalid projections. Public Social and Tax source
projections remain `public` even when the cadence report scope is
`organization:summary`. Inventory-only facility/organization actor refs are
admitted as Owner targets and are excluded from Character Core seed refs.

## Verification

- `python -m pytest -q backend/tests/test_siming_population_authorized_cadence_publication.py backend/tests/test_siming_population_inventory_vertical.py backend/tests/test_siming_population_social_signal_vertical.py backend/tests/test_siming_population_production_boundaries.py backend/tests/test_siming_population_domain_owner_runtime.py`
  - 80 passed
- `python -m pytest -q backend/tests/test_siming_population_store_projection_assembler.py backend/tests/test_siming_population_inventory_vertical.py backend/tests/test_siming_population_social_signal_vertical.py backend/tests/test_siming_population_tax_pressure.py`
  - 23 passed
- `python scripts/verification/verify_siming_population_domain_owner_adaptation.py`
  - `overall_siming_population_domain_owner_adaptation_passed=True`
- `git diff --check`
  - passed

## Boundary

No contract, Owner, scheduler, holder/container fabrication, or private Social
projection was added.

## Review Fix

The public Social candidate scope guard now admits only the exact owner-only
shape (`public` + `social` + `social_population_signal` + registered capability
and `signal:*` actor). The real cadence fixture proves the Social Owner writes
one target-stream event. Review verification: 108 focused tests passed, Social
subset 2 passed, domain-owner harness passed, and `git diff --check` passed.
