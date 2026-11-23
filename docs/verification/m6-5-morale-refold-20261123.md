# M6-5 Morale refold from historical casualty inputs

## Unit

Commit `7ff3a3cb` adds `MoraleRefoldAuthority`. It consumes the Organization roster at the casualty event's global sequence and each roster member's canonical LifeState through that same sequence. Unknown or invalid sources reject with no Pool write. It writes only the configured Morale Pool under the Morale transaction principal. The confirmed `morale_refold@1` rule computes the living roster percentage.

## Environment and verification

- Python 3.12.2: `D:\Temp\paralls-g0-py312\Scripts\python.exe`.
- SQLite 3.43.1.
- Detached verification worktree at `7ff3a3cb`; `app.__file__` resolved to `F:\codex-temp\a-m6-5-morale-verify\backend\app\__init__.py`.
- Python tempdir resolved to `F:\paralls-verification\thread-a\m6-5-morale-refold-20261123-01\temp`.
- Targeted command: `python -m pytest backend/tests/test_morale_refold_runtime.py backend/tests/test_pool_runtime.py backend/tests/test_organization_government_social_platform_runtime.py backend/tests/test_life_state_case_death_caller.py -q`.
- Ownership frozen selection: `docs/verification/absorb-main-3bf3418e/ownership.json`.
- Shared-replay frozen selection: `docs/verification/absorb-main-3bf3418e/shared-replay.json`.
- Raw output: `F:\paralls-verification\thread-a\m6-5-morale-refold-20261123-01\`.

| Check | Result | Evidence level |
|---|---|---|
| Targeted tests | 49 passed, 2 warnings | Verified on detached commit |
| Ownership frozen selection | `selected=24 problems=0 improvements=0` | Verified on detached commit |
| Shared-replay frozen selection | `selected=990 problems=2 improvements=0` | Does not pass |
| Full suite | Not run | Unverified |
| Morale FactType U2 and authorized `read_as` visibility | Not established | Unverified |
| Production Gateway/L5 event dispatch | Not implemented | Unverified |

The two shared-replay mismatches are `test_profile_repeated_in_one_run_receives_fresh_events[isolated-storage]` and `[wall-clock]`. They attempt to start a fresh backend and fail because an external process occupies port 8000. The same signatures occurred on the previous Pool revision-pin commit. No external process was stopped.

The direct tests verify a four-member garrison with one casualty refolds 100 to 75, historical inputs are pinned separately from current CAS heads, an exact retry replays the original receipt after the Organization head advances, and a missing member LifeState produces zero writes.

## Compatibility and remaining coverage

- The writer reads existing Organization membership and LifeState events. It adds no source event type and does not duplicate those source facts.
- The Morale result is one configured Pool fact. No Presence fact is written.
- The component is independently tested. End-to-end L5 triggering, production trusted-output registration, registered Morale FactType scope, authorized reader visibility, full replay/checkpoint rebuild, and full-suite behavior remain unverified.
