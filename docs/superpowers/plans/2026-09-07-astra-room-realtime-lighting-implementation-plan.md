# Astra Room Realtime Lighting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Match the supplied Astra room reference's soft, pastel real-time lighting in Godot.

**Architecture:** `AstraRoom.tscn` owns static WorldEnvironment and daylight settings. `AstraRoomCutaway.gd` continues to repair GLB-only presentation differences at runtime, including its oversized imported lamp. A focused Godot probe verifies both static settings and runtime light capping.

**Tech Stack:** Godot 4.6, GDScript, Forward/Compatibility scene rendering.

---

### Task 1: Lock The Lighting Profile

**Files:**
- Create: `scripts/verification/AstraRoomLightingProfileProbe.gd`
- Test: `scripts/verification/AstraRoomLightingProfileProbe.gd`

- [ ] **Step 1: Write the failing probe**

```gdscript
assert(room_environment.background_color.is_equal_approx(Color(0.23, 0.27, 0.31, 1)))
assert(daylight.light_energy == 0.42)
assert(imported_floor_lamp.light_energy <= 90.0)
```

- [ ] **Step 2: Run the probe to verify it fails**

Run: `Godot_v4.6.3-stable_win64_console.exe --headless --path . --script res://scripts/verification/AstraRoomLightingProfileProbe.gd`

Expected: Failure because the pre-change scene has no `WindowDaylight` and its imported lamp is capped at 120.

- [ ] **Step 3: Implement the minimal presentation settings**

Set the wrapper's blue-gray environment, create `WindowDaylight` at energy `0.42`, and reduce `MAX_IMPORTED_OMNI_ENERGY` to `90.0`.

- [ ] **Step 4: Run the probe to verify it passes**

Run: `Godot_v4.6.3-stable_win64_console.exe --headless --path . --script res://scripts/verification/AstraRoomLightingProfileProbe.gd`

Expected: `ASTRA_LIGHTING_PROFILE_PASS`.

### Task 2: Verify The Runtime View

**Files:**
- Modify: `scenes/phase0/AstraRoom.tscn`
- Modify: `scripts/presentation/environment/AstraRoomCutaway.gd`

- [ ] **Step 1: Run a Compatibility-renderer capture**

Run the temporary capture scene at `1280x720` with `--rendering-method gl_compatibility`.

- [ ] **Step 2: Compare the capture with `source/runs/high/room_preview.png`**

Pass criteria: the cutaway room is framed, wall and floor details remain visible, and the warm sofa is distinguishable from the pale walls.

- [ ] **Step 3: Re-run the headless scene parse**

Run: `Godot_v4.6.3-stable_win64_console.exe --headless --path . --scene res://scenes/phase0/AstraRoom.tscn --quit-after 2`

Expected: exit code 0 with no scene parse errors.
