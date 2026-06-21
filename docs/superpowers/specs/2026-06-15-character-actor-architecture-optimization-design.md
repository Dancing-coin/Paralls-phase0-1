# Character Actor Architecture Optimization Design

## Problem

The current `CharacterActor` direction is correct, but the repository still mixes three different concerns in ways that make future work harder than it should be:

- control source semantics
- locomotion truth ownership
- presentation and post-animation embodiment corrections

The demo now proves that:

- one shared actor substrate can serve the player role and agent-driven roles
- physics-owned locomotion can coexist with root-motion-aware presentation
- post-animation combat correction is required for reliable visible results

What is still missing is one consolidated optimization spec that explains:

- what the six-layer character stack formally is
- which layers are stable architectural layers vs transitional implementation layers
- how human, agent, and program control fit the same actor substrate
- how model swaps, skeleton rebinding, equipment, actions, and future asset-library integration should work

Without this consolidation, implementation risks drifting into:

- player-only runtime paths
- presentation-owned movement truth
- model-specific hacks with no reusable binding contract
- undocumented asset assumptions that slow future character work

## Goal

Define the optimized `CharacterActor` architecture for the Phase 0 demo repository so that:

- the character stack is structured, modular, and explainable
- the same actor substrate supports:
  - traveler / human player
  - agent player
  - NPC
- control-source switching does not require replacing the actor body or presentation substrate
- locomotion can remain physics-owned today while preserving a clean future path toward motor-owned root motion and hybrid execution
- model, skeleton, equipment, action, and future expression asset integration all have explicit contracts
- documentation is clear enough that future developers can:
  - understand the stack quickly
  - change character models
  - change skeleton binding
  - add equipment
  - modify or add actions
  - integrate future asset-library lookups

## Scope

This spec covers:

- the formal six-layer `CharacterActor` architecture
- product identity vs runtime control-mode terminology
- control-source switching rules
- locomotion execution mode definitions
- actor-runtime boundaries inside the Godot implementation
- presentation and post-animation correction responsibilities
- asset binding and action asset integration contracts
- documentation surface for future development
- migration targets for:
  - a demo-safe near-term architecture
  - a Phase1-facing mid-term architecture

This spec does not cover:

- full Phase 1 cognition rollout
- complete `FACS/SACS/Binder` implementation
- production asset library backend implementation
- final content authoring pipelines for every possible role asset

## Relationship To Existing Specs

This spec becomes the new active optimization truth above the current `2026-06-12` `CharacterActor` specs:

- `docs/superpowers/specs/2026-06-12-character-actor-unification-design.md`
- `docs/superpowers/specs/2026-06-12-character-actor-runtime-boundary-design.md`
- `docs/superpowers/specs/2026-06-12-character-actor-control-and-locomotion-design.md`

Those specs remain valuable as:

- migration history
- narrower design references
- preserved implementation rationale

They should not be deleted, but this spec becomes the primary active truth for architecture optimization and future actor-stack cleanup.

## Core Decisions

### 1. Human Control Changes The Command Source, Not The Actor Substrate

All dramatic roles remain `CharacterActor` instances.

Control-source switching must not create a separate runtime species for:

- player body
- NPC body
- agent body

The same actor substrate must support all role-control variants.

### 2. Physics Owns World Displacement Truth In The Near-Term Architecture

Baseline locomotion world truth remains motor-owned:

```text
CharacterMotor owns:
- velocity
- gravity
- collision
- move_and_slide
- normal world displacement
```

Presentation must follow locomotion truth rather than replace it.

### 3. Root Motion Remains A Valid Future Execution Mode, But Must Be Motor-Owned

Future root-motion support is explicitly allowed, but the repository must not regress into:

```text
Animation layer directly owns world displacement truth
```

The allowed future direction is:

```text
KnightRoleSkin / asset layer
-> RootMotionRequest
-> CharacterMotor(root_motion | hybrid mode)
-> CharacterMotionState
```

### 4. Presentation Is Split Into Composition And Post-Animation Modification

The optimized architecture distinguishes:

- presentation composition
- post-animation embodiment correction

This is not accidental implementation detail; it is a formal architectural boundary.

### 5. Asset Generalization Must Be Explicit

The actor stack must no longer rely on undocumented asset assumptions hidden inside model-specific code.

Explicit contracts are required for:

- role model assets
- skeleton binding
- equipment binding
- action descriptors
- future expression descriptors

## Product Identity vs Runtime Control Terminology

These are different concepts and must remain separate.

### Product Identity

