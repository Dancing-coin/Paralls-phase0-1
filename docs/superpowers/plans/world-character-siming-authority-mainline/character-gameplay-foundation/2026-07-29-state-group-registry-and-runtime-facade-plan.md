# State-Group Registry And Runtime Facade Plan

Status: `drafted-for-spec-review`

## Dependencies

`gameplay-foundation-contracts-events-and-harness-plan.md`

## Work

1. Implement immutable `StateGroupDefinition`, registry validation, dependency
   DAG resolution, conflict rejection, versioned activation, and explanation
   APIs.
2. Implement actor/world/patch eligibility, initialization, materialization,
   dormant/disable behavior, and rebuild registration from committed events.
3. Implement read-only `CharacterGameRuntimeState` with per-group revision
   vector and consumer-filtered authority, mind, Godot, and debug views.
4. Add group lifecycle tests for missing dependency, cyclic dependency,
   conflict, enable idempotency, dormant read-only state, and rematerialization.

## Exit Criteria

The facade has no write methods and cannot replace current mind runtime state.
An enabled group is dynamically assembled only after its definition and
dependencies validate, and replay rebuilds the same facade snapshot.

## Evidence

`gameplay-state-groups` plus its predecessor event/contract profiles pass.
