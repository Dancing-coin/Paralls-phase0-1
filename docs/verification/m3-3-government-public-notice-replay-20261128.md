# M3-3 Government Public Workshop Notice Replay Validation

## Scope

Code commit `e1b520d17af37112239ea93c0c35695dfe66186b` routes duplicate retries in `GovernmentAuthority.record_public_workshop_notice` through the shared `replay_duplicate` validator. The prior path searched committed event IDs for a matching type and checked source activity, causation, and correlation, but did not validate the durable transaction or event-reference vector. Existing request-matching checks and the domain-specific rejection code remain.

The regression corrupts the durable result's transaction ID after a successful notice append, retries the same request, and verifies rejection with no state changes after fault injection. No event schema, payload, command contract, or storage-core code changed.

## Environment

- Branch: `thread-a/ownership-bond-followup-20261121`.
- Python: `3.12.2`, executable `F:\codex-temp\thread-a-python312\Scripts\python.exe`.
- SQLite: `3.43.1`.
- `PYTHONPATH`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`.
- `app.__file__`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.

## Verification

The regression was first run against the pre-change runtime and failed because the corrupted receipt returned `committed=True`, `idempotency_status='duplicate_replayed'`, and `transaction_id='transaction:missing'`.

Post-commit focused tests covered the public notice and Social private follow-on callers:

```powershell
$env:PYTHONPATH='F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend'
$env:TEMP='F:\paralls-verification\thread-a\m3-3-government-public-notice-replay-20261128-01\temp-exact'
$env:TMP=$env:TEMP
& 'F:\codex-temp\thread-a-python312\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider --basetemp 'F:\paralls-verification\thread-a\m3-3-government-public-notice-replay-20261128-01\pytest-exact-temp' backend/tests/test_inf4ah_public_workshop_notice.py backend/tests/test_private_follow_on_family.py
```

Result: `17 passed, 2 warnings in 0.54s`, exit code 0. Exact output: `F:\paralls-verification\thread-a\m3-3-government-public-notice-replay-20261128-01\pytest.log`.

Registered selection `docs/verification/selection/m3-3-government-public-notice-replay.json` at the code commit returned `selected=1 problems=0 improvements=0`. The frozen `absorb-main-3bf3418e` selections ran serially on the exact code commit:

| Selection | Selected | Problems | Improvements |
|---|---:|---:|---:|
| M3-3 public notice replay | 1 | 0 | 0 |
| Ownership | 24 | 0 | 0 |
| Modifier | 12 | 0 | 0 |
| Equipment | 87 | 0 | 0 |
| Inventory | 56 | 0 | 0 |
| shared-replay | 990 | 0 | 0 |

Raw selection output is under `F:\paralls-verification\thread-a\m3-3-government-public-notice-replay-20261128-01\`.

P-1 scanned 75 final staged added lines across five credential-pattern families. Result: `patterns-scanned=5 credential-pattern-hits=0`. Raw output: `F:\paralls-verification\thread-a\m3-3-government-public-notice-replay-20261128-01\p1-scan-final.log`.

## Status

This closes one Organization/Government custom replay path. M3-3 remains in progress because other direct/custom replay paths and other Owner domains are outside this increment. Full backend suite was not run. `integration` was not modified.
