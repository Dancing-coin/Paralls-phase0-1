# M3-3 Investigation Conflict Resolve Replay Validation

## Scope

- Code commit: `0bb4b9e7`.
- `InvestigationConflictAuthority.resolve` now validates duplicate receipts with shared `replay_duplicate`, including the durable transaction, event references, and expected command and transaction identities.
- Replay integrity failures preserve the existing `idempotency_key_reused` rejection contract. Corrupt receipts return `rejected_zero_write` with no store mutation.
- No event schema, payload contract, or storage-core file changed. The action-window paths in the same runtime retain their existing behavior.

## TDD and Focused Verification

- RED changed a committed receipt's `command_id` while leaving its durable transaction intact. Before the fix, `resolve` returned `committed_success`; the assertion expected `rejected_zero_write`.
- Focused command: `F:\codex-temp\thread-a-python312\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\m3-3-investigation-conflict-replay-20261128-01\pytest-temp backend/tests/test_p5_investigation_conflict.py backend/tests/test_p5_bakery_theft_slice.py backend/tests/test_3d_scripted_mystery_action_replay.py backend/tests/test_action_conflict_window.py`.
- Result: `39 passed, 2 warnings`, exit 0. The test-module subset alone returned `18 passed, 2 warnings`.
- Environment: Python `3.12.2`; SQLite `3.43.1`; `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- Registered selection `m3-3-investigation-conflict-resolve-replay.json`: `selected=1 problems=0 improvements=0`.
- Frozen selections: ownership `24/0/0`, modifier `12/0/0`, equipment `87/0/0`, inventory `56/0/0`, shared-replay `990/0/0`; total `1,169` nodes, zero problems or improvements.

## Full Backend Regression

- Command: `F:\codex-temp\thread-a-python312\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\m3-3-investigation-conflict-replay-20261128-01\pytest-full-temp backend/tests`.
- Result: `10,823 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1. This is not a full-suite pass.
- The five failures were calibration repair contracts (`ModuleNotFoundError: tokenizers`), Task45 Godot parse probe, population cold-ready (`KeyError: resource_bounds`), population recovery measurement (`GIT_CONFIG_VALUE_0` missing config value in child process), and Task8 Godot parse probe.
- All five node IDs and failure types reproduced at direct parent `1127b431` in a targeted five-node run. That parent comparison is not a parent full-suite run.
- SQLite `3.43.1` is below the frozen baseline's `3.51.3` WAL-checkpoint requirement. Environment-gated nodes do not count as passed by frozen selections.

## Raw Evidence and Limits

- Raw logs and comparison outputs: `F:\paralls-verification\thread-a\m3-3-investigation-conflict-replay-20261128-01\`.
- P-1 scanned the added lines in code commit `0bb4b9e7` and this evidence/selection/coordination increment across five credential-pattern families. Result: `patterns-scanned=5 credential-pattern-hits=0`; raw output: `F:\paralls-verification\thread-a\m3-3-investigation-conflict-replay-20261128-01\p1-scan.log`.
- Selection comparison summaries: ownership `selected=24 problems=0 improvements=0`; modifier `12/0/0`; equipment `87/0/0`; inventory `56/0/0`; shared-replay `990/0/0`.
- `integration` was not modified. This increment does not configure production Gate numeric thresholds, establish end-to-end production dispatch, or complete M3-3. Other direct/custom replay paths remain to inventory.
