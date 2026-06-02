# Phase 0 Open Scene And Camera Redesign

## Status

- Date: `2026-06-02`
- Scope: `Phase 0` Godot scene and camera redesign only
- Approval source: current user thread

## Purpose

Replace the current multi-room greybox with one large open scene that supports freer movement and avoids the player being visually blocked by walls when moving near boundaries.

This design must stay inside `Phase 0` scope. It must preserve the existing minimum demo loop:

1. one main scene loads
2. two character replicas exist
3. one dialogue submission works
4. one backend dialogue response is observable
5. one voice path is observable
6. one authoritative successful interaction is observable
7. one authoritative failed interaction is observable
8. one visible world-state change is observable
9. one minimal Siming catalyst remains observable

## Current Problem

The current main scene in [scenes/phase0/MainDemo.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/scenes/phase0/MainDemo.tscn:1) is a small indoor greybox with outer walls, partitions, lintels, and a ceiling. Camera visibility is currently protected mainly by [scripts/player/CameraOcclusionFader.gd](/d:/Users/User/Documents/paralls-phase-0-demo/scripts/player/CameraOcclusionFader.gd:1), which fades room walls between the player and the camera.

That mitigation is not enough for the user goal:

- near walls, the player can still be visually blocked
- the small enclosed layout limits free movement
- the room-based fade logic is tailored to indoor partitions, not an open `Phase 0` demo field

## Accepted Design Decisions

The following decisions are accepted from the user discussion:

- Replace the current room-based scene with one large open scene
- Remove all room structures; keep only one large space for free movement
- Scale horizontal play space by `5x`
- Scale scene height by `2x`, not `5x`
- Keep a third-person camera, but retune it for open-space visibility
- Stop relying on room-wall fading as the primary visibility strategy

## Target Scene Shape

The scene should move from roughly `16 x 10 x 3.2` to roughly `80 x 50 x 6.4`.

This is not a “bigger room.” It is a single open greybox field.

### Remove

Remove room-forming structures from the main scene:

- ceiling
- front and back walls
- left and right outer walls
- all partition walls
- all door lintels
- room label cards tied to the old room layout

### Keep

Keep only the minimum spatial elements required for `Phase 0`:

- one large walkable floor
- low boundary geometry around the play area
- player
- `CharacterA`
- `CharacterB`
- the interaction table and `InteractiveObject`
- `EnvironmentStateNode`
- lighting and debug overlay

## Boundary Strategy

Do not replace room walls with taller perimeter walls.

Use a low-visibility boundary approach:

- low physical boundary around the field
- target height around waist level, roughly `0.8 - 1.1`
- enough collision to keep the player inside the demo space
- low enough to avoid becoming the dominant camera occluder

Possible boundary expressions are acceptable as long as they stay low and simple:

- continuous low curb
- shallow edge embankment
- sparse visual markers paired with collision

The preferred implementation is a simple continuous low greybox boundary because it is easiest to read, easiest to tune, and least risky for `Phase 0`.

## Layout Plan

The large field should use a wide triangular layout to avoid crowding the demo actors and props into one small center cluster.

### Placement intent

- Player spawn: lower-middle portion of the field
- `CharacterA`: front-left
- `CharacterB`: front-right
- interaction table and `InteractiveObject`: near center-forward
- `EnvironmentStateNode`: farther forward, still visible/reachable

### Layout goals

- immediate sense of free movement on spawn
- clear separation between actors, object interaction, and environment reaction space
- enough open ground for turning, camera rotation, and approach/retreat movement
- preserve the short repeatable `Phase 0` demo loop without needing multiple scenes

## Camera Strategy

The camera should remain third-person, but shift from “fade the room away” to “actively avoid losing the player.”

### Primary behavior

- slightly higher viewing angle than the current setup
- slightly stronger downward pitch
- mid-to-long default spring arm length
- automatic spring-arm shortening when geometry presses into the camera path
- small upward bias to the tracked framing when near boundaries or tall props

### Secondary behavior

[scripts/player/CameraOcclusionFader.gd](/d:/Users/User/Documents/paralls-phase-0-demo/scripts/player/CameraOcclusionFader.gd:1) should no longer treat room walls as its main target set.

Its role should become one of these:

1. fallback fade for a small number of taller props
2. simplified utility that can potentially be removed if low-boundary geometry solves the issue cleanly

The preferred direction is to keep it only as a fallback for a few taller obstacles, not as the main visibility system.

## Files Expected To Change During Implementation

Primary files:

- [scenes/phase0/MainDemo.tscn](/d:/Users/User/Documents/paralls-phase-0-demo/scenes/phase0/MainDemo.tscn:1)
- [scripts/player/CameraOcclusionFader.gd](/d:/Users/User/Documents/paralls-phase-0-demo/scripts/player/CameraOcclusionFader.gd:1)
- [scripts/phase0/MainDemoController.gd](/d:/Users/User/Documents/paralls-phase-0-demo/scripts/phase0/MainDemoController.gd:1)

Possible additional file:

- one small player-camera helper script, only if the current controller chain cannot express the boundary-aware adjustments cleanly

## Constraints

- Stay inside `Phase 0`; do not expand into `Phase 1` redesign
- Do not add new dependencies
- Keep the existing backend protocol and gameplay loop intact
- Preserve the root Godot project
- Prefer small, reviewable changes over controller rewrites

## Verification Plan

Implementation will not be considered complete unless it is verified at three levels.

### Scene verification

- `MainDemo.tscn` opens without scene/script errors
- the scene is a single open field, not a multi-room layout
- room partitions, ceiling, and room walls are removed

### Camera verification

- player remains visible near field boundaries
- player remains visible when moving around the central table/object area
- camera no longer depends on tall wall fade behavior to stay usable

### Phase 0 loop verification

- two characters still load and remain interactable
- dialogue path still works
- object interaction path still works
- environment change remains visible
- minimal Siming reaction remains observable

## Risks And Controls

### Risk: open scene makes the demo feel too empty

Control:

- keep the field large, but stage the active elements in a readable central-forward cluster

### Risk: camera tuning regresses third-person feel

Control:

- preserve third-person framing and only increase height/pitch enough to solve visibility

### Risk: removing room geometry breaks current fade assumptions

Control:

- simplify fade logic intentionally instead of trying to preserve room-name-based behavior

### Risk: layout changes break autotest vantage assumptions

Control:

- retune the `MainDemoController` demo vantage and focus positions as part of the same change

## Non-Goals

This redesign does not include:

- new story content
- new backend systems
- new interaction protocol shapes
- multi-scene expansion
- full camera-system rewrite
- full production-level environment art pass

## Implementation Recommendation

Use the smallest implementation path that achieves the user goal:

1. rebuild the main scene into one open field
2. remove room-specific occluder assumptions
3. retune camera height, pitch, and spring-arm behavior
4. verify that `Phase 0` demo interactions still run end-to-end
