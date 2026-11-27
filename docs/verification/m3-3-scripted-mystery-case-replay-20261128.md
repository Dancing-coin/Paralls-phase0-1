# M3-3 Scripted Mystery Case Replay Validation

## Scope

- Code commits: `b6ca607d` and `8e6d70df`.
- `resolve_outcome` and `_append_phase` now validate duplicate receipts through `replay_duplicate`, including durable transaction identity, command identity, event references, event count, event type, and resulting revisions.
- Replayed events must match the request's case/phase or outcome identity and causation/correlation metadata. A damaged receipt returns `idempotency_key_reused` without appending events.
- Outcome `phase_ref` is captured event context rather than a retry input. Exact retry validates that stored context while checking the requested outcome and case identity.
- The paths are in an unassigned file under the user's continuing authorization. `BOUNDARIES.md`, other thread-owned files, and `integration` were not changed.

## TDD and Final-Tip Focused Verification

- RED at parent `15a25e07`: both new corruption tests returned `committed=True` after the stored append result's `command_id` diverged from the durable transaction.
- Initial GREEN: `backend/tests/test_scripted_mystery_case_runtime.py` returned `7 passed, 2 warnings`.
- Final-tip GREEN after `8e6d70df`: Python `3.12.2`; SQLite `3.43.1`; `app.__file__` resolved to the A worktree.
- Focused command covered `test_scripted_mystery_case_runtime.py`, `test_stormnight_action_loop.py`, `test_stormnight_owner_handoff.py`, `test_stormnight_scenario.py`, `test_stormnight_case_template_genericity.py`, and `test_stormnight_copper_sanatorium_full_replay.py`.
- Final result: `26 passed, 2 warnings`, exit 0.
- Registered unit selection: `selected=2 problems=0 improvements=0`.
- Final-tip frozen selections: ownership `24/0/0`, modifier `12/0/0`, equipment `87/0/0`, inventory `56/0/0`, shared-replay `990/0/0`; total `1,169` selected nodes with zero problems or improvements.

## Full Backend Regression

- The full backend run was performed on `b6ca607d`, before the one-line outcome context refinement in `8e6d70df`.
- Command: `F:\codex-temp\thread-a-python312\Scripts\python.exe -B -m pytest -v -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\m3-3-scripted-mystery-case-replay-20261128-01\pytest-full-temp backend/tests`.
- Result: `10,821 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1. This is not a full-suite pass.
- The five failures were `test_all_22_repaired_budgets_equal_fixed_official_usage`, Task45 headless probe, `test_cold_ready`, recovery measurement, and Task8 headless registry probe.
- All five nodes were rerun at direct parent `15a25e07`; result: `5 failed, 2 warnings`. The same five node IDs failed with the same failure types. This was a targeted parent comparison, not a parent full-suite run.
- Full and parent logs: `F:\paralls-verification\thread-a\m3-3-scripted-mystery-case-replay-20261128-01\full-backend.log` and `parent-five-failures.log`.

## Evidence and Limits

- All raw focused, frozen-selection, full-suite, and parent-comparison outputs are under `F:\paralls-verification\thread-a\m3-3-scripted-mystery-case-replay-20261128-01\`.
- Python `3.12.2` and A-worktree import path were verified. SQLite `3.43.1` remains below the frozen baseline's `3.51.3` WAL-checkpoint requirement, so those two environment-gated nodes are not counted as passed by the baseline selections.
- Final-tip full backend suite was not rerun after `8e6d70df`. Domain U1-U10 and overall M3-3 completion remain open.
- `Godot/` was preserved. No `integration` modification or push was made in this increment.
