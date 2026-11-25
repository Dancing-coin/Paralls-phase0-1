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
| Production Gate values | Still unconfigured; this M5-3 unit does not configure them |

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

This bootstrap API does not define cross-language canonical serialization. `load_pack` still computes effective hashes using its existing Python implementation; the formal cross-language canonicalization decision remains open. There is still no production v2 package consumer, deployment manifest reader, or startup wiring. Production Gate values remain unconfigured, and no change was made to `integration`.
