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
- `Phase0PlayerBridge` no longer runs parallel raw-input polling loops; it adapts forwarded shell events and actor sync state
- `MainDemoController` no longer keeps a direct `CharacterReplica` runtime reference for player-facing forward-vector reads
- `KnightRoleSkin` now builds modifier input and hands it to `KnightCombatModifier`
- asset generalization entry contracts are frozen in code:
  - `CharacterAssetBindingProfile`
  - `CharacterEquipmentBindingProfile`
  - `CharacterActionAssetDescriptor`

## Still Transitional

- `Phase0PlayerBridge.gd` still carries some demo orchestration helpers and debug-oriented utility methods in addition to pure adaptation
- `CharacterReplica.gd` still carries some presentation-adjacent feedback helpers
- the new asset contract files are schema-only and are not yet consumed by runtime asset resolution
- `CharacterPresentationInput` is frozen as a contract, but the current payload is still assembled as a near-term dictionary bridge rather than a typed resource pipeline
- `CharacterLocomotionExecutionMode` is frozen as vocabulary, but near-term runtime remains `physics`-first with selective root-motion consumption routed through actor/motor coordination
- some debug instrumentation remains embedded in runtime scripts

## Intended Near-Term Cleanup

1. narrow raw input to `PlayerShell`
2. narrow adaptation to bridge/controller adapter layer
3. narrow actor-runtime ownership inside `CharacterReplica`
4. keep final pose/equipment correction in `SkeletonModifier3D`
5. freeze model/skeleton/equipment/action contracts

Status:
- 1 is implemented
- 2 is partially implemented and still has demo-helper residue
- 3 is partially implemented
- 4 is implemented in the current near-term architecture
- 5 is implemented as contract freeze, not full runtime adoption

## Intended Mid-Term Direction

- explicit `ControllerPort`
- explicit `CharacterPresentationInput`
- explicit asset binding profiles
- binder-ready modifier stack
- motor-owned root-motion or hybrid execution mode

## Debugging Note

Current debug additions exist to prove actor/control/presentation boundaries under active migration.

They should eventually become:

- explicit debug modes
- explicit harness toggles

rather than default runtime noise.
