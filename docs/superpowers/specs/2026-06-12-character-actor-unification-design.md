# Character Actor Unification Umbrella Design

## Problem

The current Phase 0 demo already proves that the same visible knight presentation stack can serve both the player role and agent-driven characters, but the repository still risks drifting back into separate runtime species:

- player body
- NPC body
- agent body
- presentation body

That drift would break the intended project direction where every dramatic character is an embodied actor and only the command source changes.

## Goal

Freeze one umbrella design for Character Actor unification, then split the detailed decisions into two narrower specs:

1. runtime boundary and cross-layer contract rules
2. player control, camera, motor, and locomotion rules

This umbrella spec exists to define the shared intent, boundary summary, migration posture, and cross-spec acceptance criteria.

## Umbrella Decision

Human control changes the command source, not the actor substrate.

All embodied characters in the Phase 0.5 direction are treated as `CharacterActor` instances:

- human-controlled
- agent-controlled
- scripted-test
- future conservative autonomy

The actor remains the local embodiment host. The brain-side source of commands may differ, but the body, interaction, presentation, and authority path must converge.

## Spec Split

This umbrella design is intentionally narrow. Detailed rules are delegated to two child specs.

### Spec A

`docs/superpowers/specs/2026-06-12-character-actor-runtime-boundary-design.md`

Owns:

- `CharacterAgent -> CharacterActor -> ESM` boundary
- `CharacterGoalCommand` and `CharacterIntentFrame` contract split
- interaction, focus, reacquisition, and feedback lifecycle
- autonomy modes and shared command surface
- Phase 0.5 presentation compatibility and `GreyboxHumanoidVisual` deprecation

### Spec B

`docs/superpowers/specs/2026-06-12-character-actor-control-and-locomotion-design.md`

Owns:

- locked player control model
- camera/body coupling
- `CharacterMotor` ownership rules
- locomotion, root-motion, and animation synchronization
- action locks and control-side runtime verification

## Boundary Summary

The umbrella runtime picture is:

```text
CharacterAgent
-> actor-facing goal command
-> CharacterActor
-> local intent execution
-> motor / interaction / presentation
-> ESM for world-changing settlement
```

Responsibility summary:

- `CharacterAgent`: private perception, subjective interpretation, intent choice, and high-level execution output
- `CharacterActor`: local embodiment, movement, facing, focus, interaction feasibility, presentation, and local fact emission
- `ESM`: authoritative world/object/environment settlement

## Migration Principles

The migration must preserve the current Phase 0 demo loop while removing architectural ambiguity.

Required migration posture:

- prefer one shared actor substrate over separate player/NPC body stacks
- keep `KnightRoleSkin` as the required Phase 0.5 role presentation asset
- remove `GreyboxHumanoidVisual` from the Character Actor migration path
- preserve backend authority for world-changing actions
- keep Godot as the local embodiment and presentation host, not the world-truth authority and not the character brain
- keep future Phase 1 compatibility without requiring full Phase 1 implementation in this repo

## Shared Input And Facing Invariant

The shared actor substrate must also preserve one locomotion and facing convention across the player shell, actor bridge, and motor.

Required invariant:

```text
project-local forward intent = `move_local.y > 0`
world forward execution = `-actor.global_basis.z`
bridge-facing helper = `-Vector3.FORWARD.rotated(Vector3.UP, yaw)`
```

This means:

- `W` normalizes to positive local forward intent
- `S` normalizes to negative local backward intent
- player-facing look targets and locomotion resolution must use the same forward-axis convention as the motor path

The repository briefly regressed into a split convention where raw Godot input and bridge-facing resolution disagreed about forward sign. Character Actor unification explicitly rejects that drift because it reintroduces separate body semantics for player control versus actor execution.

## Non-Goals

This umbrella design does not require:

- full Phase 1 cognition rollout
- full FACS/SACS/Binder runtime
- long-horizon autonomous planning
- replacing `ESM` authority
- a full production control polish pass in the same document as runtime boundary design

## Acceptance Criteria

The umbrella design is accepted when implementation can prove all of the following:

1. `CharacterActor` is defined as the shared embodiment substrate for human-controlled, agent-controlled, and scripted characters.
2. `CharacterAgent`, `CharacterActor`, and `ESM` have clear, non-overlapping responsibility boundaries.
3. The actor-facing cross-boundary command contract is frozen as `CharacterGoalCommand`, while `CharacterIntentFrame` is frozen as Godot-local execution input; they are not treated as the same layer.
4. Human and agent paths enter the same actor command surface and unified execution chain instead of maintaining separate low-level body paths.
5. Shared actor execution preserves one forward-direction convention end-to-end:
   - `W` resolves to `move_local.y = +1`
   - local forward resolves to `-basis.z`
   - bridge-facing and motor-facing rules do not disagree about forward sign
6. World-changing actions remain backend/`ESM` authoritative even when movement, search, facing, or presentation execute locally in Godot.
7. `KnightRoleSkin` is the required Phase 0.5 role presentation asset, and `GreyboxHumanoidVisual` is removed from the Character Actor migration path.
8. The runtime-boundary child spec and the control-and-locomotion child spec together support continued Phase 0 verification without forcing full Phase 1 runtime completion.

## Relationship To Existing Specs

This umbrella design complements:

- `docs/superpowers/specs/2026-06-11-character-agent-minimal-runtime-slice-design.md`
- `docs/superpowers/specs/2026-06-12-character-actor-runtime-boundary-design.md`
- `docs/superpowers/specs/2026-06-12-character-actor-control-and-locomotion-design.md`

The 2026-06-11 spec defines the backend-side minimal `CharacterAgent L1 -> L4` slice.

This umbrella design and its child specs define how that backend-side slice meets a shared Godot-side embodiment substrate without splitting player and agent bodies into separate species.
