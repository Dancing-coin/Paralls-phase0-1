# M3-3 Government Public Milling Notice Replay Validation

## Scope

Code commit `5f823c51fb34beede353acb8d9bf419df8b2f40f` routes duplicate retries in `GovernmentAuthority.record_public_milling_notice` through the shared `replay_duplicate` validator. The prior custom path matched the event type, command ID, source activity, validity window, causation, and correlation, but did not validate the durable transaction or complete event-reference vector. Those request-specific checks remain.

The regression corrupts the durable result's transaction ID after a successful notice append, retries the same request, and verifies rejection with no state changes after fault injection. Existing changed-window rejection and the public milling/Social acknowledgement paths remain covered. No event schema, payload, command contract, or storage-core code changed.

## Environment

- Branch: `thread-a/ownership-bond-followup-20261121`.
- Python: `3.12.2`, executable `F:\codex-temp\thread-a-python312\Scripts\python.exe`.
- SQLite: `3.43.1`.
- `PYTHONPATH`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`.
- `app.__file__`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.

## Verification

The regression was first run against the pre-change runtime and failed because the corrupted receipt returned `committed=True`, `idempotency_status='duplicate_replayed'`, and `transaction_id='transaction:missing'`.

Post-commit focused tests covered public milling notice, Social acknowledgement, and private follow-on callers:

```powershell
$env:PYTHONPATH='F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend'
$env:TEMP='F:\paralls-verification\thread-a\m3-3-government-public-milling-replay-20261128-01\temp-exact'
$env:TMP=$env:TEMP
& 'F:\codex-temp\thread-a-python312\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider --basetemp 'F:\paralls-verification\thread-a\m3-3-government-public-milling-replay-20261128-01\pytest-exact-temp' backend/tests/test_inf4am_public_milling_notice.py backend/tests/test_inf4ao_public_milling_social_ack.py backend/tests/test_private_follow_on_family.py
```

Result: `26 passed, 2 warnings in 0.83s`, exit code 0. Exact output: `F:\paralls-verification\thread-a\m3-3-government-public-milling-replay-20261128-01\pytest.log`.

Registered selection `docs/verification/selection/m3-3-government-public-milling-replay.json` at the code commit returned `selected=1 problems=0 improvements=0`. The frozen `absorb-main-3bf3418e` selections ran serially on the exact code commit:

| Selection | Selected | Problems | Improvements |
|---|---:|---:|---:|
| M3-3 public milling replay | 1 | 0 | 0 |
| Ownership | 24 | 0 | 0 |
| Modifier | 12 | 0 | 0 |
| Equipment | 87 | 0 | 0 |
| Inventory | 56 | 0 | 0 |
| shared-replay | 990 | 0 | 0 |

Raw selection output is under `F:\paralls-verification\thread-a\m3-3-government-public-milling-replay-20261128-01\`.

P-1 scanned 75 final staged added lines across five credential-pattern families. Result: `patterns-scanned=5 credential-pattern-hits=0`. Raw output: `F:\paralls-verification\thread-a\m3-3-government-public-milling-replay-20261128-01\p1-scan-final.log`.

## Status

This closes one Organization/Government custom replay path. M3-3 remains in progress because other direct/custom replay paths and other Owner domains are outside this increment. Full backend suite was not run. `integration` was not modified.
