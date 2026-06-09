# Phase 0 Open Scene Camera Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the `Phase 0` Godot main scene into one large open field and retune the third-person camera so the player stays visible near boundaries without depending on room-wall fade logic.

**Architecture:** Keep the existing `Phase 0` runtime loop and backend contract unchanged. Concentrate the change in three places: the main scene layout in `MainDemo.tscn`, the camera/occlusion behavior in `CameraOcclusionFader.gd`, and the demo-specific camera tuning in `MainDemoController.gd`. Prefer small scene and script edits over controller rewrites or new systems.

**Tech Stack:** Godot 4.6 scene files, GDScript, existing Jeheno third-person camera controller, pytest for backend regression.

---

## Status Snapshot

- Date: `2026-06-10`
- Plan status: executed and verified for the repository-local target
- Current code truth:
  - `MainDemo.tscn` uses an open-field layout with `80 x 50` walkable footprint
  - scene tuning in `MainDemoController.gd` matches the open-field camera/focus requirements
  - `CameraOcclusionFader.gd` no longer depends on the old room-wall naming conventions
  - `docs/sample-scene-setup.md` describes the open-field layout
- Verification evidence:
  - `backend/tests/test_verification_audit.py::test_phase0_open_scene_camera_artifacts_match_open_field_layout`
  - current worktree scene contains `size = Vector2(80, 50)` and `size = Vector3(80, 0.2, 50)`
  - current worktree controller contains `@export var focus_max_distance := 28.0`
  - current worktree controller contains `spring_length = 6.6`

## File Structure

### Modify

- `scenes/phase0/MainDemo.tscn`
  - Replace the room-shaped greybox with one open field sized to the approved `80 x 50 x 6.4` target.
  - Remove ceiling, outer walls, partitions, lintels, and room cards.
  - Keep player, characters, interaction object, environment node, lights, and debug overlay.
  - Reposition actors and props into the approved wide triangular layout.
- `scripts/player/CameraOcclusionFader.gd`
  - Stop targeting room-wall naming conventions.
  - Either fade only a small fallback set of taller props or harmlessly no-op when no fallback occluders exist.
- `scripts/phase0/MainDemoController.gd`
  - Retune focus distance and autotest/demo vantage values for the larger field.
  - Retune default camera pitch and spring-arm values for the open-scene layout.
- `docs/sample-scene-setup.md`
  - Update the scene description so it matches the new single open field instead of the old room layout.

### Verify only

- `backend/tests/test_ws_protocol.py`
- `backend/tests/test_session_runtime.py`
- `backend/tests/test_character_service.py`
- `backend/tests/test_esm_service.py`
- `backend/tests/test_siming_service.py`
- `backend/tests/test_demo_script.py`

### Git note

This workspace currently does not expose a `.git` directory, so this plan does not include commit steps. If the repository is reattached to Git before execution, add Lore-format commits at the end of each completed task group instead of after every micro-step.

## Task 1: Lock The Main Scene Into An Open Field

**Files:**
- Modify: `scenes/phase0/MainDemo.tscn`

- [ ] **Step 1: Read the current scene nodes that define the room shell**

Run: `rg -n "GreyboxRoomRoot|BackWall|FrontWall|OuterWall|Partition|DoorLintel|Ceiling|Room.ACard|Room.BCard|Room.CCard|TableTop|CharacterA|CharacterB|InteractiveObject|EnvironmentStateNode|Player" scenes/phase0/MainDemo.tscn`

Expected: room shell nodes and retained gameplay nodes are listed from `MainDemo.tscn`.

- [ ] **Step 2: Replace the room floor mesh and collision sizes with the approved field dimensions**

Update the scene resources in `scenes/phase0/MainDemo.tscn` to:

```text
[sub_resource type="PlaneMesh" id="PlaneMesh_1"]
size = Vector2(80, 50)

[sub_resource type="BoxShape3D" id="BoxShape3D_Floor"]
size = Vector3(80, 0.2, 50)
```

Expected result: the walkable field is `80 x 50`.

- [ ] **Step 3: Remove the old room shell nodes from the scene**

Delete these node families from `scenes/phase0/MainDemo.tscn`:

```text
Ceiling
CeilingBody
BackWall
BackWallBody
FrontWall
FrontWallBody
LeftOuterWall
LeftOuterWallBody
RightOuterWall
RightOuterWallBody
PartitionLeftTop
PartitionLeftTopBody
PartitionLeftBottom
PartitionLeftBottomBody
PartitionRightTop
PartitionRightTopBody
PartitionRightBottom
PartitionRightBottomBody
DoorLintelLeft
DoorLintelLeftBody
DoorLintelRight
DoorLintelRightBody
RoomACard
RoomBCard
RoomCCard
```

