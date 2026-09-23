# Task 5 report — evidence-backed character behavior evaluation

## Status

Implemented and verified. The evaluator now accepts canonical `CharacterTurnContext`, returns typed `BehaviorEvaluation`, preserves the legacy mapping fields and derived `behavior_score`, and records typed unknown dimensions instead of midpoint scores. Runtime compatibility remains intact for legacy settlements and durable policy admission still belongs to `BehaviorPolicyStore`.

## TDD evidence

- RED: `test_evaluation_marks_unprovable_social_effect_unknown_not_neutral` initially failed with `TypeError: ... evaluate() got an unexpected keyword argument 'turn'`, proving the scalar/legacy evaluator could not express the canonical typed interface.
- GREEN: the new divergent-outcome test passes with `execution_quality_score == 1.0`, `social_consequence_score is None`, and a typed `social_consequence` unknown.

## Implementation

- Added `BehaviorEvaluation` with six optional dimensions, confidence, evidence refs, unknown dimensions/reasons, candidate policy, and compatibility dictionary access.
- Derived comprehension, goal progress, role consistency, execution quality, social consequence, and recovery quality deterministically from available evidence; missing evidence remains unknown.
- Updated runtime evaluation to reconstruct canonical turn context from persisted stage events while keeping legacy actor/timeline reads and policy lifecycle admission unchanged.
- Updated graph projection helpers to preserve typed evaluation payloads/unknowns and candidate source identity while keeping historical compact projection compatibility.

## Verification

`python -m pytest backend/tests/test_character_behavior_evaluation.py backend/tests/test_behavior_turn_recorder.py backend/tests/test_behavior_policy_lifecycle.py -q`

Result: **25 passed**, with four existing FastAPI lifespan deprecation warnings.

`git diff --check`: passed.

## Concerns

- Existing runtime canonical projection is written before settlement for the live stage chain; the new typed evaluation remains persisted in the session timeline and is available to completed projection paths. A separate revision-update protocol for already-written graph anchors is outside Task 5.
- No Godot/runtime visual verification was required for this backend-only task.

## Fix Round 1

Addressed the independent review findings:

- Candidate creation no longer uses `behavior_score` as a gate; scalar output is compatibility-only and Task 4 remains the evidence/lifecycle gate.
- Empty settlement metadata, empty goal keys, and absent role values remain unknown rather than becoming synthetic known/neutral scores. The all-unknown compatibility fallback is `0.0`, not midpoint `0.5`.
- Role/social/recovery evidence is scoped to the canonical turn/correlation, and scoped event IDs are included in evidence refs to prevent cross-turn leakage.
- Runtime no longer writes a partial graph anchor before settlement. The completed projection writes settlement, typed evaluation/unknowns, and policy in one idempotent graph record, avoiding the pre-settlement revision conflict.
- Added coverage for scalar-independent candidate creation, cross-turn evidence isolation, and graph evaluation unknown preservation.

Fix-round verification:

`python -m pytest backend/tests/test_character_behavior_evaluation.py backend/tests/test_behavior_turn_recorder.py backend/tests/test_behavior_policy_lifecycle.py -q`

Result: **27 passed**, with four existing FastAPI lifespan deprecation warnings. `git diff --check` passed.

### Fix-round replay closure

The follow-up replay coverage exposed a second idempotency detail: duplicate
settlement callbacks can receive a new session event ID for the same authority
`result_id`. Runtime settlement ingestion now treats that result ID as the
replay identity, and canonical graph projection uses it for the completed turn
idempotency key. This prevents a duplicate callback from creating a second
evaluation anchor or a graph idempotency conflict.

Verification after replay closure:

`python -m pytest backend/tests/test_character_behavior_evaluation.py backend/tests/test_behavior_turn_recorder.py backend/tests/test_behavior_policy_lifecycle.py -q`

Result: **28 passed**, with four existing FastAPI lifespan deprecation warnings.

## Fix Round 2

- Result-ID evidence refs now resolve only to the exact settlement event whose
  payload carries that result ID; unrelated event IDs cannot satisfy the
  evidence gate.
- Duplicate settlement callbacks compare the incoming payload against the
  persisted payload (excluding the derived settlement metadata). Exact replay
  remains a no-op; reuse with changed status, authority, turn, or other payload
  data raises `character_settlement_replay_conflict` and leaves the timeline
  unchanged.
- Added regressions for qualified result-ID evidence and conflicting duplicate
  settlement reuse. Missing `result_id` continues to use the persisted event ID
  as the stable fallback identity.

Verification:

`python -m pytest backend/tests/test_character_behavior_evaluation.py backend/tests/test_behavior_turn_recorder.py backend/tests/test_behavior_policy_lifecycle.py -q`

Result: **30 passed**, with four existing FastAPI lifespan deprecation warnings.
