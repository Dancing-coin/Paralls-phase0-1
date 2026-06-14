# Character Actor Control And Locomotion Design

## Problem

The Character Actor unification effort needs one explicit control and locomotion model for the player-facing body path. Without that, runtime-boundary agreement is not enough:

- camera behavior drifts
- body-facing rules drift
- root-motion and physics ownership drift
- player and agent motion semantics stop matching

This spec isolates those control and locomotion decisions from the higher-level runtime boundary spec.

## Goal

Define the Phase 0.5 control, camera, motor, and locomotion rules for `CharacterActor` so that:

- player control is consistent and explainable
- motor ownership is unambiguous
- animation follows physics rather than replacing it
- human and agent locomotion can share the same bottom-half execution path

## Scope

This spec covers:

- player control model
- camera/body coupling
- `CharacterMotor` ownership
- `CharacterMotionState`
- locomotion target directions
- animation synchronization with motor state
- action locks and interrupts

This spec does not cover:

- `CharacterAgent / CharacterActor / ESM` responsibility boundaries
- interaction authority semantics beyond control-side execution consequences
- full Phase 1 runtime mixer implementation

## Control Model

Phase 0.5 uses `Locked FPS/TPS`, also called camera-locked body orientation.

Rules:

```text
mouse X -> CharacterActor body yaw + camera yaw
mouse Y -> camera pitch only
W/S -> move along actor/camera forward/back
A/D -> move along actor/camera left/right
```

Invariant:

```text
camera forward yaw == body forward yaw == aim forward yaw
```

`A` and `D` do not rotate the body independently. They produce lateral movement relative to the current actor yaw.

This chooses a cleaner locked model over the current incomplete hybrid behavior.

## Input Semantics

The control-side input semantics are:

- mouse X: facing turn
- mouse Y: pitch only
- `W`: forward
- `S`: backward / backpedal
- `A`: strafe left
- `D`: strafe right
- `Shift`: faster gait modifier
- `C`: crouch toggle or hold, depending on implementation details
- jump input: jump request into motor/action state

These inputs do not directly drive animation clips. They drive local movement intent which the motor resolves and presentation consumes indirectly.

Normalization rule:

```text
project-local `move_local` uses positive Y for forward intent
```

That means the player input layer must normalize raw Godot action-vector output before handing it to the shared actor path:

```text
W -> move_local.y = +1
S -> move_local.y = -1
```

This rule exists because Godot `Input.get_vector(left, right, up, down)` returns negative Y for the `up` action, while the shared Character Actor locomotion contract uses positive Y as forward intent.

## Movement Vector

Movement uses actor-local forward/right axes:

```text
forward = -actor.global_basis.z
right = actor.global_basis.x
move_world = forward * move_local.y + right * move_local.x
```

This movement rule applies equally to human- and agent-originated local execution after intent has been normalized.

Bridge-facing and look-target resolution must use the same forward sign as the motor path:

```text
forward_from_yaw(yaw) = -Vector3.FORWARD.rotated(Vector3.UP, yaw)
```

The bridge layer must not resolve look/facing using `+Vector3.FORWARD` while the motor resolves locomotion using `-basis.z`, because that reintroduces a player-only body convention mismatch.

## Camera Rig Rules

Only the local human player enables an active `CameraRig`.

Rules:

- `CameraRig` follows the actor anchor
- camera yaw comes from actor body yaw
- camera pitch is local to the rig and clamped
- spring arm or equivalent camera collision handles obstruction
- mouse left/right is not an orbit camera; it turns actor and camera together
- mouse up/down changes pitch only

Agent-controlled actors may still have facing/perception pose data, but they do not own the local player camera.

## CharacterMotor Ownership

`CharacterMotor` is the only layer allowed to:

- change `CharacterBody3D.velocity`
- call `move_and_slide()`
- perform normal movement-related position updates

Responsibilities:

- apply facing/yaw from intent
- compute local/world movement from `move_local`
- apply acceleration and deceleration
- apply gravity and jump
- handle slopes and collision
- run `move_and_slide()`
- publish movement state to presentation

Disallowed outside motor:

- `global_position = ...` for normal movement
- direct controller-specific velocity writes
- direct agent position writes
- direct animation-driven teleport for baseline locomotion

Exception:

- explicit debug/autotest teleport may exist, but it must be named as such and kept out of normal runtime paths

## Per-Frame Order

Per-frame order is:

```text
1. read CharacterIntentFrame
2. resolve facing
3. update actor yaw
4. compute desired local/world velocity
5. apply acceleration/deceleration/gravity
6. move_and_slide()
7. publish CharacterMotionState
8. presentation consumes CharacterMotionState
9. interaction sensor updates FocusState
10. fact emitters emit relevant L1 facts
```

This order ensures that presentation follows motor state rather than raw input guesses.

## CharacterMotionState

`CharacterMotionState` is the Godot-local movement result for the current frame, not backend world truth:

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

Presentation reads `CharacterMotionState`, not raw input. That keeps human and agent animation paths unified once both are in the shared actor substrate.

