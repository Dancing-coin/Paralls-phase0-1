# M5-3 Package Migration

## Implementation

Implementation commit: `aa8711683068ae220c3602e89f3da0a871f7f284`.

`pack.migrated@1` is registered as an L4 platform control-plane event. It remains outside gameplay FactType discovery and does not add a gameplay Owner. The runtime pins each archived package identity to an expected content hash, commits one `authority_only` migration event through the existing event-store API, rejects stale source sets and invalid revisions without writes, replays duplicate commands before current-source checks, and resolves historical package sets by global sequence.

## Environment

The configured interpreter is `D:\Temp\paralls-g0-py312\Scripts\python.exe`, Python 3.12.2. `PYTHONPATH` was set to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`. The pytest collection and failure traces resolve tests and imports from that A worktree. The same interpreter/worktree environment record from the preceding M5-3 run reports `app.__file__` as `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py` and SQLite 3.43.1. This run did not independently query SQLite. `TEMP`, `TMP`, and pytest `--basetemp` were set under `F:\paralls-verification\thread-a\m5-3-package-migration-20261126-final\`.

## Verification

| Check | Result | Raw output |
|---|---|---|
| `python -m pytest -q -p no:cacheprovider --basetemp=<F-run> backend/tests/test_package_migration_runtime.py backend/tests/test_gameplay_event_schema_registry.py` | 28 passed, 2 warnings, exit 0 | `F:\paralls-verification\thread-a\m5-3-package-migration-20261126-final\targeted.log` |
| M5-3 focused registered selection | 16 nodes, all passed at the implementation SHA | `F:\paralls-verification\thread-a\m5-3-package-migration-20261126-final\collected.log` |
| Frozen ownership selection | `selected=24 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m5-3-package-migration-20261126-final\ownership.log` |
| Frozen shared-replay selection | `selected=990 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m5-3-package-migration-20261126-final\shared-replay.log` |
| `git diff --check` before implementation commit | exit 0 | command output was empty apart from line-ending notices for coordination files, which were not staged in that commit |
| Backend full suite | Not run | No full-suite claim |

The shared-replay comparator used the existing F-drive `powershell.exe` name shim only for the local listener lookup. A fresh `netstat -ano -p tcp` check showed no local TCP listener on port 8000. No process was stopped. Ownership and shared-replay selections were run serially by `compare_selection.py` from `docs/verification/absorb-main-3bf3418e`.

## Scope And Remaining Work

| Requirement | Status |
|---|---|
| Platform event classification without a gameplay Owner | Verified by schema registration test and user-approved H-A-068 decision |
| Durable event write, idempotent duplicate replay, rejection with zero writes | Verified by focused tests |
| Historical package interpretation by global sequence and chain validation | Verified by focused tests |
| Frozen Ownership and shared-replay regressions | Verified, 24 and 990 nodes respectively |
| Production immutable archive bootstrap and trusted deployment hash manifest | Not implemented |
| Production package consumer/startup wiring | Not implemented; no production v2 `load_pack` caller was found |
| Full backend suite | Not run |
| M6-5 Gate configuration | `gate-03` values are now included in tracked `.env.example`; actual production deployment remains unverified |

M5-3's control-event/runtime slice is implemented and selected tests pass. This does not complete production package migration, M5 as a whole, Architecture v2, or full-suite validation.

## Trusted Archive Bootstrap Follow-up (2026-11-26)

Implementation commit: `2a5d66402aaf566bb8414ec61d51aa5cb5999b45`.

`load_package_archive` accepts an explicit package identity-to-directory mapping and a trusted identity-to-hash mapping. It resolves declared parent packages through `load_pack`, checks each loaded identity, and constructs `PackageArchive` only after every loaded effective hash matches its trusted pin. The caller remains responsible for sourcing the trusted mapping from deployment-controlled data.

| Check | Result | Raw output |
|---|---|---|
| TDD red | Collection failed because `load_package_archive` did not exist | Conversation output; expected missing-symbol failure |
| Bootstrap regression tests | 4 passed, including valid load, missing pin rejection, changed directory rejection, and parent overlay resolution | `F:\paralls-verification\thread-a\m5-3-archive-bootstrap-20261126-01\bootstrap.log` |
| Package migration, event schema, and rule-pack validator tests | 148 passed, 2 dependency deprecation warnings | `F:\paralls-verification\thread-a\m5-3-archive-bootstrap-20261126-01\targeted.log` |
| Environment | Python 3.12.2; `app.__file__` resolved inside this A worktree; SQLite 3.43.1 | `F:\paralls-verification\thread-a\m5-3-archive-bootstrap-20261126-01\environment.log` |
| M5-3 registered selection | 20 nodes, `problems=0 improvements=0` | `F:\paralls-verification\thread-a\m5-3-archive-bootstrap-20261126-01\m5-3-selection.json` |
| Frozen Ownership selection | 24 nodes, `problems=0 improvements=0` | `F:\paralls-verification\thread-a\m5-3-archive-bootstrap-20261126-01\ownership.json` |
| Frozen shared-replay selection | Incomplete. Ten 40-node batches completed with 40 passed each. Batch 11 stopped after five passed tests at `test_profile_repeated_in_one_run_receives_fresh_events[isolated-storage]`; no aggregate comparison result was produced | `F:\paralls-verification\thread-a\m5-3-archive-bootstrap-20261126-01\shared-replay.json` |

The shared-replay runner stall lasted over ten minutes with no log progress. The cause is unclassified, and the full 990-node selection is not verified. No unidentified process was terminated. The backend full suite was not run.

This bootstrap API does not define cross-language canonical serialization. `load_pack` still computes effective hashes using its existing Python implementation; the formal cross-language canonicalization decision remains open. There is still no production v2 package consumer, deployment manifest reader, or startup wiring. M6-5's tracked Gate environment template is recorded separately; no live production environment is configured. No change was made to `integration`.

## Shared-Replay Revalidation Follow-up (2026-11-26)

- Revalidated the current A tip `24b369c0` after the code-identical bootstrap commit `2a5d6640`. The profile-template commit after `2a5d6640` changed only `.env.example` and evidence/coordination files.
- The original stall was reproduced on the isolated-storage node. Pytest's faulthandler showed it blocked in `scripts/verification/common.py:_find_listener_pid` while waiting for the `powershell -NoProfile -Command Get-NetTCPConnection` subprocess. Before rerunning, `netstat -ano -p tcp` showed no listener on port 8000.
- A temporary F-drive `powershell.exe` name shim was used only for that listener lookup. The previously stalled node passed alone, then the complete frozen shared-replay comparison completed: `selected=990 problems=0 improvements=0`. No external process was stopped.
- Python `3.12.2`, SQLite `3.43.1`, `PYTHONPATH=F:/codex-temp/paralls-v2-thread-a-bond-20261121/backend`; `app.__file__` resolved under the A worktree. `TEMP`, `TMP`, pytest basetemp, comparator output, and raw logs were directed under `F:/paralls-verification/thread-a/m5-3-shared-replay-complete-20261126-01/`.
- Command: `python -B docs/verification/absorb-main-3bf3418e/compare_selection.py --repo F:/codex-temp/paralls-v2-thread-a-bond-20261121 --selection docs/verification/absorb-main-3bf3418e/shared-replay.json --output F:/paralls-verification/thread-a/m5-3-shared-replay-complete-20261126-01/shared-replay`.
- This completes the M5-3 shared-replay regression evidence for the current code state. It does not implement deployment manifest loading, a production package consumer/startup wiring, cross-language hash canonicalization, or a live production deployment. The backend full suite was not run.

## Historical replay regression and registered selections (2026-11-26)

At `c9a22c53`, Python 3.12.2 and SQLite 3.43.1 loaded `app` from the A worktree. Targeted migration and schema checks returned 35 passed and two warnings. The five frozen groups returned 1,169 node selections with zero problems and zero improvements.

The registered M5-3 selection ran at `c9a22c53`. The other 27 registered groups ran at `83d1dd12`. Only evidence documentation changed between those revisions. The counts below count a node once per group.

| Registered selection | Selected | Problems | Improvements |
|---|---:|---:|---:|
| m5-3-package-migration | 23 | 0 | 0 |
| m1-1-land-right-credential-compatibility | 1 | 0 | 0 |
| m1-2-holdings | 24 | 0 | 0 |
| m1-3-pool-domain-owner | 1 | 0 | 0 |
| m1-3-pool | 17 | 0 | 0 |
| m3-2-store-read-snapshot | 7 | 0 | 0 |
| m5-1-aggregation-models | 6 | 0 | 0 |
| m5-1-command-catalog | 14 | 0 | 0 |
| m5-1-cost-bindings | 5 | 0 | 0 |
| m5-1-entity-types | 5 | 0 | 0 |
| m5-1-impact-profiles | 7 | 0 | 0 |
| m5-1-pool-definitions | 9 | 0 | 0 |
| m5-2-parent-pack | 8 | 0 | 0 |
| m5-5-facttype-refold | 22 | 0 | 0 |
| m6-1-l5-dispatch-runtime | 5 | 0 | 0 |
| m6-1-reaction | 14 | 0 | 0 |
| m6-2-pipeline | 8 | 0 | 0 |
| m6-3-workflow | 8 | 0 | 0 |
| m6-4-play-pattern | 12 | 0 | 0 |
| m6-5-facility-integrity | 5 | 0 | 0 |
| m6-5-gate-profile-contract | 19 | 0 | 0 |
| m6-5-impact-gate-layered-execution | 21 | 0 | 0 |
| m6-5-information-report-source | 25 | 0 | 0 |
| m6-5-organization-roster | 3 | 0 | 0 |
| m6-5-place-output-types | 3 | 0 | 0 |
| m6-5-presence-passability | 6 | 0 | 0 |
| m6-5-production-wiring | 6 | 0 | 0 |
| siege_information | 25 | 0 | 0 |
| Total | 309 | 0 | 0 |

Raw comparator output and batch reports are under `F:/paralls-verification/thread-a/m5-3-history-20261126-01/`. The comparator was invoked with `--repo`, `--selection` and a distinct `--output` for each group. The full backend run was pending while thread B ran its full suite. Production startup with a trusted external archive manifest and cross-language hash canonicalization remain unverified.
