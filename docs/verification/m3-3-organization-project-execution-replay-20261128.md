# M3-3 Organization Project Execution Replay Receipt Validation

## Scope

`OrganizationAuthority.record_public_project_execution` previously searched for any committed event ID that resolved to the expected event type and then returned the stored result. A receipt containing the valid event ID plus an extra missing ID was therefore accepted as `duplicate_replayed`.

The duplicate path now validates the durable idempotency transaction with shared `replay_duplicate` before applying the existing source/revision/causation/correlation checks. Invalid receipts continue to reject with `public_project_execution_idempotency_key_reused`. Event type, payload, command behavior, and storage-core contracts are unchanged.

The new test commits a valid project execution, corrupts the durable result's event ID vector by adding a nonexistent ID, retries the exact request, and verifies rejection with an unchanged store snapshot after injection.

## Environment

- Branch: `thread-a/ownership-bond-followup-20261121`.
- Code/test/selection commit: `956fbe67689d893f61ce2e3d4d8e6d21710e4db8`.
- Python: `3.12.2`, executable `F:\codex-temp\thread-a-python312\Scripts\python.exe`.
- SQLite: `3.43.1`.
- `PYTHONPATH`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`.
- `app.__file__`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.

## Verification

TDD RED on the unmodified runtime returned `committed=True`, `idempotency_status='duplicate_replayed'` for the corrupted receipt. Raw output: `F:\paralls-verification\thread-a\m3-3-organization-project-execution-replay-20261128-01\pytest-red.log`.

Focused command:

```powershell
$env:PYTHONPATH='F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend'
$env:TEMP='F:\paralls-verification\thread-a\m3-3-organization-project-execution-replay-20261128-01\temp'
$env:TMP=$env:TEMP
& 'F:\codex-temp\thread-a-python312\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider --basetemp 'F:\paralls-verification\thread-a\m3-3-organization-project-execution-replay-20261128-01\pytest-temp-callers' backend/tests/test_inf4aj_public_project_execution.py backend/tests/test_inf4ak_public_project_execution_acknowledgment.py backend/tests/test_inf2ak_public_project_budget_close.py
```

Result: `19 passed, 2 warnings in 0.67s`, exit code 0. Raw output: `F:\paralls-verification\thread-a\m3-3-organization-project-execution-replay-20261128-01\pytest-callers.log`.

The registered regression and frozen selections were compared with `docs/verification/absorb-main-3bf3418e/compare_selection.py` on this code tree:

| Selection | Selected | Problems | Improvements |
|---|---:|---:|---:|
| Organization project execution receipt regression | 1 | 0 | 0 |
| Ownership | 24 | 0 | 0 |
| Modifier | 12 | 0 | 0 |
| Equipment | 87 | 0 | 0 |
| Inventory | 56 | 0 | 0 |
| shared-replay | 990 | 0 | 0 |

The exact summary output, per-batch artifacts, and environment verification are under `F:\paralls-verification\thread-a\m3-3-organization-project-execution-replay-20261128-02\`.

P-1 scanned code, test, selection, and communication additions across five credential-pattern families and returned `patterns-scanned=5 credential-pattern-hits=0`. Raw output: `F:\paralls-verification\thread-a\m3-3-organization-project-execution-replay-20261128-02\p1-code-scan.log`.

## Status

This closes the `record_public_project_execution` retry path only. `organization_government_runtime.py` is in a shared fourth-wave boundary; A notified B in `docs/v2-coordination/comms/2026-11-28-thread-a.md` and recorded the cross-domain scope. The full backend suite was not run. M3-3 remains in progress and `integration` was not modified.
