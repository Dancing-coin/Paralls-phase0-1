# M3-3 A-owned current-tip replay audit

- Snapshot: `684b4b1f5b1cc7b86189dc904900654488eda8e4` on `thread-a/ownership-bond-followup-20261121`.
- Environment: Python 3.12.2 from `D:\Temp\paralls-g0-py312\Scripts\python.exe`; `PYTHONPATH` resolved `app` to this worktree's `backend\app\__init__.py`; SQLite 3.43.1. Pytest temporary data was directed to `F:\paralls-verification\thread-a\m3-3-current-20261127-01\pytest-temp\`.
- Scope: A-owned replay/idempotency paths only. Shared storage and common-boundary modules were not modified.

## Static result

The migrated A-owned command paths in `credential_runtime.py`, `ownership_runtime.py`, `land_right_runtime.py`, `holdings_runtime.py`, `pool_runtime.py`, and `package_migration_runtime.py` use the shared `replay_duplicate` helper.

`OwnershipAuthorityService.grant_municipal_drought_assessment_certificate` remains a special settlement-plan path. It builds a `GameplayCommandEnvelope` after advisory and contract admission, and `SettlementPlan` derives the durable payload digest from the complete envelope. Its existing duplicate check also validates the committed certificate event against advisory, causation, and correlation fields. This path is recorded for a later contract-specific R2 decision rather than being changed by inference.

## Runtime result

Command:

```text
set PYTHONPATH=F:\\codex-temp\\paralls-v2-thread-a-bond-20261121\\backend
set TEMP=F:\\paralls-verification\\thread-a\\m3-3-current-20261127-01
set TMP=F:\\paralls-verification\\thread-a\\m3-3-current-20261127-01
D:\\Temp\\paralls-g0-py312\\Scripts\\python.exe -m pytest -q --basetemp=F:\\paralls-verification\\thread-a\\m3-3-current-20261127-01\\pytest-temp backend/tests/test_inf3u_municipal_certificate_government_acknowledgment.py backend/tests/test_inf4u_municipal_drought_assessment_certificate.py backend/tests/test_owner_runtime_base.py
```

Raw result: `17 passed, 2 warnings in 0.79s`. The full log is `F:\paralls-verification\thread-a\m3-3-current-20261127-01\pytest.log`.

## Conclusion

- A-owned migrated paths: verified at helper call-site level and covered by the prior M3-3 shared validation evidence.
- Municipal certificate path: static-only contract classification plus 17 passing focused tests. No behavior change was made.
- M3-3 remains in progress. Repository-wide R2 completion is not established.
