# M1-3 Pool Runtime Slice Evidence

## Baseline and environment

- Worktree: `F:\codex-temp\paralls-v2-thread-a-bond-20261121`
- Branch: `thread-a/ownership-bond-followup-20261121`
- Base: `3caf3ae3` (`Holdings primitive contract gaps`)
- Code commit: `e6cb728caf725704b2e60d615b425db42d461af3`
- Python: `3.12.2` from `D:\Temp\paralls-g0-py312\Scripts\python.exe`
- `app.__file__`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`
- SQLite: `3.43.1`; the frozen baseline documents the concurrent WAL checkpoint tests as requiring SQLite 3.51.3 or later.
- `PYTHONPATH` before each pytest run: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`

## Delivered slice

The Pool runtime persists initialized bounds and values, adjustments, reservations, releases, consumption, bound changes, and threshold crossings to the FactType stream. Its projector rebuilds value, reservations, window idempotency, and hysteresis state from events. Owner commands use `OwnerCommitBuilder`; validation failures leave the event store unchanged. Event names are declared for graph discovery and have opt-in schema registrations.

| File | Change | Status |
|---|---|---|
| `backend/app/gameplay/pool_runtime.py` | Event-sourced Pool projection and authority commands | Implemented and tested |
| `backend/app/gameplay/pool_event_schema.py` | Graph discovery declarations and opt-in v1 schema registrations | Implemented and tested |
| `backend/tests/test_pool_runtime.py` | Eight fixed-vector and event registration tests | Implemented and tested |
| `docs/verification/selection/m1-3-pool.json` | U11 permanent regression selection | Added and run |

## Verification

Commands were run from the worktree root after setting `PYTHONPATH` to its `backend` directory.

```text
& 'D:\Temp\paralls-g0-py312\Scripts\python.exe' -c "import sys, sqlite3, app; print(sys.version); print(app.__file__); print(sqlite3.sqlite_version)"
3.12.2 (tags/v3.12.2:6abddd9, Feb  6 2024, 21:26:36) [MSC v.1937 64 bit (AMD64)]
F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py
3.43.1

& 'D:\Temp\paralls-g0-py312\Scripts\python.exe' -m pytest backend/tests/test_pool_runtime.py -q
8 passed, 2 warnings in 0.20s

docs/verification/absorb-main-3bf3418e/compare_selection.py --repo F:\codex-temp\paralls-v2-thread-a-bond-20261121 --selection docs/verification/selection/m1-3-pool.json --output F:\paralls-verification\thread-a\m1-3-pool-20261122-184c2bbda46545378c1c33e034105f6a-unit
selected=8 problems=0 improvements=0

docs/verification/absorb-main-3bf3418e/compare_selection.py --repo F:\codex-temp\paralls-v2-thread-a-bond-20261121 --selection docs/verification/absorb-main-3bf3418e/ownership.json --output F:\paralls-verification\thread-a\m1-3-pool-20261122-184c2bbda46545378c1c33e034105f6a-ownership
selected=24 problems=0 improvements=0

docs/verification/absorb-main-3bf3418e/compare_selection.py --repo F:\codex-temp\paralls-v2-thread-a-bond-20261121 --selection docs/verification/absorb-main-3bf3418e/shared-replay.json --output F:\paralls-verification\thread-a\m1-3-pool-20261122-184c2bbda46545378c1c33e034105f6a-shared-replay
selected=990 problems=0 improvements=0
```

The comparison outputs, including per-batch logs and reports, are retained in the three F-drive directories listed above. No full 10,392-node or current full-suite run was performed.

## U1-U11

| Item | Assessment |
|---|---|
| U1 | Not verified. This runtime slice does not declare or classify the Pool Owner. |
| U2 | Not verified. It does not register a production FactType definition. |
| U3 | Verified for this slice. The event declarations are discovered by `gameplay_schema_event_types()`, and a test asserts all seven types and their opt-in v1 registrations. |
| U4 | Verified in code. Commands build append batches with the existing `OwnerCommitBuilder`. |
| U5 | Not run. R1/R2/R3 evidence is outside this slice. |
| U6 | Static only. `rg` found Pool event readers in `pool_runtime.py` and its tests. No other production consumer was found. |
| U7 | Not implemented. Subject-facing read classification remains under blocked M2-2. |
| U8 | Not implemented. No Pool rule pack or Resolver registration was added. |
| U9 | Verified to the stated selection depth. New Pool tests and both frozen selections report zero problems. No full regression claim is made. |
| U10 | Verified. Changed code and data files are listed above, with verification depth stated. |
| U11 | Verified. The eight Pool tests are registered in `docs/verification/selection/m1-3-pool.json` and the registered selection reports zero problems. |

## Remaining M1-3 scope

This slice covers bounded values, reservations, window idempotency/integration, hysteresis, event projection, and fixed vectors. The migration plan's Pool aggregation behavior and Owner fragment format are not implemented here, so M1-3 remains in progress. `effective_stats.py` remains a derived projection and was not changed.
