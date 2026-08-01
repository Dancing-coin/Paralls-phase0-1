# State-Group Registry And Runtime Facade Plan

Status: `minimum-core-implemented; remaining-phases-planned`

## Dependencies

`gameplay-foundation-contracts-events-and-harness-plan.md`

## Work

1. [x] Implement immutable `StateGroupDefinition`, duplicate/unknown
   dependency validation, deterministic dependency resolution, conflict
   rejection, and a read-only composed façade snapshot. The current core is
   in-process only; it intentionally excludes versioned activation and
   explanation APIs.
2. Implement actor/world/patch eligibility, initialization, materialization,
   dormant/disable behavior, and rebuild registration from committed events.
3. Extend the existing read-only `CharacterGameRuntimeState` with committed
   lifecycle revisions and consumer-filtered authority, mind, Godot, and debug
   views.
4. Add group lifecycle tests for missing dependency, cyclic dependency,
   conflict, enable idempotency, dormant read-only state, and rematerialization.

## Exit Criteria

The facade has no write methods and cannot replace current mind runtime state.
An enabled group is dynamically assembled only after its definition and
dependencies validate, and replay rebuilds the same facade snapshot.

## Evidence

`gameplay-state-groups` plus its predecessor event/contract profiles pass.
