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
2. [~] Implement actor/world/patch eligibility, initialization, materialization,
   dormant/disable behavior, and rebuild registration from committed events.
   The current restricted slice accepts an explicit trusted assembly context,
   validates eligibility/dependency safety, appends lifecycle events through the
   existing atomic Gameplay batch writer, then replays them into a read-only
   membership projection. A versioned declarative policy catalog now compiles
   actor archetype/world revision/patch revision inputs into that trusted
   context and fails closed for unavailable required dependencies. It does not
   yet persist/load the policy catalog from world or patch activation, rebuild
   projections across process lifetime, or expose consumer-specific views.
   The Patch lifecycle additionally uses a manifest-declared, event-sourced
   `identity_rebind` for same-definition source-revision continuity during an
   explicit actor stateful upgrade/rollback. The first bounded resource
   maximum-reduction Patch migration now additionally records an event-sourced
   state-group definition/source transition only after a typed resource fact is
   accepted into the same batch. It cannot transform generic group data or
   revoke persistent effects; other migration paths remain planned.
3. [~] Extend the existing read-only `CharacterGameRuntimeState` with committed
   lifecycle revisions and consumer-filtered authority, mind, Godot, and debug
   views. The current view projector creates immutable policy-filtered payload
   views: non-authority consumers can only receive allowlisted existing fields,
   debug requires a policy-listed principal, and a requested group without a
   policy fails closed. The backend-only sync service now builds checksummed
   full snapshots and exact-base deltas, rejects unsupported capabilities, and
   validates the reconstructed target checksum. It does not add view transport,
   consumer capability negotiation, client prediction, Godot mirror delivery,
   or persistent privacy-policy loading.
   `Phase3StateComposer` now composes only lifecycle-enabled Phase 3 group
   payloads from independently owned read projections; it has no command or
   event-store write path.
   `Phase3CheckpointReplay` now proves in-memory domain checkpoint-plus-tail
   equivalence for lifecycle/resource/body/tag projections before façade
   composition; persistence, migration, and delivery remain planned.
4. [x] Add focused group lifecycle, view, and backend-only snapshot/delta tests
   for missing dependency, cyclic dependency,
   conflict, enable idempotency, dormant read-only state, and rematerialization.

## Exit Criteria

The facade has no write methods and cannot replace current mind runtime state.
An enabled group is dynamically assembled only after its definition and
dependencies validate, and replay rebuilds the same facade snapshot.

## Evidence

`gameplay-state-groups` currently proves registry validation, explicit-context
authority lifecycle batches, lifecycle-event read projection, read-only façade
composition, filtered views, and backend-only exact-base snapshot/delta
reconstruction. Complete lifecycle and consumer-delivery work must extend that
profile, then pass it together with predecessor event/contract/replay profiles.
