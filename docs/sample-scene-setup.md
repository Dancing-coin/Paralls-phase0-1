# Sample Scene Setup

## Open Field Layout

`MainDemo.tscn` now uses one open field instead of a multi-room greybox.

- Field footprint: about `80 x 50`
- Vertical feel: about `6.4` with open sky and no ceiling
- Perimeter control: low boundary strips on all four edges instead of tall walls
- Central prop: the table remains the main demo anchor, shifted into the middle-forward area

## Required Runtime Nodes Kept

- `Player` spawn
- `CharacterA`
- `CharacterB`
- `CharacterC`
- `InteractiveObject`
- `EnvironmentStateNode`
- scene lights
- `DebugOverlay`

## Phase 0.5 Role Split

- `Player` remains the current playable locomotion and camera shell that preserves the Phase 0 loop.
- `CharacterA` and `CharacterB` are the current AI-driven in-world role shells.
- `CharacterC` is the first player-driven in-world role shell introduced for the Phase 0.5 relationship-space upgrade.
- `CharacterC` is present in scene structure and spatial staging only for now. It is not yet a separate AI actor or focus target.

## Suggested Placement

- `Player` starts on the south side of the field, looking into the space from a clear approach lane
- `CharacterA` stands to the west-northwest of the table and implicitly controls the key object relationship
- `CharacterB` stands to the east-northeast of the table as the observing witness line
- `CharacterC` stands on the south or entry side as the first in-world player-driven intervener shell, offset from the center line
- `InteractiveObject` stays on the table as the central authority-tested prop
- `EnvironmentStateNode` sits deeper to the north so the world-state reaction reads across open ground

This creates a Phase 0.5 relationship-space split:

- A at the key-object side
- B on the observation side
- C on the player-entry intervention side
- the table and object near the middle so dialogue, interaction, and reaction remain legible in one shared space
- the `Player` shell still approaches from the south so the existing Phase 0 control path does not break

## Suggested Story Beat

- A letter rests on the central table in open view.
- Character A is positioned close enough to react first and read as the role with first claim on the object.
- Character B has a wider flank view and can visibly pick up the Siming-driven beat as the observer.
- Character C enters as the player-driven in-world intervener who crosses the relationship space rather than owning the center.
- The environment state change lands beyond the table so the reaction travels outward across the field instead of feeling trapped inside a room.
