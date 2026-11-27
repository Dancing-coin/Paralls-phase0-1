# M3-3 SocialDelivery replay validation

## Scope

- Code commit: `aeb339a3aec3c59f4f50667bb9f8a751188965db`.
- `SocialDeliveryAuthority.record_delivery` and `expire_delivery` now validate durable duplicate receipts through `replay_duplicate` before returning a replay result.
- The paths retain the existing `idempotency_key_reused` rejection, `duplicate_replayed` result code, original receipt shape, current/legacy recorded event support, and zero-write rejection behavior.
- The file `backend/app/gameplay/p5/social_delivery.py` was not assigned in `BOUNDARIES.md`. This increment is explicitly taken on by A under the user's continuing full authorization. `BOUNDARIES.md` itself was not changed.
- Unit class: shared R2 mechanism increment. U1-U10 are not domain migration acceptance criteria for this unit. No domain migration completion is implied.

## Regression evidence

- TDD red: both new transaction-metadata mismatch tests failed because the old paths returned `duplicate_replayed` when the transaction `command_id` disagreed with the result receipt. Raw output: `F:/paralls-verification/thread-a/m3-3-social-delivery-20261127-02/red.log`.
- Focused SocialDelivery, caller and Information tests: `69 passed, 6 warnings`, exit 0. Python `3.12.2`, SQLite `3.43.1`; `app.__file__` resolved to the A worktree. Raw output: `F:/paralls-verification/thread-a/m3-3-social-delivery-20261127-04/focused.log`.
- New registered selection: `selected=2 problems=0 improvements=0`.
- Frozen selections: ownership 24, modifier 12, equipment 87, inventory 56, shared-replay 990; all five returned zero problems and improvements, 1,169 nodes total.
- All 47 registered selections completed with exit 0 and zero problems/improvements per selection, including the new SocialDelivery selection. Raw batch logs: `F:/paralls-verification/thread-a/m3-3-social-delivery-20261127-05/selections/`.
- P-1 scan covered 133 added lines across the branch code delta and staged documentation. Assignment-shaped secret, AWS access key, GitHub token, JWT and private-key-header rules each reported zero hits. Raw output: `F:/paralls-verification/thread-a/m3-3-social-delivery-20261128-02/p1-scan.log`.

## Full backend regression

- Command: `F:/codex-temp/thread-a-python312/Scripts/python.exe -B -m pytest -v -p no:cacheprovider --basetemp F:/paralls-verification/thread-a/m3-3-social-delivery-20261127-06/pytest-temp backend/tests`.
- Environment: Python `3.12.2`, SQLite `3.43.1`, `PYTHONPATH=F:/codex-temp/paralls-v2-thread-a-bond-20261121/backend`, and `app.__file__` under this A worktree. TEMP, TMP, TMPDIR, bytecode cache and pytest basetemp were on F:.
- Result: `10,805 passed, 14 failed, 2 skipped, 2 xfailed, 227 warnings in 1486.31s`, exit 1. Raw output: `F:/paralls-verification/thread-a/m3-3-social-delivery-20261127-06/full-backend.log`.
- Four failure families match the prior A-tip record: missing optional `tokenizers`, Task45 and Task8 Godot type resolution, and the known `test_cold_ready` resource-bound assertion. This run did not repeat a parent full-suite comparison.
- Ten other failed cases passed in focused reruns: nested harness evidence cases `14 passed, 26 deselected` with short F-drive TEMP; process-cognition recovery variants `4 passed`; recovery measurement `1 passed` after setting `GIT_CONFIG_COUNT=0`. Raw outputs: `F:/paralls-verification/thread-a/m3-3-social-delivery-20261128-01/`, `F:/paralls-verification/thread-a/m3-3-social-delivery-20261128-07/`, and `F:/paralls-verification/thread-a/m3-3-social-delivery-20261128-08/`.
- Full backend regression remains non-green. The isolated reruns do not replace the full-run result.

## Remaining

- M3-3 remains in progress. Other direct/custom replay paths remain outside this increment and require per-file ownership and contracts.
- No persistent event schema changed. `integration` was not modified.
