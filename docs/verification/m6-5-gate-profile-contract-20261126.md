# M6-5 Versioned Gate Profile Contract

Implementation commit: `d693686b`.

## Contract

- `FacilityGateProfileSettings` accepts explicit schema version 1 and defaults a missing version to 1 for existing local profiles.
- Unknown fields, non-finite numeric values, float/bool decimal values, invalid integrity bounds, invalid breach thresholds, invalid impact deltas, and invalid layered durability bounds are rejected.
- `.env.example` marks the exercised `gate-03` values as a demonstration profile. This change does not configure a production deployment or alter the ignored worktree `.env`.

## Environment

- Python `3.12.2`, SQLite `3.43.1`.
- `app.__file__`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- `PYTHONPATH`: the A worktree `backend` directory.
- `TEMP`, `TMP`, `TMPDIR`, and pytest `--basetemp` were under `F:\paralls-verification\thread-a\`.
- The interpreter is installed under `D:\Temp`; `-B` disabled bytecode writes. Test and verification output was directed to F:.

## Verification

| Check | Result | Raw output |
|---|---|---|
| Focused M6-5, layered Facility Gate, and config mode tests | `71 passed, 6 warnings in 3.26s` | `F:\paralls-verification\thread-a\m6-5-gate-profile-contract-20261126-06\pytest.log` |
| Registered profile contract selection | `selected=19 problems=0 improvements=0` | `F:\paralls-verification\thread-a\m6-5-gate-profile-contract-20261126-06\selection\` |
| Environment check | Python, SQLite, app path, and temp path recorded | `F:\paralls-verification\thread-a\m6-5-gate-profile-contract-20261126-06\environment.log` |
| Staged local five-family credential-pattern scans | `credential-pattern hits=0` for assignment, AWS/GitHub token, JWT, and private-key patterns | Code: `F:\paralls-verification\thread-a\m6-5-gate-profile-contract-20261126-06\p1-scan-corrected.log`; docs: `F:\paralls-verification\thread-a\m6-5-gate-profile-contract-20261126-06\p1-docs-scan-corrected.log` |
| Backend full suite | Interrupted after about 40 minutes at approximately 31%; two failure markers were visible before interruption, without node IDs or a summary. The failures are unclassified and the run is incomplete. | `F:\paralls-verification\thread-a\m6-5-gate-profile-contract-full-20261126-01\backend-suite.log` |
| First-failure diagnostic | `test_all_22_repaired_budgets_equal_fixed_official_usage` failed because the environment lacks `tokenizers`; current run: 1 failed, 286 passed, 8 warnings in 16.15s | `F:\paralls-verification\thread-a\m6-5-profile-first-failure-20261126-01\first-failure.log` |
| Parent comparison at `6d31a831` | The same node failed with the same `ModuleNotFoundError: No module named 'tokenizers'`; 1 failed, 2 warnings in 0.29s. This failure is baseline for the current environment. | `F:\paralls-verification\thread-a\m6-5-profile-parent-failure-20261126-01\parent-node.log` |

The backend full-suite attempt remains incomplete. The first observed failure is confirmed at the parent commit as a baseline environment failure. The second failure marker from the interrupted run remains unclassified. The profile contract selection and focused tests pass. No live production deployment, Unreal transport, or complete configured siege session was run. M6-5 remains in progress.
