# Task 7 report — L4 execution-contract convergence

## Scope

Implemented the single production-shaped `CharacterExecutionContract` and
threaded it through canonical runtime execution while retaining
`CharacterGoalCommand` only as compatibility metadata/input. No new transport,
store, authority, body-pose, VLA, or world-write path was added.

## Changes

- Added immutable/validated `CharacterExecutionContract` with canonical turn,
  actor/source/target identity, semantic intent/action, advisory realization
  hints, revision pins, idempotency, causation/correlation, privacy/authority
  scope, and expected observation.
- Added recursive rejection of transform/velocity/pose/animation/impulse/
  damage/status/inventory/world-write/VLA payload fields.
- Added `CharacterAgentL4Executor.build_execution_contract(...)` and kept
  skill/settlement realization metadata advisory.
- Added one-way `CharacterAgentL4Adapter.from_legacy_command(...)` with a
  turn-keyed duplicate/conflict guard and `LegacyExecutionTranslation` result.
- Canonical runtime execution records the contract in the existing execution
  request payload; legacy commands carry only turn/idempotency compatibility
  pins for existing observers.

## Verification

```text
python -m pytest backend/tests/test_character_execution_contract.py backend/tests/test_character_agent_l4_execution.py backend/tests/test_character_agent_goal_command_runtime.py -v
19 passed

python -m compileall -q backend/app/character_agent
passed

git diff --check
passed
```

## Notes

The working tree contains pre-existing user/other-thread changes. Only the
Task 7-owned files should be staged for the implementation commit.
