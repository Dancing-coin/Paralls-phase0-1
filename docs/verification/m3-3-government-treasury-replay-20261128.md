# M3-3 Government Treasury Replay Receipt Validation

## Scope

`GovernmentTreasuryCollectorAuthority.admit_collector_account` previously compared the stored payload digest and then returned `get_by_idempotency` without validating the durable transaction or committed event references. The method now uses the shared `replay_duplicate` validator and maps its failures to Treasury rejection results.

The regression first creates a valid collector admission, corrupts its stored receipt by adding a nonexistent committed event ID, then retries the exact command. The retry rejects with `treasury_collector_replay_event_count_mismatch`; the event-store snapshot remains unchanged after fault injection. No event schema, persisted payload, shared storage file, or command contract changed.

## Environment

- Branch: `thread-a/ownership-bond-followup-20261121`.
- Base commit: `be9739a721e9872db04bc436c6d5610965b340e3`.
- Python: `3.12.2`, executable `F:\codex-temp\thread-a-python312\Scripts\python.exe`.
- SQLite: `3.43.1`.
- `PYTHONPATH`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`.
- `app.__file__`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.

## Verification

The focused test file was run with:

```powershell
$env:PYTHONPATH='F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend'
$env:TEMP='F:\paralls-verification\thread-a\m3-3-government-treasury-replay-20261128-02\temp'
$env:TMP=$env:TEMP
& 'F:\codex-temp\thread-a-python312\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider --basetemp 'F:\paralls-verification\thread-a\m3-3-government-treasury-replay-20261128-02\pytest-temp-focused' backend/tests/test_infra_economy_tax_payment_owner_admission.py
```

Result: `10 passed, 2 warnings in 0.22s`, exit code 0. Raw output: `F:\paralls-verification\thread-a\m3-3-government-treasury-replay-20261128-02\pytest-treasury.log`.

The registered Treasury regression and frozen selections were compared with `docs/verification/absorb-main-3bf3418e/compare_selection.py` against this worktree. Results:

| Selection | Selected | Problems | Improvements |
|---|---:|---:|---:|
| Treasury receipt regression | 1 | 0 | 0 |
| Ownership | 24 | 0 | 0 |
| Modifier | 12 | 0 | 0 |
| Equipment | 87 | 0 | 0 |
| Inventory | 56 | 0 | 0 |
| shared-replay | 990 | 0 | 0 |

Raw command output and per-batch runner artifacts are under `F:\paralls-verification\thread-a\m3-3-government-treasury-replay-20261128-02\`. The total is 1,170 selected node executions across groups, including overlapping nodes.

## Status

This closes one Government Treasury custom replay-receipt path only. `government_treasury_runtime.py` is not assigned in `BOUNDARIES.md`; A notified B in `docs/v2-coordination/comms/2026-11-28-thread-a.md` and marks the cross-domain scope in the daily record. M3-3 remains in progress. The full backend suite was not run. `integration` was not modified.
