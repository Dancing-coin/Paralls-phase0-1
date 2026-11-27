# M3-3 completed-handshake social history replay validation

## Scope

- Code commit: `f431c8969025ebc0b409183c5ff769251fc19246`.
- `SocialFactAuthority.record_completed_handshake_shared_experience` now validates the durable transaction and committed event references with `replay_duplicate` before returning an exact retry receipt.
- The existing two actor-private event-type contract, canonical key, source session reference, causation, correlation, and `handshake_shared_experience_idempotency_key_reused` rejection remain. No event schema, payload, or event meaning changed.
- `backend/app/gameplay/p5/social_knowledge.py` is not explicitly assigned in `BOUNDARIES.md`. A handled this narrow M3-3 path under the user's continuing full authorization. No boundary file or other thread-owned source changed.

## TDD and focused verification

- RED: the new transaction-command mismatch test failed because a corrupted durable transaction still returned `committed_success`.
- GREEN: Python `3.12.2`, SQLite `3.43.1`, and `app.__file__` resolved under the A worktree.
- Focused command: `F:\codex-temp\thread-a-python312\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\m3-3-social-handshake-20261128-02\pytest-temp backend/tests/test_inf4ai_p5_actor_private_expression.py backend/tests/test_inf4ao_public_milling_social_ack.py backend/tests/test_p5_social_knowledge.py`.
- Result: `39 passed, 6 warnings`, exit 0. Raw output: `F:\paralls-verification\thread-a\m3-3-social-handshake-20261128-02\focused.log`.
- Unit selection: `selected=1 problems=0 improvements=0`. Output: `F:\paralls-verification\thread-a\m3-3-social-handshake-20261128-06\selection\`.

## Full backend regression

- Command: `F:\codex-temp\thread-a-python312\Scripts\python.exe -B -m pytest -v -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\m3-3-social-handshake-20261128-04\pytest-temp backend/tests`.
- Environment: Python `3.12.2`; SQLite `3.43.1`; `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`; `app.__file__` resolved under this A worktree. TEMP, TMP, bytecode cache, pytest basetemp, and raw output were on F:.
- Result: `10,802 passed, 19 failed, 2 skipped, 2 xfailed, 227 warnings in 1705.43s`, exit 1. Raw output: `F:\paralls-verification\thread-a\m3-3-social-handshake-20261128-04\full-backend.log`. This is not a full-suite pass.
- Fourteen nested gameplay-evidence nodes failed under the long pytest basetemp and passed under short F-drive TEMP: `14 passed, 2 warnings` in `13.14s`. Raw output: `F:\paralls-verification\thread-a\m3-3-social-handshake-20261128-05\short-path-rerun.log`.
- Five other failed nodes remain: missing optional `tokenizers`; Task45 Godot headless probe; `test_cold_ready`; recovery measurement; Task8 Godot headless registry probe. These were not rerun against a parent in this unit. The prior run's `test_original_owner_outbox_recovers_after_hard_kill[before_done]` passed in this run.

## Status and limits

- U1-U10: not applicable to this shared R2 increment; no Owner/domain migration is claimed.
- U11: covered by the registered one-node selection.
- M3-3 remains in progress. This closes only the completed-handshake retry path. Other direct/custom replay paths remain to inventory and verify.
- No push, merge, or `integration` change was made. Existing untracked `Godot/` content was preserved.
