# Phase 0.5 Scene Zones

This brief upgrades `MainDemo.tscn` from a simple open-field staging into a minimal relationship-space layout without breaking the existing Phase 0 loop.

## Five-Zone Brief

### 1. South Entry / Intervention Zone

- Purpose: clear player approach lane and first intervention space.
- Primary occupants: `Player` shell and `CharacterC`.
- Constraint: keep this zone off the center so `CharacterC` reads as an entering in-world role shell, not as the default focal anchor.

### 2. Central Object Authority Zone

- Purpose: hold the key object and the main authority-tested interaction.
- Primary occupants: `InteractiveObject` and `CharacterA`'s nearest line of influence.
- Constraint: object interaction readability must remain unchanged from the current Phase 0 loop.

### 3. West Control Zone

- Purpose: stage `CharacterA` as the role with first control pressure over the key object.
- Primary occupant: `CharacterA`.
- Constraint: A should stay close enough to the object that its relation is legible at a glance.

### 4. East Observation Zone

- Purpose: stage `CharacterB` as the witness and reaction reader rather than the primary intervener.
- Primary occupant: `CharacterB`.
- Constraint: B should keep line-of-sight across the object and toward the north reaction space.

### 5. North Reaction Zone

- Purpose: receive the environment or Siming-visible payoff beyond the object.
- Primary occupant: `EnvironmentStateNode`.
- Constraint: changes here should read as a scene-level consequence, not a local table-only toggle.

## Relationship Model Summary

- A controls the key object relationship.
- B observes and witnesses the shift.
- C is the first player-driven in-world intervener.
- `Player` remains the current playable shell, so focus and interaction behavior stay on the existing Phase 0 path.
