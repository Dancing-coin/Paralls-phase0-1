# M3-3 private follow-on replay validation

## Scope

- Code commit: `c48503c196b1617d5383ec3be83500aae2414f60`.
- The legacy milling and package-generic workshop retry paths now route duplicate receipts through one private validation method backed by shared `replay_duplicate`.
- Validation covers the idempotency record, transaction/command identity, expected two actor-private acknowledgment events, committed event references, `private_follow_on@1`, source notice, causation, and correlation. Existing `private_follow_on_idempotency_key_reused` rejection and successful exact-retry behavior remain.
- No event schema, payload field, or event meaning changed. `social_knowledge.py` remains unassigned in `BOUNDARIES.md`; this narrow replay increment was handled under the user's continuing authorization. No boundary file or other thread-owned source changed.

## TDD and focused verification

- RED: both new corruption tests failed because retries returned `committed_success` after the transaction `command_id` was changed.
- GREEN environment: Python `3.12.2`; SQLite `3.43.1`; `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- Focused command: `F:\codex-temp\thread-a-python312\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\m3-3-private-follow-on-20261128-01\pytest-temp backend/tests/test_private_follow_on_family.py backend/tests/test_inf4ao_public_milling_social_ack.py backend/tests/test_p5_social_knowledge.py`.
- Result: `44 passed, 2 warnings`, exit 0. Raw output: `F:\paralls-verification\thread-a\m3-3-private-follow-on-20261128-01\focused.log`.
- Unit selection: `selected=2 problems=0 improvements=0`.
- Frozen selections: ownership 24, modifier 12, equipment 87, inventory 56, shared-replay 990. All returned zero problems and improvements, 1,169 selected nodes total.

## Full backend regression

- Command: `F:\codex-temp\thread-a-python312\Scripts\python.exe -B -m pytest -v -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\m3-3-private-follow-on-20261128-01\pytest-full-temp backend/tests`.
- Environment: Python `3.12.2`; SQLite `3.43.1`; `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`; `app.__file__` resolved under the A worktree. TEMP, TMP, pytest basetemp, and raw output were on F:.
- Result: `10,819 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings in 1718.95s`, exit 1. This is not a full-suite pass.
- The five failed nodes were rerun at direct parent `8b75524073978f8608ebd229002b37844b65be00` in a temporary F-drive worktree. All five failed there too: missing optional `tokenizers`, Task45 Godot parser errors, `test_cold_ready` missing `resource_bounds`, recovery measurement missing `GIT_CONFIG_VALUE_0`, and Task8 Godot parser errors. This is a five-node parent comparison, not a parent full-suite run.
- Full raw log: `F:\paralls-verification\thread-a\m3-3-private-follow-on-20261128-01\full-backend.log`. Parent comparison log: `F:\paralls-verification\thread-a\m3-3-private-follow-on-20261128-01\parent-five-failures.log`.

## Status and limits

- U1-U10: not applicable to this shared R2 increment; no Owner/domain migration is claimed.
- U11: covered by the registered two-node selection.
- M3-3 remains in progress. This closes the legacy and package-generic private follow-on retry paths only. Other direct/custom replay paths still require owner and contract review.
- No push, merge, or `integration` change was made. The existing untracked `Godot/` directory was preserved.