Expected result: no multi-room shell remains in the scene file.

- [ ] **Step 4: Remove room-shell-only subresources that are no longer referenced**

Delete these unused resource blocks from `scenes/phase0/MainDemo.tscn` after the node removal:

```text
BoxMesh_LongWall
BoxMesh_ShortWall
BoxMesh_InnerWallShort
BoxMesh_InnerWallCap
BoxMesh_Ceiling
BoxShape3D_LongWall
BoxShape3D_ShortWall
BoxShape3D_InnerWallShort
BoxShape3D_InnerWallCap
BoxShape3D_Ceiling
StandardMaterial3D_Ceiling
StandardMaterial3D_AccentA
StandardMaterial3D_AccentB
StandardMaterial3D_AccentC
BoxMesh_DecorPanel
```

Expected result: the scene contains only resources needed by the open field and retained demo props.

- [ ] **Step 5: Add low boundary geometry around the field**

Add four low boundary meshes and bodies under `RoomVisualRoot/GreyboxRoomRoot` using these target dimensions:

```text
Boundary long mesh size: Vector3(80, 0.9, 0.6)
Boundary short mesh size: Vector3(0.6, 0.9, 50)
Boundary long body shape: Vector3(80, 0.9, 0.6)
Boundary short body shape: Vector3(0.6, 0.9, 50)

Back boundary position:  Vector3(0, 0.45, -24.7)
Front boundary position: Vector3(0, 0.45, 24.7)
Left boundary position:  Vector3(-39.7, 0.45, 0)
Right boundary position: Vector3(39.7, 0.45, 0)
```

Name them:

```text
BackBoundary
BackBoundaryBody
FrontBoundary
FrontBoundaryBody
LeftBoundary
LeftBoundaryBody
RightBoundary
RightBoundaryBody
```

Expected result: the player is kept inside the field by low curbs instead of tall walls.

- [ ] **Step 6: Reposition the player, characters, object, and environment node for the wide triangular layout**

Update these transforms in `scenes/phase0/MainDemo.tscn`:

```text
Player:               Vector3(0, 0.5, 16)
CharacterA:           Vector3(-14, 0, 2)
CharacterB:           Vector3(14, 0, 2)
InteractiveObject:    Vector3(0, 0.95, -4)
EnvironmentStateNode: Vector3(0, 1.8, -16)
```

Expected result: the scene reads as one open field with clear separation between actors and interaction targets.

- [ ] **Step 7: Reposition the table and fill lights to match the larger field**

Update the table root and light nodes in `scenes/phase0/MainDemo.tscn`:

```text
TableTop:    Vector3(0, 0.85, -4)
TableTopBody: Vector3(0, 0.85, -4)
TableLegA:   Vector3(-0.9, 0.4, -3.6)
TableLegB:   Vector3(0.9, 0.4, -3.6)
TableLegC:   Vector3(-0.9, 0.4, -4.4)
TableLegD:   Vector3(0.9, 0.4, -4.4)

FillLightA:  Vector3(-18, 2.6, 8)
FillLightB:  Vector3(0, 2.8, -4)
FillLightC:  Vector3(18, 2.6, 8)
```

Expected result: the central interaction area remains readable inside the larger field.

- [ ] **Step 8: Run a static scene sanity check**

Run: `rg -n "Partition|DoorLintel|OuterWall|BackWall|FrontWall|Ceiling|Room.ACard|Room.BCard|Room.CCard" scenes/phase0/MainDemo.tscn`

Expected: no matches.

## Task 2: Retune The Demo Camera For Open-Space Visibility

**Files:**
- Modify: `scripts/phase0/MainDemoController.gd`
- Verify: `addons/JehenoThirdPersonController/PlayerCharacter/Camera/camera_holder_scene.tscn`
- Verify: `addons/JehenoThirdPersonController/PlayerCharacter/Camera/camera_holder_script.gd`

- [ ] **Step 1: Read the current demo camera tuning points**

Run: `rg -n "focus_max_distance|focus_forward_threshold|autotest_final_position|rotation.x|spring_length" scripts/phase0/MainDemoController.gd addons/JehenoThirdPersonController/PlayerCharacter/Camera/camera_holder_scene.tscn addons/JehenoThirdPersonController/PlayerCharacter/Camera/camera_holder_script.gd`

Expected: current focus distance, final demo vantage, pitch, and spring-arm settings are listed.

- [ ] **Step 2: Expand the focus range for the larger field**

Update the exported values in `scripts/phase0/MainDemoController.gd`:

