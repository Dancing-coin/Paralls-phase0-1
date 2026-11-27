# M3-3 Action Window Replay Validation

## Scope

- Code commit: `4409b6fe`.
- `resolve_action_window` now validates the durable transaction, command/transaction identity, four event references, event count/order/type, sequence, and stream revisions through `replay_duplicate` before replaying.
- Existing intent digest, caller command digest, role, and frozen caller-request checks remain. A damaged or mismatched receipt returns `action_window_idempotency_reused` without writes.
- The implementation changes an unassigned P5 runtime path under the user's continuing authorization. No storage core, event schema, or event payload contract changed.

## TDD and Focused Verification

- RED reproduced a corrupted append result `command_id` being returned as `duplicate_replayed` while all four events remained present.
- One initial grouped test run produced `51 passed, 3 errors` because the F-drive pytest basetemp parent had not been created. All three errors were `tmp_path` setup `FileNotFoundError`s. The run was repeated with the parent directory created.
- Python `3.12.2`, SQLite `3.43.1`, and `app.__file__` under the A worktree were verified.
- Focused tests covered `test_action_conflict_window.py`, `test_action_window_temporal_owner.py`, `test_action_temporal_application.py`, `test_action_consequence_boundaries.py`, `test_stormnight_action_loop.py`, and `test_stormnight_realtime_session.py`.
- Final result: `54 passed, 6 warnings`, exit 0. Raw focused log: `F:\paralls-verification\thread-a\m3-3-action-window-replay-20261128-01\focused.log`.
- Registered selection: `selected=1 problems=0 improvements=0`.
- Frozen selections: ownership `24/0/0`, modifier `12/0/0`, equipment `87/0/0`, inventory `56/0/0`, shared-replay `990/0/0`; total `1,169` nodes, zero problems or improvements.

## Full Backend Regression

- Command: `F:\codex-temp\thread-a-python312\Scripts\python.exe -B -m pytest -v -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\m3-3-action-window-replay-20261128-01\pytest-full-temp backend/tests`.
- Result: `10,822 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1. This is not a full-suite pass.
- Failures: calibration repair contract, Task45 headless probe, `test_cold_ready`, recovery measurement, and Task8 headless registry probe.
- All five node IDs and failure types reproduced at direct parent `d96317a4` in a targeted run: `5 failed, 2 warnings`. This was not a parent full-suite run. The first parent command had a misspelled Task8 node and was rejected during collection; the corrected command produced the recorded comparison.
- Full and parent logs: `F:\paralls-verification\thread-a\m3-3-action-window-replay-20261128-01\full-backend.log` and `parent-five-failures.log`.

## Limits

- Raw outputs are under `F:\paralls-verification\thread-a\m3-3-action-window-replay-20261128-01\`.
- P-1 branch-addition scan relative to `origin/integration` checked five credential-pattern families and found zero credential hits after excluding three explicit test-fixture placeholders. The excluded matches are recorded with file, line, pattern, SHA-256 prefix `66e7c82b`, and `public=no` in `p1-scan-branch-delta.log`; matched values were not emitted.
- SQLite `3.43.1` is below the frozen baseline's `3.51.3` WAL-checkpoint requirement; the two environment-gated nodes are not counted as passed by the baseline selections.
- This closes only the `resolve_action_window` duplicate path. Other direct/custom replay paths remain under M3-3 audit. No Owner/domain completion is implied.
- `Godot/` was preserved. `integration` was not modified.
