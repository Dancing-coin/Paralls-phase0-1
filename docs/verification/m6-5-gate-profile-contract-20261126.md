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
| Backend full suite | Interrupted after about 40 minutes at approximately 31%; two failure markers were visible. Both were later located and reproduced on parent `6d31a831`; this run remains incomplete. | `F:\paralls-verification\thread-a\m6-5-gate-profile-contract-full-20261126-01\backend-suite.log` |
| First-failure diagnostic | `test_all_22_repaired_budgets_equal_fixed_official_usage` failed because the environment lacks `tokenizers`; current run: 1 failed, 286 passed, 8 warnings in 16.15s | `F:\paralls-verification\thread-a\m6-5-profile-first-failure-20261126-01\first-failure.log` |
| Parent comparison at `6d31a831` | The same node failed with the same `ModuleNotFoundError: No module named 'tokenizers'`; 1 failed, 2 warnings in 0.29s. This failure is baseline for the current environment. | `F:\paralls-verification\thread-a\m6-5-profile-parent-failure-20261126-01\parent-node.log` |

## Interrupted Full-Suite Failure Triage (2026-11-26)

Collection recorded `10737 tests collected in 4.97s`. The second progress marker was node 2308, `tests/test_character_task45_behavior.py::test_task45_headless_probe_observes_shared_path_and_contact_contract`. The node was rerun at current commit `cdf99158` and parent `6d31a831`. Both runs failed with the same Godot 4.6.3 parse errors: `CharacterMotor` could not be resolved in `CharacterTask45Probe.gd` at lines 85, 173, and 197, followed by type-inference errors for `records` and `evidence_only` at lines 103 and 107.

| Check | Result | Raw output |
|---|---|---|
| Full-suite collection and node order | `10737 tests collected in 4.97s`; the second failure was node 2308 | `F:\paralls-verification\thread-a\m6-5-full-failure-triage-20261126-01\collected.txt` |
| Current-tip exact node | `1 failed, 2 warnings in 0.88s`; Godot parse errors described above | `F:\paralls-verification\thread-a\m6-5-full-failure-triage-20261126-01\current-task45.log` |
| Parent exact node | `1 failed, 2 warnings in 0.64s`; same Godot parse errors | `F:\paralls-verification\thread-a\m6-5-full-failure-triage-20261126-01\parent-task45.log` |
| Neighboring isolated tests | Turn context `9 passed`; turn recovery, embodied episode, and worktable capability `10 passed`; worktable vertical `5 passed`; closed generic family contracts `20 passed` | `F:\paralls-verification\thread-a\m6-5-full-failure-triage-20261126-01\turn-context.log`, `turn-recovery-capability.log`, `worktable-vertical.log`, and `closed-generic-families.log` |

Both visible failures from the interrupted suite are reproduced at the parent SHA. This classifies them as pre-existing environment/repository failures for this change. The backend full suite remains incomplete and is not a pass. The Godot probe was not modified because it is outside the Gate profile unit. Python 3.12.2 remained at its existing D-drive location with `-B`; `app.__file__` resolved to the A worktree. `PYTHONPATH`, pytest temp directories, and retained outputs were on F:. Environment output: `F:\paralls-verification\thread-a\m6-5-full-failure-triage-20261126-01\environment.log`.

The backend full-suite attempt remains incomplete. Both observed failures were reproduced on parent commit `6d31a831` with matching errors, so neither is attributed to the Gate profile change. The profile contract selection and focused tests pass. No live production deployment, Unreal transport, or complete configured siege session was run. M6-5 remains in progress.
