# M5-5 FactType primitive field contract increment

## Change

The package validator now enforces the formal primitive-specific FactType field matrix for `aggregation`, `refold_model_ref`, `state_set_ref`, `bond_types`, and `place_kind`. The general FactType registry accepts each primitive already registered by the migration runtime instead of treating only `machine` and `pool` as supported. This does not register a new primitive or add package behavior.

## Verification

- Python: `D:\Temp\paralls-g0-py312\Scripts\python.exe`, Python 3.12.2.
- Focused command, with `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`: `python -m pytest -q backend\tests\test_rule_pack_validator.py backend\tests\test_credential_fact_type_registry.py`.
- Focused result: **134 passed, 2 warnings in 2.59s**. Warnings are the existing Starlette/httpx and anyio deprecations.
- M5-5 registered selection: **36 selected, 0 problems, 0 improvements** at `1be69ba3ba7b034cb626a788229604d4cb6ee867`.
- Frozen selections: ownership **24/0/0**, modifier **12/0/0**, equipment **87/0/0**, inventory **56/0/0**, shared-replay **990/0/0** (selected/problems/improvements).
- Full backend suite at the same HEAD collected 10,759 tests and exited 1: **10,693 passed, 62 failed, 2 skipped, 2 xfailed, 236 warnings in 1,142.90s**. The failure set was not compared node-by-node with the frozen baseline or parent commit, so these failures are unclassified and the full suite is not passing evidence.
- The full-run environment record reports Python 3.12.2, Windows 11, exact A-worktree `PYTHONPATH`, and `source_unchanged=true`. The run's `pytest-temp` setting was on F:, but pytest created an unexpected path under `backend` from a test-generated malformed path; that run-owned directory was moved intact to the evidence directory after pytest exited.

Raw output is under `F:/paralls-verification/thread-a/m5-5-field-primitive-20261126-02/`, `m5-5-field-primitive-20261126-03/`, `m5-5-field-primitive-g5-20261126-01/`, and `m5-5-field-primitive-full-20261126-03/`. Full-suite `results.json`, `junit.xml`, `failures.jsonl`, `environment.json`, and `console.log` are retained.

## Scope and remaining work

This verifies the primitive-specific schema-field contract increment only. It does not complete M5-5. The broader catalog still has missing formal package or runtime contracts, including `temporal_effects`, as recorded in the catalog and contract audits. The full-suite failures remain unclassified and must not be reported as baseline failures. Production package migration and deployment validation remain outside this increment.
