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