## Locomotion Animation Target

Locked camera-body control requires local-space locomotion, not forward-only animation.

Target movement directions:

```text
(0, 1)    forward
(0, -1)   backward / backpedal
(-1, 0)   strafe left
(1, 0)    strafe right
(-1, 1)   forward-left
(1, 1)    forward-right
(-1, -1)  backward-left
(1, -1)   backward-right
```

Final target:

- 2D locomotion blend using `move_x` and `move_y`
- strafe-left and strafe-right animation support
- backpedal animation support
- diagonal blend support
- turn-in-place or facing adjustment only when later design genuinely needs it, not as a substitute for locked yaw

## Locomotion Synchronization

Movement must remain physically credible and visually aligned.

Rules:

- `CharacterMotor` owns world displacement
- root motion does not directly own actor world truth for baseline locomotion
- animation matches motor velocity through blend parameters, gait speed, and playback speed
- optional root-motion delta comparison may be used for foot-sliding diagnostics
- short authored root-motion actions are allowed only for special moves after motor/collision validation

Minimum matching requirements:

- forward movement uses forward walk/run animation speed matched to motor speed
- `A/D` uses strafe-left/right animation matched to lateral speed
- `S` uses backpedal animation matched to backward speed
- diagonals use diagonal blend instead of pure forward fallback once assets exist
- stop/deceleration aligns with stop/idle transition

Minimum control-side verification requirements for this contract:

- static regression coverage locks the input normalization rule and bridge forward-axis rule
- runtime verification proves simulated forward input moves the player shell and visible `CharacterReplica` along world `-Z` when yaw is zero

## Presentation Inputs

Phase 0.5 presentation may consume a lower-level frame derived from motion and action state:

```text
PresentationInput {
  move_x
  move_y
  speed
  gait
  grounded
  action_overlay
  facing_yaw_delta
}
```

`KnightRoleSkin` should consume presentation parameters and should not know whether the controller source is human, agent, conservative autonomy, or test harness.

## Root Motion Boundary

Phase 0.5:

```text
Physics motor owns world displacement.
KnightRoleSkin follows motor state.
Root motion can be sampled for diagnostics or optional visual speed correction.
```

Phase 1 target:

```text
Runtime Mixer owns animation blending.
Foot locking, stride warping, IK, and binder constraints keep visual and motor aligned.
```

This spec freezes the Phase 0.5 rule that physics remains authoritative for locomotion displacement.

## Action Locks And Interrupts

Simple control-side action lock rules:

- locomotion is always allowed unless an action explicitly locks movement
- `look_at` and `observe` do not lock movement
- `speak` soft-locks facing toward the target and does not fully lock movement unless configured
- `interact` hard-locks facing and may use a short movement/action window
- `go_to` and `approach` can be interrupted by `interact`, `speak`, or a higher-priority command

Priority:

```text
interact > speak > observe/look_at > approach/go_to > idle
```

These rules are shared execution semantics, not controller-specific hacks.

## Transitional Compromise

Phase 0.5 may temporarily use forward locomotion with root-motion projection if full strafe/backpedal assets are unavailable.

That is an implementation compromise, not the final control model.

The frozen target remains:

- locked camera/body yaw
- motor-owned locomotion
- strafe/backpedal-capable animation support

## Acceptance Criteria

This spec is accepted when implementation can prove:

1. The player control model is explicitly locked camera/body orientation rather than an ambiguous hybrid.
2. Mouse X controls actor/camera yaw together, while mouse Y controls camera pitch only.
3. `W/S/A/D` movement is actor-local forward/back/strafe movement rather than controller-specific special cases.
4. `CharacterMotor` is the only normal runtime layer that owns velocity updates and `move_and_slide()`.
5. Presentation follows `CharacterMotionState` rather than directly reading raw input as the source of truth.
6. Root motion does not replace physics ownership for baseline locomotion displacement.
7. The locomotion target direction set includes strafe and backpedal support as the intended Phase 0.5 direction.
8. Action lock and interrupt rules are explicit and shared across command sources.

## Verification Plan For Implementation

Implementation should include:

- tests for control-to-intent normalization on the human path
- tests for `CharacterMotor` ownership boundaries
- tests proving `CharacterMotionState` drives presentation rather than raw input
- tests or static checks for locked yaw/pitch coupling rules
- tests for action lock and interrupt priority behavior
- Godot-side verification that the main scene still opens and runs
- `python scripts/verification/harness.py --profile godot-project`
- `python scripts/verification/harness.py --profile phase0`

## Relationship To Other Specs

This spec complements:

- `docs/superpowers/specs/2026-06-12-character-actor-unification-design.md`
- `docs/superpowers/specs/2026-06-12-character-actor-runtime-boundary-design.md`

The umbrella spec explains why Character Actor unification exists.

The runtime-boundary spec explains who owns what.

This control-and-locomotion spec explains how the unified actor body is supposed to move and present motion in Phase 0.5.
