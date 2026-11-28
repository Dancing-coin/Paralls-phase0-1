# M3-3 Government Policy Registration Replay Validation

## Scope

Code commit `dff057516187091f916519b222546036dae5d49a` routes duplicate retries in `GovernmentAuthority.register_commercial_inspection_policy` through the shared `replay_duplicate` validator. The prior custom branch checked the committed event count, event type, and payload, but did not verify the durable transaction or that its committed event references matched the transaction. The caller still rejects a retry whose policy payload differs from the original request.

The regression corrupts the durable result's transaction ID after a successful append, retries the command, and verifies an `idempotency_key_reused` rejection with no changes to persisted events, outbox, or idempotency state after corruption injection. No event schema, payload, command contract, or storage-core code changed.

## Environment

- Branch: `thread-a/ownership-bond-followup-20261121`.
- Python: `3.12.2`, executable `F:\codex-temp\thread-a-python312\Scripts\python.exe`.
- SQLite: `3.43.1`.
- `PYTHONPATH`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`.
- `app.__file__`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.

## Verification

The test was first run against the pre-change runtime and failed because the corrupted receipt returned `committed=True` with `idempotency_status='duplicate_replayed'` and `transaction_id='transaction:missing'`.

Post-commit focused command:

```powershell
$env:PYTHONPATH='F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend'
$env:TEMP='F:\paralls-verification\thread-a\m3-3-government-policy-replay-20261128-01\temp-exact'
$env:TMP=$env:TEMP
& 'F:\codex-temp\thread-a-python312\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider --basetemp 'F:\paralls-verification\thread-a\m3-3-government-policy-replay-20261128-01\pytest-exact-temp' backend/tests/test_infra_government_policy_registration.py
```

Result: `10 passed, 2 warnings in 0.22s`, exit code 0. Exact output: `F:\paralls-verification\thread-a\m3-3-government-policy-replay-20261128-01\pytest-exact.log`.

Registered selection `docs/verification/selection/m3-3-government-policy-registration-replay.json` at the code commit returned `selected=1 problems=0 improvements=0`. Exact output: `F:\paralls-verification\thread-a\m3-3-government-policy-replay-20261128-01\selection-exact.log`.

The frozen baseline `absorb-main-3bf3418e` selections were run serially against the same source tree before committing the tested code. The runtime and test files were unchanged in commit `dff05751`:

| Selection | Selected | Problems | Improvements |
|---|---:|---:|---:|
| Ownership | 24 | 0 | 0 |
| Modifier | 12 | 0 | 0 |
| Equipment | 87 | 0 | 0 |
| Inventory | 56 | 0 | 0 |
| shared-replay | 990 | 0 | 0 |

Raw output for the registered and frozen selections is under `F:\paralls-verification\thread-a\m3-3-government-policy-replay-20261128-01\`.

P-1 scanned 76 final staged added lines across five credential-pattern families: assignment-shaped secret, AWS access key, GitHub token, JWT, and private-key header. Result: `patterns-scanned=5 credential-pattern-hits=0`. Raw output: `F:\paralls-verification\thread-a\m3-3-government-policy-replay-20261128-01\p1-scan-final.log`.

## Status

This closes one Organization/Government custom replay path. M3-3 remains in progress because other direct/custom replay paths and other Owner domains are outside this increment. Full backend suite was not run. `integration` was not modified.
