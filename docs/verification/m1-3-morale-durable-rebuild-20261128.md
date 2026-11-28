# M1-3 Morale durable Pool rebuild recheck

Date: 2026-11-28

## Scope

Code/test commit `02534c86` adds a Morale consumer regression for the checkpoint-free Pool projection path. It creates four historical garrison members and one death event in `DurableGameplayEventStore`, commits the casualty-driven Morale refold, closes and reopens the SQLite event ledger, then compares the canonical Pool projection digest and public projection object.

The snapshot is asserted to contain no projection checkpoints. This verifies durable close/reopen and full Morale Pool event replay without a checkpoint. It does not physically delete a persisted checkpoint, because `MoraleRefoldAuthority.projection` delegates to `PoolProjector.rebuild`, which accepts an event sequence and does not read or write projection checkpoints. R3 remains partial across the migration unit.

## Environment and focused verification

- Branch: `thread-a/ownership-bond-followup-20261121`.
- Code/test commit: `02534c86`.
- Python: `3.12.2`, executable `F:\codex-temp\thread-a-python312\Scripts\python.exe`.
- SQLite: `3.43.1`.
- `PYTHONPATH`: `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`.
- Import check: `app.__file__ = F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- Pytest temporary files and raw output: `F:\paralls-verification\thread-a\m1-3-morale-durable-rebuild-20261128-01\`.

The full focused file command was:

```powershell
$env:PYTHONPATH='F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend'
& 'F:\codex-temp\thread-a-python312\Scripts\python.exe' -B -m pytest -q -p no:cacheprovider --basetemp 'F:\paralls-verification\thread-a\m1-3-morale-durable-rebuild-20261128-01\morale-file-temp' --junitxml 'F:\paralls-verification\thread-a\m1-3-morale-durable-rebuild-20261128-01\morale-file-junit.xml' backend/tests/test_morale_refold_runtime.py
```

Result: `6 passed, 2 warnings in 0.35s`. Raw output is `F:\paralls-verification\thread-a\m1-3-morale-durable-rebuild-20261128-01\morale-file.log`.

The new node also passed independently: `1 passed, 2 warnings in 0.31s`. Its raw output is `F:\paralls-verification\thread-a\m1-3-morale-durable-rebuild-20261128-01\pytest.log`.

## Frozen selection results

All comparisons used `docs/verification/absorb-main-3bf3418e/compare_selection.py`, the updated M1-3 selection, and the frozen baseline manifests. They ran serially with Python `3.12.2` and the A-worktree `app.__file__` verified before each comparison.

| Selection | Selected | Problems | Improvements |
|---|---:|---:|---:|
| M1-3 Pool | 35 | 0 | 0 |
| Ownership | 24 | 0 | 0 |
| Modifier | 12 | 0 | 0 |
| Equipment | 87 | 0 | 0 |
| Inventory | 56 | 0 | 0 |
| shared-replay | 990 | 0 | 0 |

Raw comparison output is under `F:\paralls-verification\thread-a\m1-3-morale-durable-rebuild-20261128-01\selection-<name>\` with per-run summaries alongside each selection directory.

## Status

- Verified: Morale Pool state is reconstructed from the durable event ledger after SQLite close/reopen and matches the pre-close canonical digest.
- Not verified: deletion of a real Morale/Pool checkpoint, checkpoint deletion for other M1-3 consumers, full backend suite, and production checkpoint integration.
- U5 remains partial. U1's Morale Owner classification/declaration gap, U7 subject-facing read, U9 post-freeze declaration probe, production Pool scheduler/content, and complete G5 execution remain open or unverified. `integration` was not modified.
