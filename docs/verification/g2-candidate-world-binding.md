# Candidate world binding on reuse

A second continuity command could reuse an existing candidate ID with a
different world. The candidate and its recorded world were overwritten, so a
later materialization could use the wrong world's confirmed clock. A legacy
candidate without world provenance could likewise acquire one through another
command. Both cases were reproduced before the change in memory and after a
durable restart.

New commands now reject a reused candidate ID when its latest recorded world
differs, including a transition to or from missing provenance. Exact retries
still resolve their original receipt before this check, and reuse within the
same world retains the existing update behavior. The check precedes the new
command's writes. It reads event history only for reused IDs; the cost for long
histories has not been benchmarked. Existing conflicting history is not repaired,
and already materialized memories are not removed. This check relies on the
existing serialized runtime owner; direct concurrent writers and untrusted
cadence provenance are not fenced by this change. It is not general principal
visibility, full three-time support or authority epoch enforcement.

Focused verification, Windows 11 and Python 3.12.2: 222 passed, 8 warnings.
The new test first failed in all four memory/durable and known/unknown-world
combinations. It covers restart, exact retry, rejection before candidate
replacement and early materialization, plus same-world updates.

```powershell
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' -m pytest backend/tests/test_character_activation_known_world_time.py backend/tests/test_character_population_integrated_loop.py backend/tests/test_character_agent_seed_continuity.py backend/tests/test_character_session_recovery.py backend/tests/test_character_continuity_four_cursors.py backend/tests/test_population_seed_known_time.py backend/tests/test_character_activation_lease.py backend/tests/test_siming_population_capability.py backend/tests/test_siming_population_production_boundaries.py -q
& 'D:/Temp/paralls-g0-py312/Scripts/python.exe' docs/verification/g0-939c6746/run_baseline.py --repo . --output D:/Temp/paralls-g2-candidate-world-baseline-20261110 --freeze
```

Full G0-range run: 10,021 nodes, 9,978 passed, 39 failed, 2 skipped,
2 xfailed; no collection errors. All 9,937 G0 and 10,015 preceding nodes
retained their setup/call/teardown outcomes; six new nodes passed. All 39
failure node/phase/type signatures match the preceding run. Stack differences
were limited to pytest temporary-directory numbers and an AnyIO cancel-scope
ID; after normalizing those dynamic values all stacks matched. Python, OS,
package and dependency hashes and pytest environment matched; source, HEAD
and worktree status remained stable during the run. The
[evidence archive](g2-candidate-world-binding-evidence.zip) contains the
environment, frozen manifest, node list, invocation, JUnit, results and
failure details.

Rollback: revert this commit with the runtime stopped. No storage schema or
historical digest changed, but rollback again permits a candidate ID to acquire
another world's clock; inspect retained candidates and receipts before
resuming. D2-D10, the performance gate and B3 client acceptance remain open.
