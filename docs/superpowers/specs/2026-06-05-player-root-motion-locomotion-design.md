# Player Root Motion Locomotion Design

## Context

This design covers the player-controlled knight locomotion stack in the Phase 0 demo.

Current observed problems:

- player root motion movement is too slow
- movement direction is reversed relative to `WASD`
- locomotion clips do not read as believable walking
- current player action coverage is too small for keyboard-first control

The existing runtime split remains valid:

- `Player` is the hidden collision, camera, gravity, and jump shell
- `CharacterC` is the visible in-world knight shell
- grounded horizontal movement should be driven by corrected root motion

This design stays within the current repository and current knight animation asset set.
It does not require Blender re-authoring or a full AnimationTree rewrite.

## Goals

- make `WASD` movement direction correct and intuitive
- make root motion speed and step amplitude believable
- support keyboard-fast control for:
  - amble
  - walk
  - brisk walk
  - run
  - two-foot jump
  - single-leg jump
  - crouch
  - crouch locomotion
  - crouch exit back to standing
- show current locomotion state in UI
- preserve the existing hidden-shell plus visible-shell architecture

## Non-Goals

- no new animation asset authoring in Blender
- no full locomotion blend-tree rebuild
- no IK pass or foot-locking system in this iteration
- no backend protocol redesign
- no scene-wide character architecture rewrite

## Input Contract

Player keyboard controls will be:

- `WASD`: move
- `Shift + WASD`: run
- `Z`: cycle gait mode inside standing locomotion
- `C`: toggle crouch and stand
- `WASD + Space`: two-foot jump
- `Shift + WASD + Space`: single-leg jump

Gait cycling on `Z` will be:

- `amble -> walk -> brisk_walk -> amble`

`run` is not part of the `Z` cycle. It is entered only while `Shift` is held during standing locomotion.

While crouched:

- `WASD` remains available
- movement uses a low-speed crouch locomotion mode
- `Shift` does not promote to run
- `C` exits crouch and returns to standing posture

## Runtime State Model

The player locomotion state will be represented as three orthogonal values:

- `stance`
  - `stand`
  - `crouch`
- `gait`
  - `amble`
  - `walk`
  - `brisk_walk`
  - `run`
- `jump_type`
  - `none`
  - `two_foot`
  - `single_leg`

This state model is the source of truth for:

- clip selection
- root motion calibration
- UI state display
- movement tuning

## Architecture

### 1. Input Layer

The input layer will remain on the hidden `Player` shell and `Phase0PlayerBridge`.

Responsibilities:

- read keyboard intent
- compute planar move direction in camera space
- determine locomotion modifiers:
  - gait cycle selection
  - run override
  - crouch toggle
  - jump type
- produce normalized locomotion intent, not direct grounded translation

### 2. Locomotion Intent Layer

Add an explicit locomotion intent model between raw input and motion execution.

Responsibilities:

- resolve `stance`, `gait`, `jump_type`
- resolve `move_direction`
- keep transitions stable across frames
- prevent crouch and run conflict
- determine which jump variant is active

This layer should avoid binding game logic directly to clip names.

### 3. Animation Root Motion Layer

`KnightRoleSkin` remains responsible for:

- clip selection
- root motion track discovery
- root motion sampling per active clip
- clip-level calibration metadata

This layer must be upgraded so that root motion is not consumed as raw untrusted delta.
Instead it must produce calibrated locomotion deltas.

### 4. Player Shell Drive Layer

`Phase0PlayerBridge` remains the handoff point back into `Player`.

Responsibilities:

- consume corrected root motion delta from `CharacterC`
- apply grounded horizontal translation back to the hidden `Player` shell
- preserve gravity, collision, and camera ownership on `Player`
- sync visible pose from `Player` back to `CharacterC`

## Root Motion Correction Strategy

This is the highest-priority change area.

### A. Forward Axis Normalization

The current player direction mismatch indicates that the effective animation forward axis and gameplay forward axis are not aligned.

Each locomotion clip will expose a small calibration profile:

- `forward_axis_sign`
- `distance_scale`
- `speed_scale`

The system must normalize root motion so that:

- pressing `W` moves along gameplay forward
- `S` moves backward
- `A/D` map naturally to lateral locomotion facing behavior
- diagonal movement remains consistent

The bridge and replica layers should consume only normalized root motion, not infer sign ad hoc.

### B. Step Amplitude Calibration

Current movement is too slow because root motion magnitude is under-driving the shell.

For each locomotion clip:

- extract the raw locomotion delta
- measure the projected forward distance
- apply a calibrated `distance_scale`

