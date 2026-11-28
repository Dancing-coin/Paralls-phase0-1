# M1-3 Pool checkpoint-free state digest recheck

Date: 2026-11-28

## Scope

Test commit `b398cddf3c7a784c2560e28880642619b5485afc` strengthens the Pool rebuild test. It uses the existing `DurableGameplayEventStore`, checks that its exported snapshot contains no projection checkpoints, closes the SQLite store, reopens the same event ledger, rebuilds the Pool projection from the event stream, and compares a canonical Pool state digest with the pre-close projection.

No Pool checkpoint deletion API or Pool projection cache exists in this path. This verifies the no-checkpoint rebuild branch for Pool state. It does not claim that a persisted Pool checkpoint was physically deleted, and it does not close M1-3 U5 across all domain paths.

## Environment and verification

- Branch: `thread-a/ownership-bond-followup-20261121`.
- Code/test commit: `b398cddf3c7a784c2560e28880642619b5485afc`.
- Python: `3.12.2`, executable `F:\codex-temp\thread-a-python312\Scripts\python.exe`.
- SQLite: `3.43.1`.
- `PYTHONPATH`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`.
- Import check: `app.__file__ = F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- Pytest temp and raw outputs: `F:\paralls-verification\thread-a\m1-3-pool-r3-checkpoint-free-20261128-02\`.

Focused Pool command:

```powershell
$env:PYTHONPATH='F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend'
& 'F:\codex-temp\thread-a-python312\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider --basetemp 'F:\paralls-verification\thread-a\m1-3-pool-r3-checkpoint-free-20261128-02\pool-file-temp' --junitxml 'F:\paralls-verification\thread-a\m1-3-pool-r3-checkpoint-free-20261128-02\pool-file-junit.xml' backend/tests/test_pool_runtime.py
```

Result: `19 passed, 2 warnings in 0.37s`. The warnings are the existing Starlette/httpx and AnyIO deprecations. The exact R3 regression node also passed independently: `1 passed, 2 warnings in 0.33s`.

Frozen-baseline selection comparisons used `docs/verification/absorb-main-3bf3418e/compare_selection.py` and the updated registered `docs/verification/selection/m1-3-pool.json`:

| Selection | Selected | Problems | Improvements |
|---|---:|---:|---:|
| M1-3 Pool | 33 | 0 | 0 |
| Ownership | 24 | 0 | 0 |
| Modifier | 12 | 0 | 0 |
| Equipment | 87 | 0 | 0 |
| Inventory | 56 | 0 | 0 |
| shared-replay | 990 | 0 | 0 |

All six comparisons ran serially. Raw logs and batch outputs are under `F:\paralls-verification\thread-a\m1-3-pool-r3-checkpoint-free-20261128-02\selection-runs\`. P-1 scanned both test commits across five credential-pattern families. Each scan returned `patterns-scanned=5 credential-pattern-hits=0`; raw outputs are `F:\paralls-verification\thread-a\m1-3-pool-r3-checkpoint-free-20261128-01\p1-code-scan.log` and `F:\paralls-verification\thread-a\m1-3-pool-r3-checkpoint-free-20261128-02\p1-code-scan.log`.

## Status

- Verified: Pool SQLite event-ledger reopen followed by checkpoint-free full rebuild yields the same canonical public projection state digest; the exported snapshot contains no projection checkpoints.
- Not verified: physical deletion of a persisted Pool projection checkpoint, because this Pool path does not create one; R3 coverage for other M1-3 consumers; the full backend suite.
- M1-3 remains in progress. No production runtime code, event contract, storage core, or `integration` branch changed.
