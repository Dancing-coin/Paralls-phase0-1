# Astra Room Realtime Lighting Design

## Goal

Make `AstraRoom.tscn` visually approximate the supplied Blender reference in
Godot's real-time renderer without modifying the imported GLB or Blender source.

## Design

The wrapper scene owns presentation only: a muted blue-gray background, a
cool broad directional daylight, restrained neutral ambient fill, and the
imported floor lamp capped to a safe warm-local-light budget. The cutaway script
continues to hide the three shell meshes that Blender hid for its reference
camera.

The imported asset remains world geometry. Its source materials and node layout
are not rewritten; runtime presentation configuration is isolated to
`AstraRoom.tscn` and `AstraRoomCutaway.gd`.

## Acceptance

- The imported floor lamp energy is capped at 90 or lower at runtime.
- The wrapper has a cool directional daylight at a readable, non-clipping level.
- The wrapper environment uses a blue-gray backdrop and restrained ambient fill.
- A Godot Compatibility-renderer capture shows the furnished cutaway, readable
  furniture colors, and no broad white clipping from the imported lamp.
