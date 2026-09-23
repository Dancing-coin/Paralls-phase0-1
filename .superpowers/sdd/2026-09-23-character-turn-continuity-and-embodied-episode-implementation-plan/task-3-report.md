# Task 3 report: pending character-turn recovery

## Result

Implemented durable complete continuity checkpoints and deterministic pending-turn reconciliation. An unresolved execution is never resent; a missing or invalid authority receipt returns `recovery_required` and the runtime blocks new execution for that actor while retaining the session audit record when the durable session timeline is present.

## TDD evidence

- RED: `test_restart_marks_unreceipted_execution_recovery_required` first failed because `begin_test_turn_awaiting_settlement` did not exist.
- GREEN: the focused recovery test passed after adding the recovery service, complete snapshot fields, runtime test seams, and canonical stage serialization handling.

## Files changed

- `backend/app/character_agent/services/character_turn_recovery.py`
- `backend/app/character_agent/storage/graph_continuity_store.py`
- `backend/app/character_agent/runtime/runtime_loop.py`
- `backend/tests/test_character_turn_recovery.py`

## Verification

- Focused recovery/continuity/persistence tests: **13 passed**.
- Full `python -m pytest -v`: **5648 passed, 9 failed**. The failures include existing documentation/profile/static fixture expectations and unrelated runtime assertions; the two directly exposed persistence regressions were corrected and rerun green. Remaining failures are baseline/out-of-scope and require the parent branch's broader fixture changes.

## Self-review and concerns

- `write_current_state()` remains a hot read model; `flush_continuity_snapshot()` forces a complete checkpoint with schema version, timeline checkpoint index, graph source ref, stable digest, active turns, pending execution, policy state, and last committed turn id.
- Recovery validates canonical context identity, stage order/identity, graph/session timeline continuity, and exact receipt correlation. It does not auto-resend authority work.
- Receipt-commit reconciliation returns `already_committed` as an audit-safe idempotent result; a future coordinator settlement path can append the remaining canonical stages.
- A graph-only recovery checkpoint does not append a local event when the session file is absent, avoiding invalid local event indexes beside the graph timeline; the actor is still blocked and the graph evidence is preserved.

## Fix round 1

Review fixes tightened malformed-state handling: snapshot schema/digest/source/checkpoint validation, conflicting timeline duplicate rejection, all unresolved awaiting-settlement turn inspection, exact expected-revision matching, durable recovery lifecycle transitions/policy blocking, receipt-driven original-turn stage advancement, committed-turn persistence, and forced checkpointing whenever pending execution exists. Runtime startup reapplies recovery blocking for continuity actors with persisted state.

Focused verification command:

`python -m pytest backend/tests/test_character_turn_recovery.py backend/tests/test_character_graph_continuity_store.py backend/tests/test_character_agent_runtime_persistence_wiring.py backend/tests/test_character_agent_seed_continuity.py::test_continuity_persistence_does_not_copy_full_timeline_or_scan_other_receipts -q`

Result: **13 passed** (4 expected FastAPI deprecation warnings).

## Fix round 2

Applied scoped re-review fixes for malformed active-turn/snapshot state, all-turn reconciliation, strict event IDs, forced execution checkpoints, canonical non-ASCII digest serialization, production expected-revision pins, startup block restoration, and committed-turn ID retention.

Verification:

`python -m pytest backend/tests/test_character_turn_recovery.py backend/tests/test_character_graph_continuity_store.py backend/tests/test_character_agent_runtime_persistence_wiring.py -q`

Result: **12 passed** (4 expected FastAPI deprecation warnings).
