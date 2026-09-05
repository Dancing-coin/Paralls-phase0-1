# Stormnight Procedural Low-Poly Character Presentation Design

## Goal

Add visible, reusable low-poly characters to the existing Stormnight Godot
scene without merging the knight church/Throne Hall scene or changing backend
truth ownership.

## Scope and boundaries

The first implementation uses only Godot built-in primitive meshes and
materials. The existing knight assets remain isolated in their current scenes.
Three.js or separately licensed free models may be supported later through the
same presentation profile interface, but are not required for this slice.

Characters are presentation replicas. Canonical actor identity, private
knowledge, action validity, location truth and outcome truth remain owned by the
existing backend services. No character node may append events, choose an
authority, or encode hidden case facts.

## Scene architecture

`ProceduralLowPolyCharacter.tscn` is a reusable `CharacterBody3D` with:

- capsule collision;
- `VisualRoot` containing primitive head, torso, arms, forearms, legs, boots,
  belt, shoulder marker and optional cape marker;
- `AnimationPlayer` for deterministic idle, walk, observe, hide, pursue,
  controlled and returned poses;
- metadata for `actor_ref`, `role_ref` and `presentation_profile_ref`.

`StormnightCopperSanatorium.tscn` instances four replicas at explicit spawn
points. A profile changes only visual parameters: colors, scale, marker shape,
and allowed local presentation states. Profiles never contain truth facts.

## Data flow

```text
committed CaseProjection / ActionWindow result
    -> typed presentation state
    -> local character animation and placement
rejected intent
    -> clear speculative state
    -> restore last committed replica state
```

Character Agent output remains a typed proposal. The existing ActionWindow/P5
authority decides whether an action commits; Godot only renders the committed
result.

## Profiles

The initial four profiles are visually distinct but semantically neutral:

- investigator: blue coat marker;
- guardian: red shoulder marker;
- witness: green scarf marker;
- suspect: amber belt marker.

These labels are presentation choices, not proof of guilt, authority or hidden
knowledge. Any role-to-appearance mapping can be replaced by package content
without changing the case runtime.

## Acceptance evidence

- Stormnight scene contains four low-poly character instances and no reference
  to Throne Hall or `KnightRoleSkin.tscn`.
- Static tests prove primitive-only construction, profile metadata, no backend
  write calls, and no private-fact fields in the visual profile.
- Headless Godot verifies all four replicas load and change state from a
  committed projection.
- ActionWindow/P5 focused tests remain green; rejection restores the committed
  state.
- Existing knight and church scenes remain unchanged and continue their own
  verification paths.
