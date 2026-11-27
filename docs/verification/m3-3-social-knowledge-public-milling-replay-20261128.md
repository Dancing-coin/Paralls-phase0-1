# M3-3 SocialFactAuthority public-milling retry validation

## Scope

- Code commit: `93aa11274730e09830171ea59746f3abb623349b`.
- `SocialFactAuthority.record_public_milling_notice_social_acknowledgment` now validates the durable transaction and committed event references with `replay_duplicate` before returning an exact retry receipt.
- The caller's canonical idempotency key, semantic source/causation/correlation checks, actor-private event type contract, and `idempotency_key_reused` rejection remain in place. No event type, schema version, payload field, or event meaning changed.
- `backend/app/gameplay/p5/social_knowledge.py` is not explicitly assigned in `BOUNDARIES.md`. A handled this narrow M3-3 retry path under the user's continuing full authorization. No boundary file or other thread-owned source was changed.

## TDD and focused verification

- RED: `test_inf4ao_duplicate_rejects_transaction_command_mismatch_without_writing` failed because the corrupted transaction still produced `committed_success` instead of `rejected_zero_write`.
- GREEN/current tip: Python `3.12.2`, SQLite `3.43.1`, and `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- Focused command: `F:\codex-temp\thread-a-python312\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\m3-3-social-knowledge-20261128-02\pytest-temp backend/tests/test_inf4ao_public_milling_social_ack.py backend/tests/test_p5_social_knowledge.py`.
- Result: `30 passed, 2 warnings`, exit 0. Raw output: `F:\paralls-verification\thread-a\m3-3-social-knowledge-20261128-02\focused.log`.
- Unit selection: `selected=1 problems=0 improvements=0`. Output: `F:\paralls-verification\thread-a\m3-3-social-knowledge-20261128-06\selection\`.
- Frozen selections: ownership 24, modifier 12, equipment 87, inventory 56, and shared-replay 990. All returned zero problems and improvements, 1,169 nodes total. Raw output: `F:\paralls-verification\thread-a\m3-3-social-knowledge-20261128-03\`.
- The registered-selection sweep enumerated 48 files before the new selection was added; those 48 all returned zero problems and improvements. The new one-node selection was then run separately and also returned zero differences. Thus 49 registered selections are covered by these two runs, with 48+1 selected nodes counted per manifest, not deduplicated.

## Full backend regression

- Command: `F:\codex-temp\thread-a-python312\Scripts\python.exe -B -m pytest -v -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\m3-3-social-knowledge-20261128-04\pytest-temp backend/tests`.
- Environment: Python `3.12.2`; SQLite `3.43.1`; `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`; `app.__file__` resolved under this A worktree. TEMP, TMP, bytecode cache, pytest basetemp, and raw output were under F:.
- Result: `10,800 passed, 20 failed, 2 skipped, 2 xfailed, 227 warnings in 1754.25s`, exit 1. Raw output: `F:\paralls-verification\thread-a\m3-3-social-knowledge-20261128-04\full-backend.log`. This is not a full-suite pass.
- Fourteen `test_nested_gameplay_evidence` cases failed under the long pytest temp root and passed with short F-drive TEMP: `14 passed, 2 warnings` in `16.32s`. Raw output: `F:\paralls-verification\thread-a\m3-3-social-knowledge-20261128-05\short-path-rerun.log`. The full-run exit and failures remain recorded as observed.
- Six other failed nodes remain: missing optional `tokenizers`; Task45 Godot headless probe; `test_cold_ready` resource bounds; process outbox recovery `[before_done]`; recovery measurement; Task8 Godot headless registry probe. Their failure attribution was not rerun against a parent in this unit.

## Status and limits

- U1-U10: not applicable to this shared replay-validation increment; no Owner/domain migration is claimed.
- U11: covered by the registered one-node selection.
- M3-3 remains in progress. This closes one direct duplicate-retry path only. Other direct/custom replay paths remain to inventory and verify.
- No push, merge, or `integration` change was made. Existing untracked `Godot/` content was preserved.
