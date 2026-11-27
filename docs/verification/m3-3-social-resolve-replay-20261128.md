# M3-3 SocialFactAuthority resolve replay validation

## Scope

- Code commit: `8b75524073978f8608ebd229002b37844b65be00`.
- `SocialFactAuthority.resolve` now validates duplicate P5 fact and revocation receipts through the shared `replay_duplicate` helper. It checks the request digest, expected command and transaction IDs, committed event references, and the event types implied by the committed command payload.
- Corrupt durable transaction metadata returns the existing `idempotency_key_reused` zero-write rejection. Event schemas, payloads, and normal exact-retry behavior are unchanged.
- `backend/app/gameplay/p5/social_knowledge.py` is not explicitly assigned in `BOUNDARIES.md`. This narrow M3-3 path was handled under the user's continuing authorization. No boundary file or other thread-owned source changed.

## TDD and focused verification

- RED: `test_social_resolve_duplicate_rejects_transaction_command_mismatch_without_write` failed because the corrupted durable transaction still returned `committed_success`.
- GREEN: Python `3.12.2`, SQLite `3.43.1`, and `app.__file__` resolved under the A worktree.
- Focused command: `F:\codex-temp\thread-a-python312\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\m3-3-social-resolve-20261128-01\pytest-temp backend/tests/test_p5_social_knowledge.py`.
- Result: `22 passed, 2 warnings`, exit 0. Raw focused output: `F:\paralls-verification\thread-a\m3-3-social-resolve-20261128-01\focused.log`.
- Unit selection: `selected=1 problems=0 improvements=0`.
- Frozen selections: ownership 24, modifier 12, equipment 87, inventory 56, shared-replay 990. All returned zero problems and improvements, 1,169 selected nodes total.

## Full backend regression

- Command: `F:\codex-temp\thread-a-python312\Scripts\python.exe -B -m pytest -v -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\m3-3-social-resolve-20261128-01\pytest-full-temp backend/tests`.
- Environment: Python `3.12.2`; SQLite `3.43.1`; `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`; `app.__file__` resolved under the A worktree. TEMP, TMP, pytest basetemp, and raw output were on F:.
- Result: `10,817 passed, 5 failed, 2 skipped, 2 xfailed, 227 warnings in 1668.79s`, exit 1. This is not a full-suite pass.
- The five failed nodes were rerun at parent `f34dd3a627b8739c84763329e173b4893497a92c` in a temporary F-drive worktree. All five failed there too: missing optional `tokenizers`, Task45 Godot parser errors, `test_cold_ready` missing `resource_bounds`, recovery measurement missing `GIT_CONFIG_VALUE_0`, and Task8 Godot parser errors. This is a five-node parent comparison, not a parent full-suite run.
- Full raw log: `F:\paralls-verification\thread-a\m3-3-social-resolve-20261128-01\full-backend.log`. Parent comparison log: `F:\paralls-verification\thread-a\m3-3-social-resolve-20261128-01\parent-five-failures.log`.

## Status and limits

- U1-U10: not applicable to this shared R2 increment; no Owner/domain migration is claimed.
- U11: covered by the registered one-node selection.
- M3-3 remains in progress. This closes only `SocialFactAuthority.resolve` duplicate validation. Other direct/custom replay paths still require owner and contract review.
- No push, merge, or `integration` change was made. The existing untracked `Godot/` directory was preserved.
