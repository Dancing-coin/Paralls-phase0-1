# M6-5 Presence passability assessment

- Implementation commit: `d7ae1d38c8217ca76da42a4654efe76bb4fabca4`.
- Worktree: `F:\codex-temp\a-m6-5-place-verify-20261124`, detached at the implementation commit.
- Python: `D:\Temp\paralls-g0-py312\Scripts\python.exe`, version `3.12.2`.
- `PYTHONPATH` resolved `app` to `F:\codex-temp\a-m6-5-place-verify-20261124\backend\app\__init__.py`.
- `TEMP`, `TMP`, pytest basetemp, and verification output were directed to `F:\paralls-verification\thread-a\m6-5-presence-detached-20261124-01\`.

## Contract

The siege specification says a committed integrity breach triggers a Presence reevaluation and does not itself change passability. `PlacePassabilityAuthority` accepts only a committed Production/Facility-owned `gameplay.pool.threshold_crossed` event for the gate's `breach` threshold. A trusted resolver must supply a `blocked` or `passable` assessment and cite the breach plus at least one additional committed evidence event. Each cited stream must have an Owner-verified event, an explicit revision pin, and a current head matching that revision. No resolver result or no independent evidence returns `place_assessment_unknown` with no write. Stale evidence returns `place_assessment_source_stale` with no write.

Presence writes only `place:<gate>:passability`, with the existing `population.presence_authority` transaction principal and the registered event `gameplay.presence.place_passability_changed@1`. The Place stream and the Facility integrity stream retain independent revisions. Exact retry after later source changes replays the original receipt. The assessment policy itself remains an injected trusted resolver. The implementation does not define a breach-to-passability formula.

## Verification

| Check | Result |
|---|---|
| Detached targeted command | `python -m pytest -q backend/tests/test_place_passability_runtime.py backend/tests/test_facility_integrity_runtime.py backend/tests/test_morale_refold_runtime.py` — 12 passed, 2 deprecation warnings |
| P-3 event discovery | `gameplay.presence.place_passability_changed` is in `FACT_TYPE_REGISTRY.event_types()` and maps to domain `presence` |
| Ownership frozen selection | `selected=24 problems=0 improvements=0` |
| Shared-replay frozen selection | `selected=990 problems=2 improvements=0`; two pre-existing external Port 8000 failures |
| Full suite on the M6-5 combined worktree at `d7ae1d38c8217ca76da42a4654efe76bb4fabca4` | `10,543 passed, 35 failed, 2 skipped, 2 xfailed, 239 warnings`; 10,582 collected; exit code 1; 1,565.19 seconds |
| New unit selection | `selected=6 problems=0 improvements=0` |

The combined-worktree full-suite run used `F:\paralls-verification\thread-a\m6-5-presence-full-short-20261124-01\full\`. Its `results.json`, `junit.xml`, `failures.jsonl`, `environment.json`, `invocation.json`, and collected node IDs preserve the raw result. A prior run at the same code SHA with a longer pytest temporary path had 47 failures. The short-path run had 35 failures, all shared with that first run; 12 path-sensitive failures from the first run did not recur. This is evidence for the combined worktree only and does not establish a clean full-suite pass or classify every shared failure against a parent-code baseline. Inspect `failures.jsonl` for the exact tracebacks.

The shared-replay failures are `test_profile_repeated_in_one_run_receives_fresh_events[isolated-storage]` and `[wall-clock]`. They also fail at parent commit `5d7cc0da` with `Port 8000 is occupied by an external process without a healthy backend`. This check did not stop or modify that process. Parent recheck output is in `F:\paralls-verification\thread-a\m6-5-presence-parent-diff-20261124-01\`. The complete shared-replay logs are under `F:\paralls-verification\thread-a\m6-5-presence-shared-replay-20261124-02\`. The earlier incomplete attempt is retained in `F:\paralls-verification\thread-a\m6-5-presence-detached-20261124-01\`.

## Reader inventory

Static search covered `backend/app`, `backend/tests`, `scripts`, and probes for `gameplay.presence.place_passability_changed`, `PlacePassabilityAuthority`, and `place:...:passability`.

- Writer: `backend/app/gameplay/place_passability_runtime.py`, `PlacePassabilityAuthority.commit_assessment`.
- Event registration: `backend/app/gameplay/place_event_schema.py`; production factory registration: `backend/app/gameplay/event_schema_registry.py`.
- Projection discovery: `gameplay_schema_event_types()` scans the domain event schema module; the P-3 test confirms registry visibility and domain mapping.
- Current state reader: `PlacePassabilityAuthority.state` replays the Place stream and validates each transition and transaction owner.
- Other production readers: none found by the static search.

## Unit status

| DoD | Status |
|---|---|
| U1 Owner declaration and classification | Partially verified. The formal Owner table classifies Presence/Movement as stewarded. No v2 Presence Owner declaration exists in the code registry yet. |
| U2 FactType declaration | Not done. `fact:place:<gate>:passability` is not yet declared with the complete L2 schema. |
| U3 Event schema and P-3 | Verified for the added event type. |
| U4 Shared mechanism | Partially verified. Uses `build_atomic_event_batch` and EventStore read/write/CAS behavior. |
| U5 R1/R2/R3 | Partially verified by exact retry and snapshot reconstruction tests. |
| U6 Reader inventory | Static inventory recorded above; the focused tests cover current reads and writes. |
| U7 Read classification and visibility | Not done. The output event currently uses `project`; a v2 visibility declaration and `read_as` contract are absent. |
| U8 Rule-pack settings and resolver registration | Not done. Resolver is constructor-injected and is not registered through a v2 Owner/rule-pack declaration. |
| U9 Probe and frozen baseline | Partially verified. Ownership selection is zero-difference. Shared-replay has two failures reproduced at the parent commit. Full suite remains pending. |
| U10 Changed files and verification levels | Recorded in this file and the implementation commit. |
| U11 Permanent unit selection | Verified; `selected=6 problems=0 improvements=0`. |

This is a Presence-owned passability writer component. It does not complete M6-5, the L5 production dispatcher, the generic Place primitive, or the Presence Owner's full v2 migration.
