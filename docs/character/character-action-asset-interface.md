# Character Action Asset Interface

This document defines the future-facing interface between the shared `CharacterActor` runtime and an action / expression / equipment asset library.

## Why This Exists

The repository should not keep hardcoding every new action directly into model-specific scripts forever.

Future role behavior needs an interface where:

- the runtime asks for an action or expression by meaning/tag
- the asset layer resolves a compatible asset package
- the actor presentation stack consumes that package without changing the actor substrate

## Current Reality

Today, the repository still uses:

- direct action strings
- direct clip names
- direct timer-driven combat overlays
- direct equipment node paths

That is acceptable for the current demo, but it is not the long-term generalized interface.

## Required Future Asset Types

At minimum, the future actor stack should support:

1. action assets
2. expression assets
3. equipment-aware overlays

## CharacterActionAssetDescriptor

Suggested future contract:

```text
CharacterActionAssetDescriptor {
  action_tag
  animation_clip_ref?
  locomotion_compatibility
  root_motion_profile?
  modifier_profile?
  equipment_override?
  required_slots
  allowed_control_modes?
}
```

Examples of action tags:

- `sword_swing`
- `shield_block`
- `speak`
- `observe`
- `inspect`
- `jump`

## CharacterExpressionAssetDescriptor

Suggested future contract:

```text
CharacterExpressionAssetDescriptor {
  expression_tag
  face_binding_profile?
  modifier_profile?
  physiology_overrides?
  intensity_range?
}
```

Examples:

- `alert_micro`
- `focused_guard`
- `tense_breath`
- `soft_speak`

## Equipment Override Contract

Some actions cannot rely on body pose alone.

Future action descriptors may need:

```text
equipment_override {
  slot_name
  local_rotation_offset
  local_position_offset
  visibility_override?
}
```

This is especially relevant for:

- sword swings
- shield raises
- bow aim
- staff cast
- prop inspection

## Runtime Consumption Model

The long-term call direction should be:

```text
ActorRuntimeState / facts / command context
-> action / expression request
-> asset descriptor lookup
-> CharacterPresentationInput + ModifierInput
-> KnightRoleSkin / modifiers
```

The runtime should request by tag and context, not by hardcoded clip name whenever possible.

## Near-Term Rule

The current demo may still map a few key tags directly in code, but new architecture work should aim toward:

- explicit descriptors
- explicit modifier profiles
- explicit equipment slot expectations
- explicit skeleton binding compatibility

## Asset-Library Compatibility Goal

The future main-project design expects actions and expressions to be fetched on demand from an asset library.

This repository should therefore optimize toward:

- tag-based requests
- reusable descriptors
- model-agnostic runtime contracts

rather than:

- model-specific hardcoded action assumptions
- logic hidden inside one skin script

## Minimum Documentation Obligation For New Actions

Whenever a new action is added, future contributors should document:

- action tag
- required clips
- required modifier behavior
- required equipment slots
- any special skeleton constraints

That keeps the actor stack generalizable instead of accreting hidden one-off behavior.
