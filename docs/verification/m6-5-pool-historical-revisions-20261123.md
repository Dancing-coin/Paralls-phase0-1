# M6-5 Pool historical input revision pins

## Unit

Commit `da8fa3b82eadc0bcd33d4c7dd32bbcf838b1a56d` separates Pool model input revision pins from current owner-commit read revisions. Historical Organization and LifeState revisions remain provenance pins. The current stream heads are independently checked by the Owner commit CAS. Calls that provide only `input_revision_vector` retain the original read-set behavior.

## Environment and commands

- Python: `D:\Temp\paralls-g0-py312\Scripts\python.exe`, Python 3.12.2.
- SQLite: 3.43.1.
- Verification worktree: `F:\codex-temp\a-m6-5-pool-verify` at the commit above. `app.__file__` resolved to `F:\codex-temp\a-m6-5-pool-verify\backend\app\__init__.py`.
- Targeted command: `python -m pytest backend/tests/test_pool_runtime.py backend/tests/test_organization_government_social_platform_runtime.py backend/tests/test_facility_integrity_runtime.py backend/tests/test_life_state_case_death_caller.py -q`.
- Ownership selection: `compare_selection.py --selection docs/verification/absorb-main-3bf3418e/ownership.json`.
- Shared replay selection: `compare_selection.py --selection docs/verification/absorb-main-3bf3418e/shared-replay.json`.
- Run output: `F:\paralls-verification\thread-a\m6-5-pool-historical-revisions-20261123-01\`.

## Results

| Check | Result | Evidence level |
|---|---|---|
| Targeted tests | 51 passed, 2 warnings | Verified on detached commit |
| Ownership frozen selection | `selected=24 problems=0 improvements=0` | Verified on detached commit |
| Shared-replay frozen selection | `selected=990 problems=2 improvements=0` | Does not pass |
| Full suite | Not run | Unverified |

The two shared-replay failures are `test_profile_repeated_in_one_run_receives_fresh_events[isolated-storage]` and `[wall-clock]`. Both attempted to start a fresh backend on port 8000 and failed because an external listener occupied the port. A direct rerun reproduced the same failure and the test cleanup reported `harness_cleanup=passed`. No external process was stopped.

The shared-replay run therefore does not establish a clean 990-node result. This unit's targeted and ownership selection results remain separately attributable to the detached commit.

## Compatibility and remaining coverage

- Existing Pool adjustment callers that omit `read_stream_revisions` keep their prior revision-vector read and pin behavior.
- New historical refolds can pin source revisions at an event's global-sequence cut while using current source heads for CAS.
- Morale and Presence writer behavior, production Gateway/L5 dispatch, and full-suite behavior are not covered by this unit.
- Verification runner temporary roots are removed by their cleanup. The test output showed a proposed `D:\codex-temp\user-temp\paralls-session-*` runtime path, but those named directories did not exist after cleanup. All retained verification output is under F:.
