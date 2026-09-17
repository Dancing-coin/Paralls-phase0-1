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

The active contract is no longer merely suggestive. It is defined by the
2026-09-14 unified action-foundation spec and must remain presentation/action
metadata only:

```text
CharacterActionAssetDescriptor {
  semantic_action_id
  source_clip_ref
  realization_profiles
  canonical_skeleton_mapping_ref
  canonical_bone_mask_ref?
  atomic_sequence              # Phase 1: []
  resource_claims
  physics_claims
  physics_profile_ref
  authority_route_ref
  required_clips
  optional_clips
  locomotion_compatibility
  cancel_windows
  timing_markers
  root_motion_profile?
  root_motion_policy           # hold | bounded_continue | reversible_continue
  root_motion_required
  fallback_policy              # exclusive | queue_until_compatible | reject | presentation_only
  qualification_report_ref
  presentation_tags
  required_slots
  allowed_control_modes?
}
```

The complete field semantics belong to the active unified action-foundation
spec and its physics/ESM/animation-qualification child specifications. This
document is an asset interface index, not a second authority contract.

`realization_profiles` allow one semantic action to expose a native upper-body
clip, a build-time derived upper-body clip, a full-body exclusive clip, a
locomotion-driving clip, or an additive clip. Profile selection is based on
qualification results and current claims; it is never inferred from a folder
name or performed by runtime track surgery.

The detailed import, canonical mapping, full-body derivation, mask validation,
fallback, and qualification-report contract lives in:

`docs/superpowers/specs/2026-09-14-character-animation-asset-qualification-and-concurrent-realization-subspec.md`

For external handoff, its `Normative Phase 1 Asset Delivery Rules` section is
the binding checklist. This interface document intentionally does not create a
second set of asset acceptance rules.

## Task 7 Staging Evidence

`assets/active/crusader_knight/manifest.json` is a qualified-with-fallback
external package. Its imported clips include lower-body/root/pelvis curves, so
its declared melee action is full-body exclusive and Walk/Run concurrency is
not claimed. `assets/active/external_character_b/manifest.json` is a
source-provenance-preserving staged candidate, rejected from runtime admission:
the supplied asset exposes only `anim_drink` and `anim_knock`, rather than a
verified locomotion suite or native/derived upper-body realization. The
machine-readable reports and candidate statuses are in
`assets/characters/qualification_reports/`; names and paths do not promote a
rejected candidate.

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

## Phase 1 Weapon Slice

The first milestone uses the existing descriptor/claims path for a deliberately
small weapon contract. At least one qualified package must expose a held-item
slot and hand anchor plus a phase-marked melee action. A semantic hitscan
profile is also valid for request/authority tests, but does not imply that
ammunition, ballistics, projectile simulation, or client-side damage exists.

```text
EquipmentBinding {
  slot_id
  anchor_ref
  item_ref
  attachment_mode
}

WeaponActionProfile {
  semantic_action_id
  action_family       # melee | hitscan
  weapon_ref
  resource_claims
  physics_claims
  timing_markers
  authority_route_ref
}
```

Weapon profiles remain ordinary action profiles. They do not introduce a
parallel `WeaponLayer` scheduler, and they may not contain `damage`, `hit`,
`ammo`, or direct transform fields.

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

Action tags are namespaced at runtime (`action:sword_swing`,
`phase:contact`, `presentation:combat_ready`). An action descriptor must not
contain authoritative damage, status application, inventory mutation, or
death settlement. Timing markers create local presentation events or
structured ActionAttempt candidates; Motor/sensor evidence and ESM/Gameplay
validation are still required. Markers do not settle local damage or world
truth.

For the first milestone, `atomic_sequence` is always empty. Future values are
semantic atom IDs resolved by a versioned registry before resource arbitration;
they are not animation clip names and do not bypass physics claims or ESM
settlement.

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

## Relation To INF Metadata

INF metadata such as goals, evidence, confidence, provenance, constraints,
causation, correlation, revision, and privacy scope is carried as context for
asset resolution and action admission. It is not copied wholesale into the
local action-state tag set. The legal direction is:

```text
INF / CharacterAgent metadata
-> IntentProposal
-> action descriptor resolution and layer arbitration
-> contact event
-> authority result
-> CharacterRuntimeState projection
```

## Minimum Documentation Obligation For New Actions

Whenever a new action is added, future contributors should document:

- action tag
- required clips
- available realization profiles and fallback policy
- required modifier behavior
- required equipment slots
- any special skeleton constraints
- qualification report and source/derived clip provenance

That keeps the actor stack generalizable instead of accreting hidden one-off behavior.
