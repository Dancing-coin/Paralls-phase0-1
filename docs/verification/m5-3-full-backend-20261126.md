# A backend full regression at 7ab4d72e

## Environment and command

- Commit `7ab4d72e08ed2afa17db4deb8d1cac262f5dd50b`.
- Python `D:\Temp\paralls-g0-py312\Scripts\python.exe`, version `3.12.2`.
- `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- SQLite `3.43.1`.
- Command `python -B docs/verification/g0-939c6746/run_baseline.py --repo F:/codex-temp/paralls-v2-thread-a-bond-20261121 --output F:/paralls-verification/thread-a/m5-3-history-20261126-01/full-success/full --freeze`.
- Raw output and temporary files are under `F:/paralls-verification/thread-a/m5-3-history-20261126-01/full-success/`. Python 3.12.2 and the A worktree import path were verified before pytest. The output directory was unique.

## Result

- Exit code `1`. Collected `10,745`. Passed `10,718`. Failed `23`. Skipped `4`, including `2 xfailed`. Warnings `239`. Duration approximately `1,332.86 seconds`.
- Twenty-two failed node IDs also appear in the frozen README failure table. One additional node ID is absent: `tests/test_population_cold_ready_gate.py::test_cold_ready` (`AssertionError`). This is a node-ID comparison only, so the run is not reported as zero-difference.
- The additional node's assertion is `report["resource_bounds"]["passed"] == False`. Neither that test nor `scripts/verification/verify_population_long_session_recovery.py` nor `backend/app/population/` changed between `origin/integration` and this A tip. The finding is outside the Architecture v2 A scope and was not modified.
- The separate 28 registered selections remain 309 node selections with zero problems and zero improvements. The five frozen selections remain 1,169 nodes with zero problems and zero improvements.
- Two earlier launch attempts with bad path overrides were aborted and excluded. The process and malformed temporary directory owned by those attempts were cleaned. They did not change tracked source.

## Raw artifacts

- Console `F:/paralls-verification/thread-a/m5-3-history-20261126-01/full-success/full.log`.
- Structured results, JUnit, failure details, environment, collected node IDs, and frozen test manifest are in the same `full/` directory.
