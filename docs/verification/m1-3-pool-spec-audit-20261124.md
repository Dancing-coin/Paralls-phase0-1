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
| P6 threshold crossing triggers a cut window | `adjust` and `consume` append hysteresis transition events in the same commit when thresholds cross | Threshold transition is persisted atomically. No separate window-close event or downstream window executor exists in Pool runtime |
| P7 hysteresis prevents flips inside the band | `_threshold_events` and replay maintain active threshold state and use enter/exit bounds | Implemented |
| Time integration over `[t0,t]` | `PoolDefinition.rate_per_tick` and `integrate(ticks, window_ref)` calculate an explicit caller-supplied tick delta | Partial. No authoritative clock is read, no interval endpoints are persisted, and caller must decide when/how many ticks to settle |
| Settle at input revision, threshold, pause, handoff, and version boundaries | Model adjustments can pin input revisions; threshold events are in the same command batch | Partial. Pause, handoff, version-upgrade lifecycle, and a common boundary dispatcher are absent |
| Preserve any intermediate zero during projection integration | `integrate` turns caller-supplied ticks into one net `adjusted` event; payload stores previous/delta/next but no intermediate trajectory or minimum | Not demonstrated. Current API cannot encode whether a value reached zero and later recovered within one integration interval |
| Aggregation modes and distribution refold | `aggregate_pool_values` implements `none`, `sum`, `ordered`, and revision-pinned `distribution` | Implemented at generic runtime level; domain resolver and production rules remain outside M1-3 |
| Owner fragment format with ordered operations and pinned revisions | Pool commands use `OwnerCommitBuilder`; existing evidence records fragment, operation, read-set and input revision coverage | Implemented at the stated mechanism level |

## Decisions and remaining inputs

The existing explicit-tick `integrate` API is a deterministic primitive, but it does not satisfy the formal continuous-time settlement lifecycle by itself. Closing that gap requires a defined authoritative tick/time source, boundary event contract for pause/handoff/version changes, and a representation for within-window minimum/zero observations. Those affect persisted event payloads and replay semantics. They are not inferred here.

The remaining domain-level M1-3 items are unchanged: domain Owner classification and production Pool FactTypes require the owning-domain mapping; `read_as` remains dependent on M2-2; rule-pack Resolver registration requires the domain model contract; R1/R2/R3 and the complete G5 gate remain unverified. Existing selection and full-suite results in the base M1-3 evidence are not reattributed by this audit.

## Verification status

- The specification comparison itself was static and changed no code. A follow-up current-tip Pool regression was run at `5e7b7eeb97bdc2216065f67bdf36546be56a8d69` using Python 3.12.2, with `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`. The import check printed `app.__file__ = F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- Command: `python -m pytest -q --basetemp F:\paralls-verification\thread-a\m1-3-pool-current-20261124-5e7b7eeb\pytest-tmp backend/tests/test_pool_runtime.py`.
- Raw output: `19 passed, 2 warnings in 0.21s`. Environment and pytest logs are in `F:\paralls-verification\thread-a\m1-3-pool-current-20261124-5e7b7eeb\`.
- Frozen selections and full suite were not rerun for this audit.
- The latest recorded Pool focused tests and selections remain in the linked M1-3 runtime, factory, and casualty evidence. The combined-state full suite previously exited nonzero and is not a passing result.
- M1-3 remains `待门禁`; this audit does not claim that Pool or Architecture v2 is complete.