Base clips:

- `walk_guard`
- `run_charge`

Derived gait bands:

- `amble`: lower step amplitude and lower playback speed than `walk`
- `walk`: baseline calibration from `walk_guard`
- `brisk_walk`: increased amplitude and playback speed from `walk_guard`
- `run`: baseline or slightly increased amplitude from `run_charge`

### C. Speed Normalization

Movement speed must match visual cadence.

Therefore:

- `AnimationPlayer.speed_scale`
- root motion distance scaling
- gameplay target speed expectations

must be tuned together.

Target outcome:

- no slow-motion run
- no leg-cycling without body translation
- no body translation outrunning leg cadence

### D. Transition Tuning

To prevent awkward locomotion:

- starting movement uses a short acceleration window
- stopping movement uses a short deceleration window
- gait switches from `Z` use short eased transitions
- facing updates respond quickly to move direction

## Animation Mapping

The design intentionally reuses current knight clips.

### Standing

- `idle_stand` -> `idle_guard`
- `amble` -> `walk_guard` with low speed and low distance scaling
- `walk` -> `walk_guard` with baseline calibration
- `brisk_walk` -> `walk_guard` with raised speed and distance scaling
- `run` -> `run_charge`

### Jump

- `two_foot_jump` -> `jump_command`
- `single_leg_jump` -> `jump_command` with lighter motion tuning:
  - faster launch timing
  - lower heaviness feel
  - shorter commitment window

If a clean dedicated airborne follow clip is unavailable, airborne hold can remain a wrapped form of the existing jump or fall response until a better asset exists.

### Crouch

No dedicated crouch clip is assumed for this iteration.

Crouch will be constructed from:

- stance toggle state
- posture offset
- collision height adjustment
- reduced-speed locomotion wrapper

Animation execution states:

- `crouch_enter`
- `crouch_idle`
- `crouch_walk`
- `crouch_exit`

These may initially reuse standing animation with strong posture offsets and low-speed calibration.

The purpose of the first iteration is correctness and responsiveness, not final performance capture fidelity.

## State Machine Design

Use two conceptual layers.

### Intent State Layer

- `stand_idle`
- `stand_move`
- `crouch_idle`
- `crouch_move`
- `jump_two_foot`
- `jump_single_leg`
- `airborne`

### Animation Execution Layer

- `idle_stand`
- `locomotion_stand`
- `idle_crouch`
- `locomotion_crouch`
- `jump_two_foot_start`
- `jump_single_leg_start`
- `airborne_hold`
- `crouch_enter`
- `crouch_exit`

This separation prevents keybind logic from hardcoding animation names and keeps locomotion tuning local to the animation execution layer.

## UI Design

Use the existing on-screen debug display first.

Minimum displayed fields:

- `Stance: Stand/Crouch`
- `Gait: Amble/Walk/Brisk/Run`
- `Jump: None/TwoFoot/SingleLeg`
- `Clip: current clip name`
- `Root Motion: active/inactive`

The purpose is not presentation polish.
The purpose is immediate runtime observability while tuning keyboard control.

## Implementation Sequence

1. Fix root motion forward direction
2. Calibrate `walk_guard` and `run_charge` distance and speed
3. Introduce standing gait bands:
   - `amble`
   - `walk`
   - `brisk_walk`
   - `run`
4. Bind `Z` gait cycling
5. Bind crouch toggle and crouch movement
6. Bind two-foot jump
7. Bind single-leg jump
8. Add UI locomotion state display
9. Run keyboard-flow verification and Phase 0 regression verification

## Verification Plan

The iteration passes only when all of these are true:

- `WASD` direction matches visible movement direction
- `Shift + WASD` produces an obviously faster run
- `Z` cycles visibly distinct `amble / walk / brisk_walk`
- `C` cleanly toggles crouch and allows low-speed crouch movement
- `WASD + Space` and `Shift + WASD + Space` feel observably different
- UI correctly reports the active locomotion state
- the player shell remains collision-correct
- Phase 0 strict verification does not regress

## Risks

- root track forward direction may differ between clips
- `walk_guard` may not visually support all three standing gait bands equally well
- crouch without dedicated clip may look mechanically correct but visually provisional
- single-leg jump may require additional timing shaping to feel clearly distinct

## Recommendation

Implement the root motion correction and standing gait normalization first.

Do not start from crouch or jump.
The current blocking issue is the grounded locomotion foundation:

- wrong direction
- too little travel
- poor cadence-to-translation match

Once grounded locomotion is corrected, the rest of the keyboard control stack can be layered predictably on top.
