# Character Asset Integration

This document explains how to swap role models, update skeleton bindings, and attach equipment without breaking the shared `CharacterActor` substrate.

## Integration Goal

A new role asset should plug into the same actor stack without creating a new runtime species.

That means:

- no separate player-only body implementation
- no separate NPC-only body implementation
- no hidden model-specific logic path that bypasses the actor stack

## Required Integration Layers

Any new role asset should be considered across four concerns:

1. role model asset
2. skeleton binding
3. equipment binding
4. action support

## 1. Role Model Asset

Current role presentation uses:

- `KnightRoleSkin.tscn`
- imported role scene under `KnightScene`

When replacing the role model:

- keep the outer `KnightRoleSkin` scene shell
- replace the imported role content under the presentation subtree
- preserve the actor-facing scene contract

Do not:

- replace `CharacterReplica`
- collapse the actor runtime into a model-only scene

## 2. Skeleton Binding

Every new model needs a skeleton binding review.

Today the repository resolves bones by candidate name sets. Future work should migrate this toward explicit binding profiles.

For a new skeleton, verify at minimum:

- pelvis / hips
- spine lower
- spine upper
- neck
- head
- left upper arm / forearm / hand
- right upper arm / forearm / hand
- left thigh / calf / foot
- right thigh / calf / foot

Current examples include names like:

- `mixamorig_*`
- `DEF-*`
- `Bip001 *`

Adding a new model should never rely on “guess and hope” bone names. Document the new names or binding profile explicitly.

## 3. Equipment Binding

The current knight stack already proves that equipment may need its own direct post-animation correction.

Equipment integration should define:

- slot name
- slot anchor path
- default local offset
- optional modifier behavior

Current examples:

- `sword_in_hand`
- `shield_in_hand`

Future profile shape should converge toward:

```text
CharacterEquipmentBindingProfile {
  slots
  slot_anchor_paths
  offset_defaults
  visibility_rules
}
```

## 4. Action Support

A model is not ready just because it loads visually.

Each model must declare:

- which locomotion set it supports
- which action tags it supports
- which equipment slots are required for a given action
- whether the action needs:
  - base animation
  - post-animation modifier
  - equipment transform override

Examples of action tags:

- `sword_swing`
- `shield_block`
- `speak`
- `inspect`
- `jump`

## Minimal Validation Checklist

When integrating a new model, verify:

1. The actor still uses the same `CharacterBase -> CharacterReplica -> presentation` stack.
2. The model is visible in the shared role skin shell.
3. Required bones resolve to valid indices.
4. Equipment anchors resolve to valid nodes.
5. Locomotion animation still follows `CharacterMotionState`.
6. Combat or short action overlays remain visible after animation evaluation.
7. Head/nameplate/focus visuals still behave correctly.

## Near-Term Repository Rule

Near-term, the repository may keep binding logic partly in code while the profile abstraction is introduced. But every new model integration should leave behind:

- updated candidate bone names or an explicit binding profile
- updated equipment slot mapping
- updated docs

## Long-Term Direction

Future model swaps should move toward:

```text
CharacterAssetBindingProfile
-> SkeletonBindingProfile
-> EquipmentBindingProfile
-> ActionAssetDescriptor support list
```

That is the intended path for generalized actor asset integration.