```gdscript
@export var autotest_final_position := Vector3(0.0, 0.5, 20.0)
@export var focus_max_distance := 10.0
@export var focus_forward_threshold := 0.2
```

Expected result: the focus picker can still acquire characters and the interaction target in the open layout.

- [ ] **Step 3: Retune the default autotest/demo camera pitch and spring length**

Update `_move_player_to_demo_vantage()` in `scripts/phase0/MainDemoController.gd` to:

```gdscript
func _move_player_to_demo_vantage() -> void:
	player.global_position = autotest_final_position
	_orient_player_toward(interactive_object.global_position)
	var camera_holder := _get_camera_holder()
	if camera_holder:
		camera_holder.rotation.x = deg_to_rad(-22.0)
		var spring_arm := camera_holder.find_child("SpringArm3D", true, false)
		if spring_arm is SpringArm3D:
			(spring_arm as SpringArm3D).spring_length = 7.2
```

Expected result: the demo vantage sees more of the field from a higher, more downward angle.

- [ ] **Step 4: Add a reusable open-field camera tuning helper**

Add this method to `scripts/phase0/MainDemoController.gd`:

```gdscript
func _configure_open_field_camera() -> void:
	var camera_holder := _get_camera_holder()
	if camera_holder == null:
		return

	camera_holder.rotation.x = deg_to_rad(-20.0)
	var spring_arm := camera_holder.find_child("SpringArm3D", true, false)
	if spring_arm is SpringArm3D:
		(spring_arm as SpringArm3D).spring_length = 6.6
```

Expected result: the open-field defaults are not duplicated across the controller.

- [ ] **Step 5: Call the new camera helper during scene startup**

In `_ready()` in `scripts/phase0/MainDemoController.gd`, insert the helper call before backend connection:

```gdscript
func _ready() -> void:
	var bus := _get_bus()
	if bus:
		bus.backend_connected.connect(_on_backend_connected)
		bus.backend_ack_received.connect(_on_backend_ack_received)
	_configure_open_field_camera()
	_bus_log("phase0_main_ready")
	autotest_enabled = OS.get_environment("PHASE0_AUTOTEST") == "1"
	call_deferred("_connect_backend")
```

Expected result: the open-field camera defaults are active on first load.

- [ ] **Step 6: Add a small focus-origin lift so near-boundary framing stays more stable**

Update `_get_focus_origin()` in `scripts/phase0/MainDemoController.gd` to:

```gdscript
func _get_focus_origin() -> Vector3:
	return player.global_position + Vector3(0.0, 1.0, 0.0)
```

Expected result: focus checks aim from the player body height instead of the feet.

- [ ] **Step 7: Run a controller syntax scan**

Run: `Get-Content scripts\phase0\MainDemoController.gd`

Expected: new helper, wider focus range, and updated demo vantage values are present with no duplicate method names.

## Task 3: Simplify Occlusion Fading For The Open Field

**Files:**
- Modify: `scripts/player/CameraOcclusionFader.gd`

- [ ] **Step 1: Read the room-specific occluder assumptions**

Run: `rg -n "_is_room_occluder|WallBody|Partition|DoorLintel|GreyboxRoomRoot" scripts/player/CameraOcclusionFader.gd`

Expected: the current room-name-based filter is listed.

- [ ] **Step 2: Rename the room-specific filter to an open-field fallback filter**

Replace the old call site and function name:

```gdscript
if _is_fallback_occluder(collider):
	var mesh := _resolve_mesh_for_body(collider)
	if mesh:
		result[mesh] = true
```

and:

```gdscript
func _is_fallback_occluder(collider: Object) -> bool:
```

Expected result: the script no longer encodes “room occluder” as its main concept.

- [ ] **Step 3: Replace the body-name filter with a narrow fallback set**

Implement `_is_fallback_occluder()` as:

```gdscript
func _is_fallback_occluder(collider: Object) -> bool:
	if not (collider is StaticBody3D):
		return false

	var body := collider as StaticBody3D
	var body_name := body.name
	if not (
		body_name.ends_with("TableTopBody")
		or body_name.ends_with("BoundaryBody")
	):
		return false

	return true
```

Expected result: only the larger remaining props can trigger fade as a fallback.

- [ ] **Step 4: Prevent low boundary curbs from fading aggressively**

Add this helper to `scripts/player/CameraOcclusionFader.gd`:

```gdscript
func _should_skip_low_boundary(mesh: MeshInstance3D) -> bool:
	return mesh.name.ends_with("Boundary") and sample_height >= 1.0
```

Then gate the result collection:

```gdscript
if _is_fallback_occluder(collider):
	var mesh := _resolve_mesh_for_body(collider)
	if mesh and not _should_skip_low_boundary(mesh):
		result[mesh] = true
```

