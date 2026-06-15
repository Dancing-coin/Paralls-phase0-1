# Character Actor Migration Status

This document tracks which parts of the optimized `CharacterActor` architecture are already aligned and which remain transitional.

## Active Architecture Truth

Current active optimization truth:

- `docs/superpowers/specs/2026-06-15-character-actor-architecture-optimization-design.md`

Historical/narrower references still preserved:

- `2026-06-12-character-actor-unification-design.md`
- `2026-06-12-character-actor-runtime-boundary-design.md`
- `2026-06-12-character-actor-control-and-locomotion-design.md`

## Aligned Now

- shared player actor root via `CharacterBase.tscn`
- `CharacterMotor` owns normal world displacement
- player path uses the same visible role stack as the shared actor presentation path
- `KnightCombatModifier` exists as post-animation correction
- shared control terminology is frozen in code:
  - `human_controlled`
  - `agent_controlled`
  - `program_controlled`
- shared locomotion execution terminology is frozen in code:
  - `physics`
  - `root_motion`
  - `hybrid`
- `CharacterPresentationInput` exists as an explicit shared presentation-boundary contract
- `PlayerShell` now owns raw input capture and forwards shell events to the adapter layer
- `Phase0PlayerBridge` no longer owns shell command dispatch; `Phase0PlayerCommandRelay` owns Phase 0 action-map command routing
- `Phase0PlayerBridge` no longer runs parallel raw-input polling loops; it exposes callable adapter methods and actor sync state
- `MainDemoController` no longer keeps a direct `CharacterReplica` runtime reference for player-facing forward-vector reads
- visible runtime feedback moved out of `CharacterReplica` into `CharacterRuntimeFeedback`
- `CharacterPresentationInput` is preserved at the actor-to-skin boundary while the near-term flat fallback remains available
- `KnightRoleSkin` now builds modifier input and hands it to `KnightCombatModifier`
- asset generalization entry contracts are frozen in code:
  - `CharacterAssetBindingProfile`
  - `CharacterEquipmentBindingProfile`
  - `CharacterActionAssetDescriptor`
- asset lookup remains gated behind explicit readiness criteria
- future root-motion / hybrid work has a motor-owned displacement guard

## Still Transitional

- `Phase0PlayerBridge.gd` still carries demo sync and autotest-oriented utility methods in addition to pure adaptation
- `CharacterReplica.gd` still owns the actor runtime shell and remains a transition point for future `CharacterRuntimeState` extraction
- the new asset contract files are schema-only and are not yet consumed by runtime asset resolution
- asset lookup remains contract-only in this near-term cleanup; do not add `CharacterAssetLibrary.gd` until multiple role skins require real lookup and fallback behavior
- `CharacterPresentationInput` is frozen as a contract, but the current payload is still assembled as a near-term dictionary bridge rather than a typed resource pipeline
- `CharacterLocomotionExecutionMode` is frozen as vocabulary, but near-term runtime remains `physics`-first with selective root-motion consumption routed through actor/motor coordination
- CharacterReplica direct root-motion displacement remains transitional; future root-motion and hybrid work must be motor-owned, and presentation must not become the owner of world displacement
- some debug instrumentation remains embedded in runtime scripts

## Intended Near-Term Cleanup

1. narrow raw input to `PlayerShell`
2. narrow adaptation to bridge/controller adapter layer
3. narrow actor-runtime ownership inside `CharacterReplica`
4. keep final pose/equipment correction in `SkeletonModifier3D`
5. freeze model/skeleton/equipment/action contracts

Status:
- 1 is implemented
- 2 is implemented for shell command dispatch and partially implemented for remaining demo sync helpers
- 3 is implemented for visible runtime feedback and partially implemented for future runtime-state extraction
- 4 is implemented in the current near-term architecture
- 5 is implemented as contract freeze, not full runtime adoption

Near-term cleanup closeout:

- `Phase0PlayerBridge` no longer owns shell command dispatch
- visible runtime feedback moved out of `CharacterReplica`
- `CharacterPresentationInput` is preserved at the actor-to-skin boundary
- `ControllerPort` remains a documented mid-term target, not a near-term implementation
- asset lookup remains gated behind explicit readiness criteria
- future root-motion / hybrid work remains motor-owned
- remaining work before Phase1-facing mid-term can begin

## Intended Mid-Term Direction

- explicit `ControllerPort`
- explicit `CharacterPresentationInput`
- explicit asset binding profiles
- binder-ready modifier stack
- motor-owned root-motion or hybrid execution mode

`ControllerPort` is intentionally not implemented in the near-term cleanup. It remains a mid-term target after the Phase 0 bridge and runtime shell are slimmer.

## Debugging Note

Current debug additions exist to prove actor/control/presentation boundaries under active migration.

They should eventually become:

- explicit debug modes
- explicit harness toggles

rather than default runtime noise.
