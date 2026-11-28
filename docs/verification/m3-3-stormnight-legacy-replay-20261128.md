# M3-3 Stormnight Legacy Action Replay Validation

## Scope

- Code commit: `20934a37`.
- The legacy-compatible `StormnightRealtimeSessionService` action retry now validates the durable transaction, complete ordered four-event set, global sequence, and resulting stream revisions through shared `replay_duplicate` before returning a prior receipt.
- Existing frozen caller digest checks and the legacy rule requiring an in-process matching request remain. Corrupt receipts return `stormnight_player_idempotency_reused` without writes.
- No persisted event, event schema, storage-core file, or public command contract changed.

## TDD and Focused Verification

- RED changed the durable append result `command_id` after a legacy-mode action committed. Before the fix, the same-process retry returned `accepted=true` and `duplicate_replayed`; the regression expects rejection and unchanged event/transaction counts.
- Focused command: `F:\codex-temp\thread-a-python312\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\m3-3-stormnight-replay-20261128-02\pytest-focused backend/tests/test_stormnight_realtime_session.py backend/tests/test_action_conflict_window.py backend/tests/test_action_consequence_boundaries.py backend/tests/test_action_window_temporal_owner.py backend/tests/test_action_temporal_application.py backend/tests/test_stormnight_action_loop.py`.
- Result: `56 passed, 6 warnings`, exit 0. The new test alone failed first with `accepted=true`, then passed after the fix.
- Environment: Python `3.12.2`; SQLite `3.43.1`; `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- Registered selection `m3-3-stormnight-legacy-replay.json`: `selected=1 problems=0 improvements=0`.
- Frozen selections: ownership `24/0/0`, modifier `12/0/0`, equipment `87/0/0`, inventory `56/0/0`, shared-replay `990/0/0`; total `1,169` nodes with zero problems or improvements.

## Full Backend Regression

- Command: `F:\codex-temp\thread-a-python312\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\m3-3-stormnight-replay-20261128-02\pytest-full-temp backend/tests`.
- Result: `10,826 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1. This is not a full-suite pass.
- The five failures were the missing `tokenizers` calibration contract, Task45 Godot parse probe, population cold-ready `KeyError: resource_bounds`, population recovery measurement missing `GIT_CONFIG_VALUE_0`, and Task8 Godot parse probe.
- All five node IDs and failure types reproduced at direct parent `5e178aeb` in a targeted run (`5 failed, 2 warnings`). This was not a parent full-suite run.
- The frozen selection environment uses SQLite `3.43.1`, below the `3.51.3` WAL-checkpoint baseline requirement. Environment-gated nodes are not counted as passed by those selections.

## Raw Evidence and Limits

- Raw logs and comparison outputs: `F:\paralls-verification\thread-a\m3-3-stormnight-replay-20261128-02\`.
- P-1 scanned code/test additions and documentation additions separately across five credential-pattern families. Both results were `patterns-scanned=5 credential-pattern-hits=0`; raw outputs: `F:\paralls-verification\thread-a\m3-3-stormnight-replay-20261128-02\p1-code-scan.log` and `F:\paralls-verification\thread-a\m3-3-stormnight-replay-20261128-02\p1-docs-scan.log`.
- The implementation closes the legacy-compatible realtime adapter path only. Other direct/custom replay paths remain outside this increment; M3-3 remains in progress. `integration` was not modified.
