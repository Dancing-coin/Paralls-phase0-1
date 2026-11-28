# M1-3 Pool formal-spec audit

Date: 2026-11-24

## Scope and evidence

This is a static comparison of the read-only formal specification `docs/architecture-v2/02-原语/02-六原语规格.md` (version 1.0, Pool section, lines 15–79) against the A-worktree implementation at `d1ff2e55acdb417c9035451312a70d296241b2ad` in `backend/app/gameplay/pool_runtime.py`, its tests, and the existing M1-3 evidence. No source code or persisted event contract changed in this audit. No pytest command was run.

## Contract comparison

| Formal requirement | Current implementation evidence | Assessment |
|---|---|---|
| P1 value stays within bounds | `PoolProjector.rebuild`, `PoolAuthorityService.adjust`, `consume`, `set_bound`; lower and upper bounds are checked | Implemented for commands and replay |
| P2 reservations stay nonnegative and within the pool | `reserve` requires positive amount and aggregate reserved amount no greater than value; replay validates the same | Implemented |
| P3 available equals value minus reserved and remains nonnegative | `PoolProjection.available`; reserve/adjust/consume and replay prevent value falling below active reservations | Implemented for valid projections |
| P4 consume requires a reservation and is atomic with value reduction | `consume` appends `gameplay.pool.consumed`; replay removes reservation and subtracts actual in one committed event | Implemented |
| P5 one integration per world window | `integrate` requires `window_ref`; `adjust` includes it in idempotency and the projector rejects duplicate integrated windows | Implemented for `integrate`; direct non-integration adjustments may omit a window by design |
| P6 threshold crossing triggers a cut window | `adjust` and `consume` append hysteresis transition events in the same commit when thresholds cross | Threshold transition is persisted atomically and provides the cut trigger. The runtime has no production subscriber that starts the next integration interval after this trigger |
| P7 hysteresis prevents flips inside the band | `_threshold_events` and replay maintain active threshold state and use enter/exit bounds | Implemented |
| Time integration over `[t0,t]` | `PoolDefinition.rate_per_tick` and `integrate(ticks, window_ref)` calculate an explicit caller-supplied tick delta | Primitive is implemented for explicit ticks. Static call-site search found no production caller outside `pool_runtime.py`; there is no production scheduler connecting Pool integration to the world clock |
| Settle at input revision, threshold, pause, handoff, and version boundaries | Model adjustments can pin input revisions; threshold events are in the same command batch | Primitive support is partial. No production Pool integration caller/dispatcher was found to close intervals at these boundaries |
| Preserve any intermediate zero during projection integration | `integrate` turns caller-supplied ticks into one net `adjusted` event; payload stores previous/delta/next | A zero endpoint is persisted. The event does not encode a within-interval minimum, so a non-constant rate trajectory that reaches zero then recovers cannot be reconstructed |
| Aggregation modes and distribution refold | `aggregate_pool_values` implements `none`, `sum`, `ordered`, and revision-pinned `distribution` | Implemented at generic runtime level; domain resolver and production rules remain outside M1-3 |
| Owner fragment format with ordered operations and pinned revisions | Pool commands use `OwnerCommitBuilder`; existing evidence records fragment, operation, read-set and input revision coverage | Implemented at the stated mechanism level |

## Decisions and remaining inputs

The existing explicit-tick `integrate` API is a deterministic primitive. The missing production path is a caller that connects the authoritative world tick to domain Pool streams and invokes integration at revision/threshold/pause/handoff/version boundaries. The repository has `SimulationClock` and `SimulationDriver.current_tick` as candidate time sources, but no Pool integration call site was found using them. A future implementation should preserve the current explicit integration API where possible, use a stable world-window reference, and only extend persisted payloads if a domain needs reconstruction of non-constant within-window rate trajectories. No such trajectory or event change was added in this audit.

The remaining domain-level M1-3 items are unchanged: domain Owner classification and production Pool FactTypes require the owning-domain mapping; `read_as` remains dependent on M2-2; rule-pack Resolver registration requires the domain model contract; R1/R2/R3 and the complete G5 gate remain unverified. Existing selection and full-suite results in the base M1-3 evidence are not reattributed by this audit.

## Verification status

