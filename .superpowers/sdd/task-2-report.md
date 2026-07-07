Status: DONE

Summary:
- Added deterministic `SimingQualityMonitor` with narrative-aware quality signals and fairness snapshot output.
- Added focused Task 2 regression tests from the brief and verified the red-to-green TDD cycle.
- Kept `SimingFairnessAuditEngine.DEFAULT_DIMENSIONS` aligned with the new monitor's required dimension set through a minimal adjacent import-only fix.

Files changed:
- `backend/app/services/siming_quality_monitor.py`
- `backend/app/services/siming_fairness_audit.py`
- `backend/tests/test_siming_quality_monitor.py`

TDD evidence:
1. Wrote `backend/tests/test_siming_quality_monitor.py` exactly as specified in the task brief.
2. Ran `python -m pytest backend/tests/test_siming_quality_monitor.py -v`.
3. Observed expected red failure:
   - `ModuleNotFoundError: No module named 'app.services.siming_quality_monitor'`
4. Implemented the minimal production code to satisfy the tests.
5. Re-ran `python -m pytest backend/tests/test_siming_quality_monitor.py -v`.
6. Observed green:
   - `2 passed`

Additional verification:
- `python -m pytest backend/tests/test_siming_fairness_registry.py -v`
  - `13 passed`

Notes:
- The current Task 2 brief required a new narrative-aware monitor but did not require wiring it into `SimingRuntime.tick(...)` yet.
- The existing fairness audit service still returns placeholder `0.5` scores for its legacy snapshot path; Task 2 introduces the deterministic quality-monitor seam without changing runtime behavior outside the owned surfaces.

Commit:
- Created after staging only the Task 2 files listed above.
