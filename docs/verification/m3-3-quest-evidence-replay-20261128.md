# M3-3 Quest Evidence Resolve Replay Validation

## Scope

- Code commit: `9ee8eb23`.
- `QuestEvidenceAuthority.resolve` now validates duplicate receipts through shared `replay_duplicate`, including durable transaction identity, committed event references, and expected command and transaction identities.
- Replay-integrity failures preserve the existing `idempotency_key_reused` rejection contract and return `rejected_zero_write` without changing the store.
- No event schema, payload contract, or storage-core file changed.

## TDD and Focused Verification

- RED changed the stored append receipt `command_id` while preserving its durable transaction. Before the fix, the retry returned `committed_success` instead of `rejected_zero_write`.
- Focused command: `F:\codex-temp\thread-a-python312\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\m3-3-quest-evidence-replay-20261128-01\pytest-temp backend/tests/test_p5_quest_evidence.py backend/tests/test_p5_bakery_theft_slice.py backend/tests/test_p5_investigation_conflict.py`.
- Result: `49 passed, 2 warnings`, exit 0.
- Environment: Python `3.12.2`; SQLite `3.43.1`; `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- Registered selection `m3-3-quest-evidence-resolve-replay.json`: `selected=1 problems=0 improvements=0`.
- Frozen selections: ownership `24/0/0`, modifier `12/0/0`, equipment `87/0/0`, inventory `56/0/0`, shared-replay `990/0/0`; total `1,169` nodes, zero problems or improvements.

## Full Backend Regression

- Command: `F:\codex-temp\thread-a-python312\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\m3-3-quest-evidence-replay-20261128-01\pytest-full-temp backend/tests`.
- Result: `10,824 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1. This is not a full-suite pass.
- Failures: calibration repair (`ModuleNotFoundError: tokenizers`), Task45 Godot parse probe, population cold-ready (`KeyError: resource_bounds`), population recovery measurement (`GIT_CONFIG_VALUE_0` missing config value in child process), and Task8 Godot parse probe.
- All five node IDs and failure types reproduced at direct parent `0bb4b9e7` in a targeted five-node run. This was not a parent full-suite run.
- SQLite `3.43.1` is below the frozen baseline's `3.51.3` WAL-checkpoint requirement. Environment-gated nodes do not count as passed by frozen selections.

## Raw Evidence and Limits

- Raw logs and comparison outputs: `F:\paralls-verification\thread-a\m3-3-quest-evidence-replay-20261128-01\`.
- P-1 scanned added code and documentation lines across five credential-pattern families. Result: `patterns-scanned=5 credential-pattern-hits=0`; raw output: `F:\paralls-verification\thread-a\m3-3-quest-evidence-replay-20261128-01\p1-scan.log`.
- M3-3 remains in progress. The `confirm_world_death` custom receipt path and other direct/custom replay paths remain to inventory. `integration` was not modified, and production Gate numeric thresholds remain unconfigured.