```text
traveler
agent_player
npc
```

These terms answer:

- who this role is in product semantics
- how players and roles are described externally

### Runtime ControlMode

```text
ControlMode
- human_controlled
- agent_controlled
- program_controlled
```

These terms answer:

- who currently drives the role body
- which adapter supplies the next local intent

`program_controlled` is intentionally broader than test-only automation. It covers:

- autotest
- harness control
- replay
- tool-driven control
- scripted staging
- future cutscene/tutorial/runtime-owned programmatic takeover

### Switching Rule

Any role may switch control mode while remaining the same actor substrate.

Examples:

- `traveler` role switches from `human_controlled` to `agent_controlled` on disconnect
- `npc` may be taken over by `agent_controlled` or `human_controlled`
- automated harness or replay uses `program_controlled`

What must stay stable across a switch:

- same actor body
- same visible role
- same role state
- same equipment / skeleton / binding profile
- same authority path

### ControlMode Transition Semantics

Allowed transitions:

```text
human_controlled <-> agent_controlled
human_controlled <-> program_controlled
agent_controlled <-> program_controlled
```

Common triggers:

- disconnect takeover
- explicit handoff
- programmatic automation attach/detach
- replay enter/exit
- debug attach/detach

The transition rule is:

```text
switch controller source
preserve actor substrate
preserve actor identity
preserve visible role continuity
```

## The Formal Six-Layer Character Stack

The optimized architecture formally names the stack as:

```text
L1 Controller Input Layer
L2 Control Adaptation Layer
L3 Actor Runtime Layer
L4 Motor / Locomotion Execution Layer
L5 Presentation Composition Layer
L6 Post-Animation Embodiment Modification Layer
```

### L1 Controller Input Layer

Purpose:

- receive raw control-source input

Allowed sources:

- traveler mouse / keyboard
- agent high-level goal command
- program-driven test / replay / harness input

Forbidden responsibilities:

- direct actor-state mutation
- direct world displacement
- final pose ownership

### L2 Control Adaptation Layer

Purpose:

- adapt diverse control sources into one shared local actor execution shape

Primary output:

```text
CharacterIntentFrame
```

This layer is where control-source differences are normalized.

### L3 Actor Runtime Layer

Purpose:

- own the shared `CharacterActor` runtime shell
- maintain role-level local execution state
- coordinate:
  - command status
  - focus
  - interaction feasibility
  - action state
  - presentation inputs

This is the unified actor substrate.

### L4 Motor / Locomotion Execution Layer

Purpose:

- own locomotion truth
- produce `CharacterMotionState`

Near-term:

- `physics`

Mid-term allowed:

- `root_motion`
- `hybrid`

### L5 Presentation Composition Layer

Purpose:

- choose base animation, motion profile, role skin config, combat timer, and presentation parameters

This layer composes how the role should be presented.

### L6 Post-Animation Embodiment Modification Layer

Purpose:

- apply final local body/equipment corrections after animation evaluation

Examples:

- combat overlay
- equipment pose offsets
- future expression modifier overlays
- future binder-ready embodiment fixups

This layer exists because some visible embodiment changes must happen after the base animation system has evaluated.

## Recommended Shared Runtime Contracts

### CharacterIntentFrame

```text
CharacterIntentFrame {
  actor_id
  control_mode
  move_local
  desired_facing_yaw
  look_pitch
  gait
  action
  target_ref?
  verb?
  causation_id?
  correlation_id?
}
```

### CharacterMotionState

```text
CharacterMotionState {
  actor_id
  position
  velocity_world
  facing_yaw
  camera_pitch?
  move_local_actual
  gait_actual
  grounded
  collision_flags
  focus_target_id?
}
```

### CharacterPresentationInput

```text
CharacterPresentationInput {
  actor_id
  motion_state
  focus_state
  action_state
  equipment_state
  expression_hint
  physiology_hint
  speech_state
}
```

`CharacterPresentationInput` is the formal L3 -> L5 presentation boundary.

New presentation work should enter through this contract rather than by allowing more side-channel node-specific state reads from arbitrary scripts.

### RootMotionRequest

```text
RootMotionRequest {
  local_delta
  facing_delta
  clip_name
  grounded_required
  source
}
```

### ModifierInput

```text
ModifierInput {
  sword_overlay_progress
  shield_overlay_progress
  equipment_pose_offsets
  upper_body_override
  future_expression_overlay?
}
```

## LocomotionExecutionMode

This concept must be explicit.

```text
LocomotionExecutionMode
- physics
- root_motion
- hybrid
```

