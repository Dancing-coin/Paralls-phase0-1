# M1-3 Pool Runtime Evidence

Date: 2026-11-22

## Baseline and environment

- Worktree: `F:\codex-temp\paralls-v2-thread-a-bond-20261121`
- Branch: `thread-a/ownership-bond-followup-20261121`
- Base: `3caf3ae3` (`Holdings primitive contract gaps`)
- M1-3 code commits: `e6cb728caf725704b2e60d615b425db42d461af3` and `022f1772429fa95d1969d82de984568880da3a83`
- Python: 3.12.2 from `D:\Temp\paralls-g0-py312\Scripts\python.exe`
- `PYTHONPATH`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`
- `app.__file__`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`
- SQLite: 3.43.1. The frozen baseline documents concurrent WAL checkpoint tests as requiring SQLite 3.51.3 or later.
- All verification output and pytest output directories are under `F:\paralls-verification\thread-a\`.

## Delivered slice

The Pool runtime stores bounds, values, adjustments, reservations, releases, consumption, bound changes, and threshold crossings in its FactType stream. Its projector rebuilds value, reservations, window idempotency, and hysteresis state. Aggregation modes are `none`, `sum`, `distribution`, and `ordered`; distribution delegates recomputation to the refold resolver and requires a trigger reason and input revision vector. Owner commands persist an `OwnerAuthorizedFragment` with ordered operations, principal, read-set revisions, and pinned revisions. Model input revisions participate in idempotency and atomic read-set validation. Commands without that optional revision input retain their prior idempotency digest.

This does not implement the domain-specific D8 morale formula, declare a production Pool FactType, or add a Pool rule pack. `effective_stats.py` remains a derived projection and was not changed.

| File | Change | Status |
|---|---|---|
| `backend/app/gameplay/pool_runtime.py` | Event-sourced Pool projection, aggregation, Owner fragment commits | Implemented and tested |
| `backend/app/gameplay/pool_event_schema.py` | Graph discovery declarations and opt-in v1 schema registrations | Implemented and tested |
| `backend/tests/test_pool_runtime.py` | 15 fixed-vector, rejection, aggregation, replay, and event-registration tests | Implemented and tested |
| `docs/verification/selection/m1-3-pool.json` | U11 permanent regression selection, 15 tests, HEAD `022f1772` | Added and run |

## Focused and selection verification

Commands ran from the worktree root. `PYTHONPATH` was set to the worktree backend before each pytest run, and the import check confirmed `app.__file__` resolves inside this worktree.

```text
& 'D:\Temp\paralls-g0-py312\Scripts\python.exe' -m pytest -q backend/tests/test_pool_runtime.py
15 passed, 2 warnings

Pool unit selection: selected=15 problems=0 improvements=0
ownership selection: selected=24 problems=0 improvements=0
shared-replay selection: selected=990 problems=0 improvements=0
equipment selection: selected=87 problems=0 improvements=0
inventory selection: selected=56 problems=0 improvements=0
modifier selection: selected=12 problems=0 improvements=0
```

The five frozen selections total 1,169 nodes. The Pool unit selection adds 15 registered regression nodes. Outputs:

- Earlier M1-3 focused and ownership/shared-replay selections: `F:\paralls-verification\thread-a\m1-3-gates-959d0c0946b840219a9c10f49bca6f5a\`
- Additional frozen selections: `F:\paralls-verification\thread-a\m1-3-autonomy-gates-20261122-2313\`

## Combined-state full regression

This is a full regression of the combined worktree state at code HEAD `022f1772429fa95d1969d82de984568880da3a83`. It is not a test of any individual commit by itself.

```text
docs/verification/g0-939c6746/run_baseline.py --freeze --repo F:\codex-temp\paralls-v2-thread-a-bond-20261121 --output F:\paralls-verification\thread-a\m1-3-full-d2abc2af51334b388db144c74b4726b6\full
10,461 collected; 10,433 passed, 24 failed, 2 skipped, 2 xfailed, 239 warnings; exit code 1
```

The `(test_name, phase, error_type)` set was compared to the M3-1 short-temporary-path full run at HEAD `7defd05b7d2b9f7b8038b8240901e6933076cd64`: `new_only=0`, `old_only=0`. The 24 failures match the prior run's existing set. This comparison establishes no new full-suite failures for the combined state; it does not turn the full run into a passing run.

- Raw console: `F:\paralls-verification\thread-a\m1-3-full-d2abc2af51334b388db144c74b4726b6\full-console.log`
- Results, failure records, environment, frozen node list, and JUnit: `F:\paralls-verification\thread-a\m1-3-full-d2abc2af51334b388db144c74b4726b6\full\`
- Prior comparison: `F:\paralls-verification\thread-a\m3-1-full-shorttemp-20261122-7defd05b-58a2\results.json`

The environment used the required Python 3.12.2 interpreter and SQLite 3.43.1. The baseline documents the SQLite version gap for concurrent WAL checkpoint cases. The full-suite command exited nonzero because the 24 baseline failures remain.

## U1-U11

| Item | Assessment |
|---|---|
| U1 | Not done. The Pool Owner is not declared or classified by this runtime unit. |
| U2 | Not done. No production Pool FactType definition was added. |
| U3 | Verified for this slice. Pool event declarations are found by graph discovery and have opt-in v1 schema registrations. |
| U4 | Verified. Pool commands use `OwnerCommitBuilder` and persist the Owner fragment contract. |
| U5 | Not run. R1/R2/R3 evidence is outside this unit. |
| U6 | Static only. Production event readers found are in `pool_runtime.py`; tests cover the projection. No external production reader was found. |
| U7 | Not done. Subject-facing read classification remains blocked on M2-2. |
| U8 | Not done. No Pool rule pack or domain Resolver registration was added; distribution delegates to the existing refold resolver. |
| U9 | Verified to the stated depth. Focused tests and all five frozen selections have no selection differences. The combined-state full run has the 24 existing failures and adds none by `(test_name, phase, error_type)` comparison. |
| U10 | Verified. Code changes, test selection, verification depth, raw outputs, and remaining gaps are listed here. |
| U11 | Verified. `docs/verification/selection/m1-3-pool.json` registers all 15 Pool tests, and the selection reports zero problems. |

M1-3 implementation and its registered test selection are ready for the project gate. The unit does not establish Pool Owner/Facts registration, domain-specific D8 behavior, subject-facing reads, or Architecture v2 completion.
