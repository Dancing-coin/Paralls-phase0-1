# M1-3 Pool replay receipt consumer check

Date: 2026-11-28

## Scope

Test commit `0b7852fe1152588aaf1ec4c718834677a0112b8d` adds a Pool consumer-level R2 regression. It commits an adjustment, injects a receipt whose `committed_event_ids` contains an unresolvable event ID, retries the same command, and asserts the Pool API raises `pool_replay_event_missing` without changing the exported store snapshot.

This covers Pool's mapping of the shared `replay_duplicate` validation and the no-write rejection path. It does not establish repository-wide R2 completion or change production code.

## Environment and verification

- Branch: `thread-a/ownership-bond-followup-20261121`.
- Code/test commit: `0b7852fe1152588aaf1ec4c718834677a0112b8d`.
- Python: `3.12.2`, executable `F:\codex-temp\thread-a-python312\Scripts\python.exe`.
- SQLite: `3.43.1`.
- `PYTHONPATH`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`.
- Import check: `app.__file__ = F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- Raw outputs: `F:\paralls-verification\thread-a\m1-3-pool-r2-receipt-consumer-20261128-01\`.

Focused tests:

| Command scope | Result |
|---|---|
| `backend/tests/test_pool_runtime.py::test_pool_duplicate_rejects_unresolvable_committed_event_id_without_writes` | `1 passed, 2 warnings in 0.26s` |
| `backend/tests/test_pool_runtime.py` | `20 passed, 2 warnings in 0.35s` |

The warnings are existing Starlette/httpx and AnyIO deprecations.

Frozen-baseline comparisons using `docs/verification/absorb-main-3bf3418e/compare_selection.py`:

| Selection | Selected | Problems | Improvements |
|---|---:|---:|---:|
| M1-3 Pool | 34 | 0 | 0 |
| Ownership | 24 | 0 | 0 |
| Modifier | 12 | 0 | 0 |
| Equipment | 87 | 0 | 0 |
| Inventory | 56 | 0 | 0 |
| shared-replay | 990 | 0 | 0 |

All six comparisons ran serially. Logs and batch outputs are under `F:\paralls-verification\thread-a\m1-3-pool-r2-receipt-consumer-20261128-01\selection-runs\`. P-1 scanned the added test lines across five credential-pattern families and returned `patterns-scanned=5 credential-pattern-hits=0`; raw output is `p1-code-scan.log` in the run directory.

## Status

- Verified: Pool duplicate receipt rejects an unresolvable committed event reference with the Pool error code and zero store mutation; the Pool U11 selection now registers this test at 34 nodes.
- Not verified: full backend suite, full M1-3 U5 across all Pool/Morale consumers, and the remaining M1-3 declaration, reader, probe, and production scheduling work.
- M1-3 remains in progress. No production runtime, event contract, storage core, or `integration` branch changed.