- The specification comparison itself was static and changed no code. A follow-up current-tip Pool regression was run at `5e7b7eeb97bdc2216065f67bdf36546be56a8d69` using Python 3.12.2, with `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`. The import check printed `app.__file__ = F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- Command: `python -m pytest -q --basetemp F:\paralls-verification\thread-a\m1-3-pool-current-20261124-5e7b7eeb\pytest-tmp backend/tests/test_pool_runtime.py`.
- Raw output: `19 passed, 2 warnings in 0.21s`. Environment and pytest logs are in `F:\paralls-verification\thread-a\m1-3-pool-current-20261124-5e7b7eeb\`.
- Frozen selections and full suite were not rerun for this audit.
- The latest recorded Pool focused tests and selections remain in the linked M1-3 runtime, factory, and casualty evidence. The combined-state full suite previously exited nonzero and is not a passing result.
- M1-3 remains `待门禁`; this audit does not claim that Pool or Architecture v2 is complete.

## Current A-tip regression recheck (2026-11-28)

The code and selections were rechecked at A HEAD `72082ffd8d7bb5143fc0b2acda2e5faf7eb354ba`. The commit adds only coordination documentation after code tip `51d88a4c`; no Pool runtime code changed in between.

Environment: Python `3.12.2`, `app.__file__` at `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`, SQLite `3.43.1`. All raw output is under `F:\paralls-verification\thread-a\m1-3-current-tip-20261128-01\`.

| Check | Result |
|---|---|
| Pool, Facility integrity, and Morale Pool focused tests | `27 passed, 2 warnings` |
| M1-3 Pool registered selection | `selected=17 problems=0 improvements=0` |
| M1-3 domain-owner registered selection | `selected=1 problems=0 improvements=0` |
| Frozen ownership selection | `selected=24 problems=0 improvements=0` |
| Frozen modifier selection | `selected=12 problems=0 improvements=0` |
| Frozen equipment selection | `selected=87 problems=0 improvements=0` |
| Frozen inventory selection | `selected=56 problems=0 improvements=0` |
| Frozen shared-replay selection | `selected=990 problems=0 improvements=0` |

This is focused and selection evidence only. The full backend suite was not run. Production Pool scheduling, non-zero rate-bearing Pool content, domain Owner/FactType declaration, domain Resolver registration, R1/R2/R3 evidence, and subject-facing reads remain unverified or incomplete. No `integration` change was made.

## Current A-tip regression recheck (2026-11-28, second run)

The recheck ran at A documentation HEAD `6f84de9ec82858a6228468733b8c73f038d161d2` and backend code tip `616d9815053e9309e996cd81998c1c47fc2906e2`.

Environment: Python `3.12.2`, SQLite `3.43.1`, and `app.__file__` at `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`. `PYTHONPATH` pointed to the A worktree `backend`; pytest temp, `TEMP`, `TMP`, `TMPDIR`, and raw output were under `F:\paralls-verification\thread-a\m1-3-current-tip-20261128-02\`.

| Check | Result |
|---|---|
| Pool, Facility integrity, and Morale Pool focused tests | `27 passed, 2 warnings` |
| M1-3 Pool registered selection | `selected=17 problems=0 improvements=0` |
| M1-3 domain-owner registered selection | `selected=1 problems=0 improvements=0` |
| Frozen ownership selection | `selected=24 problems=0 improvements=0` |
| Frozen modifier selection | `selected=12 problems=0 improvements=0` |
| Frozen equipment selection | `selected=87 problems=0 improvements=0` |
| Frozen inventory selection | `selected=56 problems=0 improvements=0` |
| Frozen shared-replay selection | `selected=990 problems=0 improvements=0` |

The first frozen-selection invocation used `docs/verification/selection/` for the five frozen manifests, where those files do not exist. It stopped before running the ownership selection and logged the path error. The five were then run from `docs/verification/absorb-main-3bf3418e/`; all returned zero differences. Both the failed invocation and corrected commands are retained in the raw output directory.

Command for the focused tests:

```powershell
$env:PYTHONPATH='F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend'
$env:TEMP='F:\paralls-verification\thread-a\m1-3-current-tip-20261128-02\temp'
$env:TMP=$env:TEMP
$env:TMPDIR=$env:TEMP
& 'F:\codex-temp\thread-a-python312\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider --basetemp 'F:\paralls-verification\thread-a\m1-3-current-tip-20261128-02\pytest-temp' backend/tests/test_pool_runtime.py backend/tests/test_facility_integrity_runtime.py backend/tests/test_morale_refold_runtime.py
```

This is focused and selection evidence only. The full backend suite was not run. Production Pool scheduling, non-zero rate-bearing Pool content, domain Owner/FactType declaration, domain Resolver registration, R1/R2/R3 evidence, and subject-facing reads remain unverified or incomplete. M1-3 remains `待门禁`; `integration` was not modified.
