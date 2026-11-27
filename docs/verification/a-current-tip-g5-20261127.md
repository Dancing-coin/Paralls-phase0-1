# A Current-Tip G5 Verification

## Baseline

- A branch: `thread-a/ownership-bond-followup-20261121`
- Commit: `01b0d1c330d0a7f4127c24ab9fb494f393922a9f`
- Python: `3.12.2`, executable `D:\Temp\paralls-g0-py312\Scripts\python.exe`
- SQLite: `3.43.1`
- Import check: `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`
- Git status before and after both contained only the pre-existing untracked `Godot/` tree.

## Registered Selections

All 45 files in `docs/verification/selection/*.json` were compared with `docs/verification/absorb-main-3bf3418e/compare_selection.py` at this commit. They contain 376 selected test nodes in total. Every file returned exit code 0 with `problems=0 improvements=0`.

The frozen ownership, modifier, equipment, inventory, and shared-replay selections were also run separately. Their sizes were 24, 12, 87, 56, and 990 respectively. Each returned `problems=0 improvements=0`.

Raw per-selection output and summaries are under `F:\paralls-verification\thread-a\a-tip-g5-20261127-02\`.

## Full Backend Results

The frozen G0 runner command was:

```powershell
& D:\Temp\paralls-g0-py312\Scripts\python.exe docs\verification\g0-939c6746\run_baseline.py `
  --repo F:\codex-temp\paralls-v2-thread-a-bond-20261121 `
  --output F:\paralls-verification\thread-a\a-tip-g5-20261127-02\full-backend-g0 `
  --freeze
```

It collected 10,819 nodes and returned `10,791 passed, 24 failed, 4 skipped`, exit 1. Its process ran pytest with the backend directory as the current working directory. The failure set included repository-root relative-path failures, child-process test-module import failures, and a malformed inherited Git configuration. This result is retained as the G0 runner output and is not treated as equivalent to the repository-root test entry point.

The repository-root command was:

```powershell
# Before running: PYTHONPATH=<A backend>; TEMP/TMP, PYTEST_DEBUG_TEMPROOT,
# PYTHONPYCACHEPREFIX, and --basetemp all point below the F-drive run directory;
# GIT_CONFIG_COUNT=0 avoids an inherited empty git-config value.
& D:\Temp\paralls-g0-py312\Scripts\python.exe -m pytest backend\tests -q -p no:cacheprovider `
  --basetemp=F:\paralls-verification\thread-a\a-tip-g5-20261127-02\full-backend-root-pytest\basetemp
```

It returned `10,811 passed, 4 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1, in 25:36. The four failures were:

- `tests/test_calibration_repair_contracts.py::test_all_22_repaired_budgets_equal_fixed_official_usage`
- `tests/test_character_task45_behavior.py::test_task45_headless_probe_observes_shared_path_and_contact_contract`
- `tests/test_population_cold_ready_gate.py::test_cold_ready`
- `tests/test_role_presentation_adapter_contract.py::test_task8_headless_registry_probe_resolves_profiles_and_blocks_rejected_registration`

These are within the five failure families previously reproduced on A tip `c821c558` and parent `e8c9f841`. The recovery-measurement failure from that run passed with `GIT_CONFIG_COUNT=0`. No current failure is attributed to the FactType instance resolver from this run. This remains a non-green full suite, not a pass.

The G0 runner log, frozen manifest, `results.json`, environment snapshot, and repository-root pytest log are under `F:\paralls-verification\thread-a\a-tip-g5-20261127-02\`. The G0 run created temporary test data under D through the inherited `PYTEST_DEBUG_TEMPROOT`; the 8,298 files (894 MiB) were moved to the F-drive evidence directory. The D source tree has no files remaining. Empty source directories remain because cleanup was blocked by the execution policy.

## Conclusion

- Registered selections: verified, zero differences.
- Frozen five selections: verified, zero differences.
- Full backend suite: executed, non-green, exit 1. Four repository-root failures remain in previously reproduced failure families.
- G0 full run: executed, non-green, with additional runner working-directory and environment-sensitive failures.
- M2-2 and U7 remain incomplete. The generic `read_as`, principal qualification, selector execution, and visibility enforcement are still absent.
