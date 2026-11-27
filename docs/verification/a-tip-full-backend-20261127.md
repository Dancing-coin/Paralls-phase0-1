# A tip full backend regression

- Current A tip: `c821c5582cb1169046641a1f96685085a78c619a`.
- Parent comparison tip: `e8c9f841b5b79045260b8ed023361c29b73fed48`.
- Command: `D:\Temp\paralls-g0-py312\Scripts\python.exe -m pytest backend\tests -q -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\a-tip-full-20261127-01\pytest-temp`, with `PYTHONPATH`, TEMP, TMP and PYTHONPYCACHEPREFIX under the F-drive run directory.

## Result

Current tip returned `10,783 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings`, exit code 1, elapsed 23:52.

The five failures were `test_all_22_repaired_budgets_equal_fixed_official_usage`, `test_task45_headless_probe_observes_shared_path_and_contact_contract`, `test_cold_ready`, `test_recovery_owner_probe_measures_original_startup_before_full_oracle`, and `test_task8_headless_registry_probe_resolves_profiles_and_blocks_rejected_registration`.

The same five node IDs were run at parent `e8c9f841` in a detached F-drive worktree. Parent result was `5 failed, 2 warnings`, with the same failure families. No failure was attributed to the FactType schema-ref retention or reverse-index changes.

This is merge-state regression evidence, not a full-suite pass. Current run files are under `F:\paralls-verification\thread-a\a-tip-full-20261127-01\`; parent comparison files are under `F:\paralls-verification\thread-a\a-parent-m2-2-20261127\`.
