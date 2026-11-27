# A tip full backend regression

- Current A tip: `c821c5582cb1169046641a1f96685085a78c619a`.
- Parent comparison tip: `e8c9f841b5b79045260b8ed023361c29b73fed48`.
- Command: `D:\Temp\paralls-g0-py312\Scripts\python.exe -m pytest backend\tests -q -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\a-tip-full-20261127-01\pytest-temp`, with `PYTHONPATH`, TEMP, TMP and PYTHONPYCACHEPREFIX under the F-drive run directory.

## Result

Current tip returned `10,783 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings`, exit code 1, elapsed 23:52.

The five failures were `test_all_22_repaired_budgets_equal_fixed_official_usage`, `test_task45_headless_probe_observes_shared_path_and_contact_contract`, `test_cold_ready`, `test_recovery_owner_probe_measures_original_startup_before_full_oracle`, and `test_task8_headless_registry_probe_resolves_profiles_and_blocks_rejected_registration`.

The same five node IDs were run at parent `e8c9f841` in a detached F-drive worktree. Parent result was `5 failed, 2 warnings`, with the same failure families. No failure was attributed to the FactType schema-ref retention or reverse-index changes.

This is merge-state regression evidence, not a full-suite pass. Current run files are under `F:\paralls-verification\thread-a\a-tip-full-20261127-01\`; parent comparison files are under `F:\paralls-verification\thread-a\a-parent-m2-2-20261127\`.

## Current A-tip full backend run, 2026-11-27 follow-up

- A-tip: `3e87cadbabe48411f48362158418245820865684`.
- Command: `F:\codex-temp\thread-a-python312\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\a-tip-backend-full-20261127-01\pytest-tmp backend/tests`.
- Environment: Python `3.12.2`, SQLite `3.43.1`, `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`, and `app.__file__` under the A worktree. `TEMP`, `TMP`, `TMPDIR`, pytest basetemp, and raw output were under the new F-drive run directory. `GIT_CONFIG_COUNT=0`; `PYTEST_ADDOPTS` was cleared.
- Raw result: `10,806 passed, 11 failed, 2 skipped, 2 xfailed, 227 warnings in 1494.01s`, exit code 1. Full console log: `F:\paralls-verification\thread-a\a-tip-backend-full-20261127-01\full.log`.
- Seven failures were `test_population_harness_evidence.py::test_nested_gameplay_evidence[...]` cases. Their tracebacks show `FileNotFoundError` creating a nested report under the long temporary root. Re-running the seven cases with a short F-drive temp root returned `7 passed, 33 deselected, 2 warnings in 5.65s`; raw output is `F:\paralls-verification\thread-a\p3\focused.log`.
- The remaining four failures are the frozen-baseline calibration dependency (`tokenizers` missing), the two Godot parser probes (`CharacterMotor` and `CharacterEmbodimentAssetRegistry` type resolution), and the known out-of-scope `test_cold_ready` resource-bounds assertion. The first three failure families appear in the frozen failure set; the `cold_ready` failure was previously reproduced outside the A code scope. Prior exact-parent evidence for these failure families is recorded above and in H-A-129/H-A-098. No current-parent rerun was performed for this follow-up.

The raw full run remains nonzero and is not reported as a full-suite pass. The seven path-sensitive cases are separately verified with the shorter temporary root; this does not replace the original full-run result or a clean full rerun.
