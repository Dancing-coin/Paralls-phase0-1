# Character Actor Architecture

This document explains the optimized `CharacterActor` stack used by the Phase 0 demo repository.

## Why This Exists

The repository now supports:

- traveler / human-controlled roles
- agent-controlled roles
- program-controlled test or replay roles

All of them must share one actor substrate. This doc explains the stable structure that makes that possible.

## Product Identity vs Runtime Control

### Product Identity

These are gameplay-facing terms:

- `traveler`
- `agent_player`
- `npc`

### Runtime ControlMode

These are runtime-facing terms:

- `human_controlled`
- `agent_controlled`
- `program_controlled`

Identity and control mode are intentionally separate. A role may keep its product identity while switching control mode.

## The Formal Six Layers

```text
L1 Controller Input Layer
L2 Control Adaptation Layer
L3 Actor Runtime Layer
L4 Motor / Locomotion Execution Layer
L5 Presentation Composition Layer
L6 Post-Animation Embodiment Modification Layer
```

## Current File Mapping

### L1 Controller Input Layer

- `scripts/player/PlayerShell.gd`
- backend-side `CharacterGoalCommand`
- program-driven harness/autotest/replay input sources

Responsibilities:

- capture raw human input
- receive backend high-level commands
- receive programmatic control commands

### L2 Control Adaptation Layer

- `scripts/player/Phase0PlayerBridge.gd`
- `scripts/character/HumanControllerAdapter.gd`
- `scripts/character/AgentControllerAdapter.gd`
- `scripts/character/ProgramControllerAdapter.gd`
- `scripts/character/CharacterControllerPort.gd`

Responsibilities:

- normalize source-specific input into `CharacterIntentFrame`
- translate traveler combat clicks into actor action requests
- keep player shell and visible actor in sync through thin actor-facing helper surfaces

### L3 Actor Runtime Layer

- `scripts/character/CharacterReplica.gd`

Responsibilities:

- role/action runtime state
- focus and interaction runtime state
- command-to-role-state adaptation
- presentation input aggregation
- user-visible short feedback like the nameplate overlays

### L4 Motor / Locomotion Execution Layer

- `scripts/character/CharacterMotor.gd`
- current live player path: `scenes/phase0/CharacterReplica.tscn`

Responsibilities:

- velocity ownership
- gravity
- move_and_slide
- collision and grounded state
- normalized local motion-state publication used by the shared actor presentation path

### L5 Presentation Composition Layer

- `scripts/character/KnightRoleSkin.gd`

Responsibilities:

- role model configuration
- animation clip selection
- motion profile selection
- locomotion refinement setup
- combat timer state
- parameter handoff into the post-animation modifier

### L6 Post-Animation Embodiment Modification Layer

- `scripts/character/KnightCombatModifier.gd`

Responsibilities:

- apply combat overlay after animation evaluation
- modify visible arm/hand/spine pose after base animation
- directly adjust `sword_in_hand` / `shield_in_hand` transforms when needed

## Near-Term Execution Truth

Current near-term truth:

```text
CharacterMotor owns world displacement.
KnightRoleSkin follows motor state.
KnightCombatModifier applies final combat embodiment after animation.
```

This is the stable Phase 0 demo-safe posture.

## Future LocomotionExecutionMode

The architecture is prepared for:

```text
LocomotionExecutionMode
- physics
- root_motion
- hybrid
```

Near-term default:

- `physics`

Future root-motion support must remain motor-owned rather than presentation-owned.

## Root-Motion Ownership Guard

CharacterMotor remains the only normal owner of baseline displacement.

`KnightRoleSkin` may expose sampled root-motion deltas, and `CharacterReplica` may coordinate those deltas with actor runtime state, but presentation nodes must not directly move the world body.

Future root-motion and hybrid work must be motor-owned. A complete mid-term `root_motion` or `hybrid` execution mode must preserve this path:

```text
presentation root-motion sample
-> CharacterReplica coordination
-> CharacterMotor-owned displacement
-> normalized local motion-state publication
```

## Shared Actor Principle

The key architectural principle is:

```text
Human control changes the command source, not the actor substrate.
```

That means:

- no player-only body species
- no NPC-only body species
- one shared actor body path

## Asset Generalization Direction

Future model and action flexibility depends on explicit contracts for:

- skeleton binding
- equipment slots
- action asset descriptors
- future expression asset descriptors

This repository does not need to implement the full asset library yet, but the actor stack must evolve toward explicit binding profiles and asset descriptors rather than hidden model-specific assumptions.