Expected result: low curbs do not flash transparent during normal movement.

- [ ] **Step 5: Run a static script sanity check**

Run: `rg -n "Partition|DoorLintel|WallBody|_is_room_occluder" scripts/player/CameraOcclusionFader.gd`

Expected: no matches.

## Task 4: Update The Human Runbook To Match The New Scene

**Files:**
- Modify: `docs/sample-scene-setup.md`

- [ ] **Step 1: Read the current sample scene setup**

Run: `Get-Content docs\sample-scene-setup.md`

Expected: the old short setup description is shown.

- [ ] **Step 2: Replace the old room-oriented setup text with the new open-field layout**

Write `docs/sample-scene-setup.md` with content equivalent to:

```md
# Sample Scene Setup

- Main scene: `scenes/phase0/MainDemo.tscn`
- Play field: single open greybox field, approximately `80 x 50 x 6.4`
- Boundary: low curb around the field, not tall room walls
- Player spawn: lower-middle of the field
- Character A: front-left of the player
- Character B: front-right of the player
- Interaction table and `obj_letter`: center-forward
- Environment state node: farther forward beyond the interaction table
- Goal: keep all `Phase 0` demo targets reachable inside one open free-movement space
```

Expected result: the runbook matches the approved open scene design.

## Task 5: Verify Scene, Runtime, and Regression Safety

**Files:**
- Verify: `scenes/phase0/MainDemo.tscn`
- Verify: `scripts/phase0/MainDemoController.gd`
- Verify: `scripts/player/CameraOcclusionFader.gd`
- Verify: `backend/tests/test_ws_protocol.py`
- Verify: `backend/tests/test_session_runtime.py`
- Verify: `backend/tests/test_character_service.py`
- Verify: `backend/tests/test_esm_service.py`
- Verify: `backend/tests/test_siming_service.py`
- Verify: `backend/tests/test_demo_script.py`

- [ ] **Step 1: Confirm the main scene is now single-field and wall-free**

Run: `rg -n "Partition|DoorLintel|OuterWall|BackWall|FrontWall|Ceiling" scenes/phase0/MainDemo.tscn`

Expected: no matches.

- [ ] **Step 2: Confirm the new boundary nodes exist**

Run: `rg -n "BackBoundary|FrontBoundary|LeftBoundary|RightBoundary" scenes/phase0/MainDemo.tscn`

Expected: all four boundaries and their body nodes are listed.

- [ ] **Step 3: Run backend regression tests**

Run: `python -m pytest -v`

Workdir: `backend`

Expected: existing backend tests pass.

- [ ] **Step 4: Open the Godot main scene and verify it loads without immediate errors**

Run one of:

```powershell
godot4 --path . --scene res://scenes/phase0/MainDemo.tscn
```

or:

```powershell
godot4 --path .
```

Expected: the scene opens, the open field is visible, and there are no immediate scene/script load errors.

- [ ] **Step 5: Manually verify the visibility goal in runtime**

Verify these behaviors in the running scene:

```text
1. Move the player to each field boundary.
2. Rotate the camera along each boundary.
3. Confirm the player remains visible instead of being hidden behind tall walls.
4. Move around the table and object area.
5. Confirm the camera remains usable without frequent transparent-wall flashing.
```

Expected: the player remains visible near boundaries and the interaction area.

- [ ] **Step 6: Manually verify the Phase 0 loop still works**

Verify:

```text
1. Both characters remain present.
2. Dialogue submit still triggers a backend request.
3. One interaction still succeeds through backend authority.
4. One interaction still fails with a structured constraint result.
5. One visible environment or object state change still occurs.
6. One minimal Siming reaction is still observable.
```

Expected: the open-scene redesign does not break the existing `Phase 0` demo loop.

## Self-Review

### Spec coverage

- Open field target size: covered in Task 1, Steps 2 and 5.
- Remove all room structures: covered in Task 1, Steps 3, 4, and Task 5, Step 1.
- Low boundary instead of high walls: covered in Task 1, Step 5 and Task 3, Step 4.
- Wide triangular layout: covered in Task 1, Steps 6 and 7.
- Third-person camera retune: covered in Task 2.
- Stop depending on room-wall fading: covered in Task 3.
- Preserve `Phase 0` runtime loop: covered in Task 5, Steps 3 through 6.

No coverage gaps found.

### Placeholder scan

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Each task contains exact files, concrete values, and explicit verification commands.

### Type consistency

- `Boundary` / `BoundaryBody` naming is used consistently across scene, fade logic, and verification.
- `autotest_final_position`, `_configure_open_field_camera()`, and `_get_focus_origin()` names are consistent with the current controller file.