### physics

- `CharacterMotor` owns displacement
- animation follows motion state

### root_motion

- `CharacterMotor` consumes root motion requests
- animation-originated displacement is validated and applied by motor

### hybrid

- physics remains the baseline truth
- root motion influences cadence, short authored motion, and local correction

## Asset Generalization Model

Future character flexibility depends on explicit binding contracts.

### CharacterAssetBindingProfile

```text
CharacterAssetBindingProfile {
  role_asset_id
  skeleton_profile_id
  equipment_slots
  supported_action_tags
  supported_expression_tags
  locomotion_binding_mode
}
```

### SkeletonBindingProfile

```text
SkeletonBindingProfile {
  canonical_bone_roles
  candidate_bone_names
  fallback_bindings
  post_animation_modifier_support
}
```

### EquipmentBindingProfile

```text
EquipmentBindingProfile {
  slots
  slot_anchor_paths
  offset_defaults
  variant_visibility_rules
}
```

### AssetCompatibilityLevel

New assets should eventually declare the minimum compatibility level they satisfy:

```text
AssetCompatibilityLevel
- locomotion_only
- locomotion_plus_equipment
- full_action_ready
- binder_ready
```

This exists so future role-model integration is tracked as a compatibility state rather than a vague “works/doesn't work” judgment.

### ActionAssetDescriptor

```text
ActionAssetDescriptor {
  action_tag
  animation_clip_ref?
  root_motion_profile?
  modifier_profile?
  equipment_override?
  required_slots
}
```

### ExpressionAssetDescriptor

```text
ExpressionAssetDescriptor {
  expression_tag
  modifier_profile?
  face_binding_profile?
  physiology_overrides?
}
```

## Future Asset-Library Integration Surface

This repository does not need to implement the final library now, but it must freeze the integration seam.

Future role runtime should be able to resolve:

```text
fact / state / command context
-> action / expression / equipment asset lookup
-> CharacterPresentationInput + ModifierInput
```

This means current code should evolve toward:

- explicit tags
- explicit binding profiles
- explicit modifier profiles

not hardcoded model-specific action assumptions.

## Current Demo-Safe Target Architecture

The near-term architecture may keep these major implementation pieces:

- `PlayerShell.gd`
- `Phase0PlayerBridge.gd`
- `CharacterMotor.gd`
- `CharacterReplica.gd`
- `KnightRoleSkin.gd`
- `KnightCombatModifier.gd`

But their responsibilities should be clarified as:

- `PlayerShell`: raw player input, camera, shell movement context
- `Phase0PlayerBridge`: control adaptation for the player path
- `CharacterMotor`: locomotion truth
- `CharacterReplica`: actor runtime shell
- `KnightRoleSkin`: presentation composition
- `KnightCombatModifier`: animation-post final combat/equipment correction

## Phase1-Facing Mid-Term Target

The mid-term architecture should move toward:

```text
CharacterActor
-> ControllerPort
-> CharacterMotor
-> CharacterRuntimeState
-> CharacterPresentationInput
-> KnightRoleSkin
-> Binder-ready modifier stack
```

Likely future additions:

- `HumanControllerAdapter`
- `AgentControllerAdapter`
- `ProgramControllerAdapter`
- `CharacterAssetBindingProfile`
- `EquipmentModifier`
- `ExpressionModifier`

## Required Documentation Surface

This optimization effort requires durable docs for both engineering and asset work.

The repository should gain:

- `docs/character/character-actor-architecture.md`
- `docs/character/character-control-chain.md`
- `docs/character/character-asset-integration.md`
- `docs/character/character-action-asset-interface.md`
- `docs/character/character-actor-migration-status.md`
- `docs/character/character-debug-and-verification.md`

## Migration Principles

- keep the demo runnable
- preserve one actor substrate
- do not reintroduce player-only body species
- keep locomotion truth separate from presentation truth
- freeze contracts before broad rewrites
- prefer additive adapters and clear boundaries before destructive removal

## Temporary Diagnostics And Cleanup Rule

The repository may temporarily add debug instrumentation while converging the architecture, including:

- input trace logs
- combat trace logs
- nameplate debug feedback
- debug overlay sections

But all such diagnostics must be classified as one of:

```text
- temporary diagnostics to remove after migration
- debug facilities to keep behind an explicit debug flag
```

No temporary debug signal should silently become a permanent default runtime behavior without being explicitly promoted to a documented debug mode.

## Acceptance Criteria

This spec is accepted when implementation can prove:

1. The character stack is documented as an explicit six-layer architecture.
2. Product identity and runtime control mode are clearly separated.
3. `traveler`, `agent_player`, and `npc` all map onto one shared actor substrate.
4. `human_controlled`, `agent_controlled`, and `program_controlled` are supported as explicit control modes.
5. `CharacterMotor` remains the only normal owner of locomotion truth in the near-term architecture.
6. Root-motion support is frozen as a valid future motor-owned execution mode.
7. Presentation composition and post-animation embodiment modification are explicitly separated.
8. Asset binding and action/equipment integration have explicit contracts.
9. Documentation exists for architecture, control chain, and asset integration.
10. Phase 0 demo verification remains green while the architecture is optimized.

## Completion Status

Status as of `2026-06-15`: first near-term optimization pass completed and verified; second near-term cleanup pass completed and verified.

The repository now proves:

- the six-layer architecture is documented in the active truth spec and character docs
- product identity and runtime control mode are separated in both docs and code vocabulary
- shared runtime terminology is frozen in code for:
  - `human_controlled`
  - `agent_controlled`
  - `program_controlled`
  - `physics`
  - `root_motion`
  - `hybrid`
- `PlayerShell` owns raw input capture and forwards shell events to the controller adapter seam
- `Phase0PlayerBridge` no longer runs a parallel raw-input polling loop for the same concerns
- `Phase0PlayerCommandRelay` owns shell command dispatch that used to live in `Phase0PlayerBridge`
- `CharacterReplica` remains the shared actor runtime shell rather than being bypassed by scene code
- visible runtime feedback moved out of `CharacterReplica` into `CharacterRuntimeFeedback`
- `CharacterPresentationInput` is preserved at the actor-to-skin boundary while near-term flat fallback fields remain available
- `KnightRoleSkin` and `KnightCombatModifier` now expose a clearer composition -> modifier handoff
- model / equipment / action asset entry contracts are frozen in code as explicit schema helpers
- asset lookup remains gated behind explicit readiness criteria rather than adding a full runtime library
- future root-motion / hybrid work has an explicit motor-owned displacement guard
- strict `Phase 0` verification remains green after the convergence pass

Verified acceptance evidence for this pass includes:

- `python -m pytest -v`
- `python scripts/verification/harness.py --profile docs`
- `python scripts/verification/harness.py --profile godot-project`
- `python scripts/verification/harness.py --profile phase0`

This satisfies the current near-term demo-safe convergence target of the implementation plan.

## Remaining Transitional Areas

The architecture is cleaner, but this pass intentionally stops short of a full Phase1 rollout.

The main transitional areas that remain are:

- `Phase0PlayerBridge.gd` still contains some demo sync/helper and autotest-oriented responsibilities in addition to pure control adaptation
- `CharacterReplica.gd` still owns the actor runtime shell and remains a transition point for future `CharacterRuntimeState` extraction
- `CharacterPresentationInput` is frozen as a contract, but the runtime still assembles it through near-term dictionary bridging rather than a fuller typed pipeline
- the new asset binding / equipment / action descriptor files are contract-level entry points only and are not yet used as a full runtime asset lookup system; actual lookup is gated behind explicit readiness criteria
- near-term locomotion remains `physics`-first with coordinated root-motion consumption rather than a full mid-term `LocomotionExecutionMode` execution stack

These are acceptable for the current repository goal because they preserve demo stability while preventing further architectural drift.

## Next Steps

After the near-term cleanup closeout, do not re-plan the completed near-term work:

- `Phase0PlayerBridge` shell command dispatch has been extracted
- `CharacterReplica` visible runtime feedback has been split out
- `CharacterPresentationInput` is preserved at the actor-to-skin boundary
- `ControllerPort` has been documented as a mid-term boundary and intentionally not implemented in the near-term cleanup
- asset lookup has a documented readiness gate and remains contract-only until multiple role skins require real lookup
- future root-motion / hybrid work has a motor-owned displacement guard

Remaining follow-up should start from the Phase1-facing mid-term target:

1. Implement explicit `ControllerPort` adapters only when the next runtime slice needs human / agent / program control ports.
2. Replace near-term dictionary bridging with a stronger typed presentation pipeline when runtime consumers are ready.
3. Build actual asset lookup only after multiple role skins require binding profiles and fallback behavior.
4. Expand `LocomotionExecutionMode` into real root-motion or hybrid execution only while preserving `CharacterMotor` as displacement owner.
5. Keep Phase 0 demo verification green before and after each mid-term slice.
