# Character Base Player Unification Plan

Goal: replace the current `PlayerShell -> CharacterC` split with a single player-controlled `CharacterBase` entity while preserving the current Phase 0 demo loop.

Scope:
- add a reusable `CharacterBase` scene rooted at `CharacterBody3D`
- migrate the player-controlled role from `Player + CharacterC` to one `PlayerCharacter`
- keep `CharacterA` and `CharacterB` on their current scene for now
- preserve the current knight skin, `AnimationTree`, and root-motion locomotion path

Constraints:
- no new dependencies
- keep `MainDemo.tscn` runnable throughout the migration
- keep current backend protocol and focus/interaction loop intact

Execution steps:
1. Add `CharacterBase.tscn` and `CharacterBase.gd` by combining the collision/camera shell from `PlayerShell` with the visual/role-asset structure from `CharacterReplica`.
2. Move the player control and camera methods onto `CharacterBase` so `MainDemoController` can talk to one node.
3. Retarget `Phase0PlayerBridge` so it drives its parent `CharacterBase` directly instead of looking up `CharacterC`.
4. Replace `Player` + `CharacterC` in `MainDemo.tscn` with a single `PlayerCharacter` instance.
5. Update focused tests and run a Godot scenario to verify movement, focus, and interaction.

Verification:
- `python -m pytest scripts/verification/tests/test_character_base_unification.py -q`
- Godot runtime scenario on `res://scenes/phase0/MainDemo.tscn`

## Confirmed Design Decisions From Context Handoff

Human control changes the command source, not the actor substrate. A player-controlled actor still uses the same character actor base as agent-controlled replicas, including private perception, subjective interpretation, automatic expression, physiology, and conservative continuity systems. The migration must not recreate a separate "player-only" runtime that bypasses those layers.

The shared Character Actor command surface remains:

- `look_at`
- `go_to`
- `approach`
- `observe`
- `interact`
- `speak`

Autonomy mode changes command permissions, not the actor substrate. Human mode may allow all six commands; agent mode may allow all six through policy; away/conservative mode should restrict risky movement, interaction, and speech on key objects.

## Presentation Staging

Phase 0.5 keeps the implementation direct and demo-safe:

```text
CharacterPresentation -> KnightRoleSkin direct animation / motor sync
```

Phase 1 remains the target architecture:

```text
CharacterAgent L4
-> FACS/SACS Planner
-> Embodiment Binder
-> Canonical Rig
-> Asset Adapter
-> Godot Runtime Mixer
-> KnightRoleSkin / final asset
```

`CharacterBase` unification must not require full FACS/SACS implementation before the shared motor/controller substrate is stable. New presentation APIs should still be named and shaped so they can later become Runtime Mixer inputs.

## Phase 0.5 Presentation Input Shape

The first implementation should be compatible with this conceptual input:

```text
CharacterPresentationInput {
  actor_id
  motion_state
  focus_state
  action_state
  expression_hint
  physiology_hint
  speech_state
}
```

`KnightRoleSkin` maps these fields directly for now:

- `motion_state` maps movement direction, speed, gait, grounded state, facing yaw, and velocity to locomotion clips/profiles.
- `focus_state` maps target and attention strength to orientation and focus highlight.
- `action_state` maps `idle`, `observe`, `interact`, `speak`, `inspect`, `jump`, and `fall` to animation choices.
- `expression_hint` and `physiology_hint` are placeholders for future expression/posture channels, not full FACS/SACS.
- `speech_state` maps speaking/silent state, target actor, and dialogue reference to speak animation plus voice hook.

## Root Motion Boundary

Phase 0.5:

```text
Physics motor owns world displacement.
KnightRoleSkin follows motor state.
Root motion can be sampled for diagnostics or optional visual speed correction.
```

Phase 1:

```text
Runtime Mixer owns animation blending.
Foot locking, stride warping, IK, and binder constraints keep visual and motor aligned.
```

## Non-Goals And Deprecated Paths

- Phase 0.5 does not implement full FACS/SACS.
- Phase 0.5 does not require production facial animation.
- Phase 0.5 does not require every asset to have a full canonical rig profile.
- Phase 0.5 does not move cognition into Godot.
- `GreyboxHumanoidVisual` is deprecated for Character Actor migration.
- `KnightRoleSkin` is the required Phase 0.5 presentation asset.
- Fallback should be an explicit missing-asset placeholder, not a second humanoid runtime.
