# Phase 0.5 Character Scene Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the current demo into a stronger `Phase 0.5` base where `A/B` remain AI-driven, `C` becomes the first player-driven in-world role on the same role-agent substrate, and the scene becomes a readable semi-open intervention space.

**Architecture:** Keep the current `Phase 0` loop alive while strengthening two foundations in parallel. The character side evolves `CharacterReplica` from a demo callback shell into a shared execution layer with explicit driver modes and a `mixabridge`-ready asset/action pipeline. The scene side evolves the open field from a technical greybox into a `homebuilder`-shaped relationship space with an intervention entry, a control zone for `A`, an observation zone for `B`, and a focal object/environment chain.

**Tech Stack:** Godot 4.6 scene files, GDScript, current WebSocket backend demo services, `mixabridge`, `home_builder`, project-local Markdown reference docs.

---

## Status Snapshot

- Date: `2026-06-10`
- Plan status: executed and verified for the repository-local target
- Current code truth:
  - `CharacterC` exists as the first player-driven in-world role shell on the shared role substrate
  - explicit driver-spec and execution notes exist
  - scene-zone notes exist
  - `mixabridge` and `homebuilder` pipeline notes exist
  - the sample scene description reflects the upgraded role split
- Verification evidence:
  - `backend/tests/test_verification_audit.py::test_phase05_character_scene_upgrade_artifacts_exist_and_match_role_split`
  - current worktree contains `scripts/character/CharacterDriverSpec.gd`
  - current worktree contains `docs/character-execution-notes.md`
  - current worktree contains `docs/phase05-scene-zones.md`
  - current worktree contains `docs/mixabridge-character-pipeline.md`
  - current worktree contains `docs/homebuilder-scene-pipeline.md`

## File Structure

### Copy from main project into local reference docs

- Create: `docs/reference/phase1-character-agent/07-L4执行层与具身表达总纲.md`
- Create: `docs/reference/phase1-character-agent/08-玩家接管、挂机接管与旅人-角色边界设计.md`
- Create: `docs/reference/phase1-character-agent/12-Embodiment Binder v0.1 规范.md`
- Create: `docs/reference/phase1-character-agent/13-FACS-SACS Planner 规范.md`
- Create: `docs/reference/phase1-character-agent/14-Canonical Rig 与 Asset Adapter 规范.md`
- Create: `docs/reference/phase1-character-agent/19-角色智能体与事件总线契约.md`
- Create: `docs/reference/phase1-event-bus/03-Godot本地表现总线设计.md`
- Create: `docs/reference/phase1-event-bus/04-感知链路与候选事件设计.md`

### Character line

- Modify: `scenes/phase0/CharacterReplica.tscn`
- Modify: `scripts/character/CharacterReplica.gd`
- Modify: `scripts/player/Phase0PlayerBridge.gd`
- Modify: `scripts/phase0/MainDemoController.gd`
- Create: `scripts/character/CharacterDriverSpec.gd`
- Create: `docs/character-execution-notes.md`

### Scene line

- Modify: `scenes/phase0/MainDemo.tscn`
- Modify: `docs/sample-scene-setup.md`
- Create: `docs/phase05-scene-zones.md`

### Asset pipeline / plugin line

- Create: `assets/characters/README.md`
- Create: `assets/environment/README.md`
- Create: `assets/props/README.md`
- Create: `docs/mixabridge-character-pipeline.md`
- Create: `docs/homebuilder-scene-pipeline.md`

### Verification

- Verify: `backend/tests/test_ws_protocol.py`
- Verify: `backend/tests/test_session_runtime.py`
- Verify: `backend/tests/test_character_service.py`
- Verify: `backend/tests/test_esm_service.py`
- Verify: `backend/tests/test_siming_service.py`
- Verify: `backend/tests/test_demo_script.py`

### Git note

The workspace still does not expose a `.git` directory. Do not include commit steps during execution unless the repository is reattached to Git.

## Task 1: Vendor The Main-Project Reference Set Locally

**Files:**
- Create: `docs/reference/phase1-character-agent/07-L4执行层与具身表达总纲.md`
- Create: `docs/reference/phase1-character-agent/08-玩家接管、挂机接管与旅人-角色边界设计.md`
- Create: `docs/reference/phase1-character-agent/12-Embodiment Binder v0.1 规范.md`
- Create: `docs/reference/phase1-character-agent/13-FACS-SACS Planner 规范.md`
- Create: `docs/reference/phase1-character-agent/14-Canonical Rig 与 Asset Adapter 规范.md`
- Create: `docs/reference/phase1-character-agent/19-角色智能体与事件总线契约.md`
- Create: `docs/reference/phase1-event-bus/03-Godot本地表现总线设计.md`
- Create: `docs/reference/phase1-event-bus/04-感知链路与候选事件设计.md`

- [ ] **Step 1: Create the local reference directories**

Run:

```powershell
New-Item -ItemType Directory -Force docs/reference/phase1-character-agent | Out-Null
New-Item -ItemType Directory -Force docs/reference/phase1-event-bus | Out-Null
```

Expected: both reference folders exist locally.

- [ ] **Step 2: Copy the character-agent reference files from the main project**

Run:

```powershell
Copy-Item 'D:\Projects\Paralls\docs\phase1\core\01-运行时核心\角色智能体\07-L4执行层与具身表达总纲.md' 'docs/reference/phase1-character-agent/'
Copy-Item 'D:\Projects\Paralls\docs\phase1\core\01-运行时核心\角色智能体\08-玩家接管、挂机接管与旅人-角色边界设计.md' 'docs/reference/phase1-character-agent/'
Copy-Item 'D:\Projects\Paralls\docs\phase1\core\01-运行时核心\角色智能体\12-Embodiment Binder v0.1 规范.md' 'docs/reference/phase1-character-agent/'
Copy-Item 'D:\Projects\Paralls\docs\phase1\core\01-运行时核心\角色智能体\13-FACS-SACS Planner 规范.md' 'docs/reference/phase1-character-agent/'
Copy-Item 'D:\Projects\Paralls\docs\phase1\core\01-运行时核心\角色智能体\14-Canonical Rig 与 Asset Adapter 规范.md' 'docs/reference/phase1-character-agent/'
Copy-Item 'D:\Projects\Paralls\docs\phase1\core\01-运行时核心\角色智能体\19-角色智能体与事件总线契约.md' 'docs/reference/phase1-character-agent/'
```

Expected: all six character-agent references are available inside the demo workspace.

- [ ] **Step 3: Copy the event-bus reference files from the main project**

Run:

```powershell
Copy-Item 'D:\Projects\Paralls\docs\phase1\core\01-运行时核心\事件总线\03-Godot本地表现总线设计.md' 'docs/reference/phase1-event-bus/'
Copy-Item 'D:\Projects\Paralls\docs\phase1\core\01-运行时核心\事件总线\04-感知链路与候选事件设计.md' 'docs/reference/phase1-event-bus/'
```

Expected: both event-bus references are available inside the demo workspace.

- [ ] **Step 4: Verify the copied reference set**

Run:

```powershell
Get-ChildItem docs/reference/phase1-character-agent
Get-ChildItem docs/reference/phase1-event-bus
```

Expected: the local demo now contains the eight intended Phase 1-ready reference files.

## Task 2: Define The Local Character Execution Contract

**Files:**
- Create: `scripts/character/CharacterDriverSpec.gd`
- Create: `docs/character-execution-notes.md`
- Modify: `scripts/character/CharacterReplica.gd`

- [ ] **Step 1: Write the failing contract test as a static checklist**

Create `docs/character-execution-notes.md` with an initial checklist that the upgraded execution shell must satisfy:

```md
# Character Execution Notes

Required shell capabilities:

- explicit driver mode: `ai` / `player`
- explicit move target API
- explicit look target API
- explicit action dispatch API
- no hard dependency on patrol-only motion for all roles
- same shell usable by A, B, and C
```

Expected: the file states the exact contract this upgrade must satisfy.

- [ ] **Step 2: Read the current execution shell before editing it**

Run:

```powershell
Get-Content scripts/character/CharacterReplica.gd
```

Expected: current patrol-driven shell logic is visible and can be compared to the target contract.

- [ ] **Step 3: Create a small driver-mode spec resource script**

Write `scripts/character/CharacterDriverSpec.gd` as:

```gdscript
extends Resource

class_name CharacterDriverSpec

enum DriverMode {
	AI,
	PLAYER,
}

@export var driver_mode: DriverMode = DriverMode.AI
@export var move_target: Vector3 = Vector3.ZERO
@export var has_move_target := false
@export var look_target: Vector3 = Vector3.ZERO
@export var has_look_target := false
@export var requested_action := ""
```

Expected: a minimal explicit runtime driver spec exists for the shared role shell.

- [ ] **Step 4: Add explicit driver-mode and target fields to CharacterReplica**

Add to `scripts/character/CharacterReplica.gd`:

```gdscript
enum DriverMode {
	AI,
	PLAYER,
}

@export var driver_mode := DriverMode.AI

var external_move_target := Vector3.ZERO
var has_external_move_target := false
var external_look_target := Vector3.ZERO
var has_external_look_target := false
var requested_action := ""
```

Expected: the shell no longer assumes patrol-only logic is the only motion source.

- [ ] **Step 5: Add explicit shell entrypoints**

Add these methods to `scripts/character/CharacterReplica.gd`:

```gdscript
func set_driver_mode(next_mode: int) -> void:
	driver_mode = next_mode

func set_move_target(target: Vector3) -> void:
	external_move_target = target
	has_external_move_target = true

func clear_move_target() -> void:
	has_external_move_target = false

func set_look_target(target: Vector3) -> void:
	external_look_target = target
	has_external_look_target = true

func clear_look_target() -> void:
	has_external_look_target = false

func perform_action(action_name: String) -> void:
	requested_action = action_name
```

Expected: the role shell now exposes explicit control entrypoints for future AI and player driving.

- [ ] **Step 6: Make movement logic prefer external targets before patrol**

Reshape `_update_patrol(delta)` into a more general movement path:

```gdscript
func _update_patrol(delta: float) -> void:
	if hold_timer > 0.0:
		current_velocity = current_velocity.move_toward(Vector3.ZERO, move_decel * delta)
		return

	if has_external_move_target:
		_move_toward_target(external_move_target, delta)
		return

	if not patrol_enabled or patrol_points.size() <= 1:
		current_velocity = current_velocity.move_toward(Vector3.ZERO, move_decel * delta)
		return

	var target: Vector3 = home_position + patrol_points[patrol_index]
	_move_toward_patrol_target(target, delta)
```

Also split helper methods:

```gdscript
func _move_toward_target(target: Vector3, delta: float) -> void:
	var to_target := target - global_position
	to_target.y = 0.0
	if to_target.length() < 0.05:
		clear_move_target()
		current_velocity = current_velocity.move_toward(Vector3.ZERO, move_decel * delta)
		locomotion_state = LocomotionState.IDLE
		return

	var move_direction := to_target.normalized()
	current_velocity = current_velocity.move_toward(move_direction * move_speed, move_accel * delta)
	var step := current_velocity * delta
	if step.length() > to_target.length():
		step = move_direction * to_target.length()

	global_position += step
	current_look_target = global_position + move_direction
	has_look_target = true
	locomotion_state = LocomotionState.WALK
	posture_target = Vector3.ZERO

func _move_toward_patrol_target(target: Vector3, delta: float) -> void:
	var to_target := target - global_position
	to_target.y = 0.0
	if to_target.length() < 0.05:
		patrol_index = (patrol_index + 1) % patrol_points.size()
		locomotion_state = LocomotionState.IDLE
		hold_timer = max(hold_timer, patrol_wait_duration)
		current_velocity = current_velocity.move_toward(Vector3.ZERO, move_decel * delta)
		return

	_move_toward_target(target, delta)
```

Expected: the shell can now be driven toward explicit targets without abandoning patrol support.

- [ ] **Step 7: Make rotation logic prefer external look targets**

Update `_update_rotation(delta)` in `scripts/character/CharacterReplica.gd`:

```gdscript
func _update_rotation(delta: float) -> void:
	if has_external_look_target:
		current_look_target = external_look_target
		has_look_target = true

	if not has_look_target:
		return

	var look_target: Vector3 = Vector3(current_look_target.x, global_position.y, current_look_target.z)
	var desired_basis: Basis = Basis.looking_at((look_target - global_position).normalized(), Vector3.UP)
	global_basis = global_basis.slerp(desired_basis, clamp(turn_speed * delta, 0.0, 1.0))
```

Expected: the shell can now be explicitly steered visually by future AI/player intent layers.

- [ ] **Step 8: Re-read the shell and confirm the new contract exists**

Run:

```powershell
Select-String -Path scripts/character/CharacterReplica.gd -Pattern 'set_driver_mode|set_move_target|clear_move_target|set_look_target|clear_look_target|perform_action|has_external_move_target|has_external_look_target'
```

Expected: all explicit role-shell entrypoints are present.

## Task 3: Make Room For C As The First Player-Driven In-World Role

**Files:**
- Modify: `scripts/player/Phase0PlayerBridge.gd`
- Modify: `scripts/phase0/MainDemoController.gd`
- Modify: `scenes/phase0/MainDemo.tscn`

- [ ] **Step 1: Define the local handoff rule in the controller notes**

Append to `docs/character-execution-notes.md`:

```md
Player-driven C rule:

- player input should eventually drive character C's active role surface
- player should not permanently bypass the shared role shell
- current demo may keep the existing player character while introducing the C-ready handoff points
```

Expected: the plan explicitly records that player control must converge toward a role shell, not stay a separate forever-path.

- [ ] **Step 2: Add a named placeholder slot for C in MainDemo**

Add a third role instance to `scenes/phase0/MainDemo.tscn`:

```text
[node name="CharacterC" parent="." instance=ExtResource("5_character")]
transform = Transform3D(... south/entry-side placement ...)
actor_id = "char_c"
patrol_enabled = false
```

Use a readable south-side or entry-side placement rather than dropping `C` into the center.

Expected: the scene structurally includes the first player-role shell.

- [ ] **Step 3: Expose CharacterC in MainDemoController**

Add:

```gdscript
@onready var character_c: Node3D = $CharacterC
```

Expected: the scene controller can address the player-role shell explicitly.

- [ ] **Step 4: Extend candidate focus targets to include C-safe future logic**

Keep current interaction targets, but restructure `_pick_focus_target()` so its candidate list is explicit and easy to extend:

```gdscript
func _pick_focus_target() -> Node3D:
	var candidates: Array[Node3D] = [character_a, character_b, interactive_object]
```

Leave the current list intact for now, but add a comment or clear staging that `CharacterC` is not yet part of the targetable NPC list because it represents the player-role shell.

Expected: the controller's relationship model is explicit and future-safe.

- [ ] **Step 5: Add a scene-level note describing the role split**

Append to `docs/sample-scene-setup.md`:

```md
- `CharacterA` and `CharacterB` are the AI-driven in-world roles in the current relationship field.
- `CharacterC` is reserved as the first player-driven in-world role on the same shared role shell.
- The current playable `Player` remains the immediate movement shell until player-to-C role driving is wired more deeply.
```

Expected: the project records the intended A/B/C split instead of leaving it implicit.

## Task 4: Prepare The mixabridge Character Pipeline

**Files:**
- Create: `docs/mixabridge-character-pipeline.md`
- Create: `assets/characters/README.md`
- Verify: `addons/mixabridge/`

- [ ] **Step 1: Read the local asset injection guide and mixabridge entry points**

Run:

```powershell
Get-Content docs/asset-injection-guide.md
Get-Content addons/mixabridge/bone_mapper.gd
Get-Content addons/mixabridge/animation_extractor.gd
```

Expected: the existing asset mount convention and the plugin skeleton/animation capabilities are visible.

- [ ] **Step 2: Create the character asset staging README**

Write `assets/characters/README.md` with content equivalent to:

```md
# Character Asset Staging

Place incoming A/B/C character assets here.

Recommended structure:

- A/
- B/
- C/
- shared_animations/

Preferred source formats:

- `.glb`
- `.gltf`

Pipeline intent:

- all three roles should pass through one shared `mixabridge`-ready skeleton and action pipeline
- A/B/C should not diverge into separate asset conventions
```

Expected: the asset folder communicates the shared role-substrate rule.

- [ ] **Step 3: Write the mixabridge pipeline note**

Create `docs/mixabridge-character-pipeline.md` with content equivalent to:

```md
# mixabridge Character Pipeline

Purpose:

- connect A/B/C to one shared skeleton and animation preparation path

Use mixabridge for:

- skeleton discovery
- bone map generation
- animation scene extraction
- preparing a shared minimal action set

Required first action set:

- idle
- locomotion
- turn/look
- speak
- inspect/guard
- alert/recoil
- hold-ground/observe

Mount rule:

- keep `CharacterReplica` as outer shell
- mount imported role assets under `VisualRoot/AssetMount/.../ImportedModel`
```

Expected: the role/animation strategy is recorded locally.

- [ ] **Step 4: Verify mixabridge documentation readiness**

Run:

```powershell
Get-Content docs/mixabridge-character-pipeline.md
Get-Content assets/characters/README.md
```

Expected: the shared A/B/C pipeline is clearly documented.

## Task 5: Reshape The Scene Into A Relationship Space

**Files:**
- Modify: `scenes/phase0/MainDemo.tscn`
- Modify: `docs/sample-scene-setup.md`
- Create: `docs/phase05-scene-zones.md`

- [ ] **Step 1: Write the zone brief before moving geometry**

Create `docs/phase05-scene-zones.md` with content equivalent to:

```md
# Phase 0.5 Scene Zones

Required zones:

- player intervention entry band
- central relationship focus zone
- A control zone
- B observation zone
- environment reaction zone
```

Expected: scene work is driven by spatial roles, not arbitrary decoration.

- [ ] **Step 2: Reposition the three role anchors by relationship logic**

Update `scenes/phase0/MainDemo.tscn` so that:

- `CharacterA` is nearest the table and key object
- `CharacterB` is offset to a side observation position
- `CharacterC` sits farther south or entry-side

Use concrete transforms that preserve the open field but create a non-symmetric relationship triangle.

Expected: the scene no longer reads as two symmetric demo actors plus empty space.

- [ ] **Step 3: Move the table/object and environment node to support the relationship chain**

Update scene placement so that:

- table and `obj_letter` form the central relationship focus zone
- environment node sits beyond the center line, reading as an outward amplification rather than an unrelated distant marker

Expected: the spatial chain supports `C enters -> A control is disturbed -> environment reaction expands -> B notices`.

- [ ] **Step 4: Add one entry-language structure and one observation-language structure**

Using the current scene file, add low geometry or prop grouping that implies:

- where `C` enters from
- where `B` naturally observes from

Do not create a room maze. Keep the scene semi-open.

Expected: the space becomes narratively legible without losing open traversal.

- [ ] **Step 5: Update the human scene setup document**

Rewrite the relevant parts of `docs/sample-scene-setup.md` so that it explicitly names:

- `A` as controller of the key object
- `B` as observer
- `C` as player-driven intervener
- the five zone structure

Expected: the local runbook matches the Phase 0.5 relationship-space design.

## Task 6: Prepare The homebuilder Scene Pipeline

**Files:**
- Create: `docs/homebuilder-scene-pipeline.md`
- Create: `assets/environment/README.md`
- Create: `assets/props/README.md`
- Verify: `addons/home_builder/`

- [ ] **Step 1: Create the environment staging README**

Write `assets/environment/README.md` with content equivalent to:

```md
# Environment Asset Staging

Use this folder for semi-open relationship-space assets.

Preferred categories:

- ground kits
- low dividers
- railings
- focal furniture
- light fixtures
- environment reaction fixtures
```

Expected: environment staging aligns with the relationship-space goal.

- [ ] **Step 2: Create the props staging README**

Write `assets/props/README.md` with content equivalent to:

```md
# Prop Asset Staging

Use this folder for key relationship props.

Priority props:

- key-object table set
- letter / evidence props
- observation-side furniture
- reaction-side environment props
```

Expected: prop staging aligns with the A/B/C intervention model.

- [ ] **Step 3: Write the homebuilder pipeline note**

Create `docs/homebuilder-scene-pipeline.md` with content equivalent to:

```md
# homebuilder Scene Pipeline

Purpose:

- turn the open greybox field into a semi-open relationship space

Do:

- preserve one open traversable scene
- create an intervention entry band
- create a central control/focus zone
- create a side observation zone
- create an outward environment reaction zone

Do not:

- fragment the space into many small demo rooms
- bury the key object inside maze-like geometry
```

Expected: scene-construction logic is documented before asset iteration begins.

- [ ] **Step 4: Verify scene-pipeline docs**

Run:

```powershell
Get-Content docs/homebuilder-scene-pipeline.md
Get-Content assets/environment/README.md
Get-Content assets/props/README.md
```

Expected: local docs clearly define how `homebuilder` should be used in this project.

## Task 7: Regression-Proof The Existing Phase 0 Loop

**Files:**
- Verify: `scenes/phase0/MainDemo.tscn`
- Verify: `scripts/character/CharacterReplica.gd`
- Verify: `scripts/phase0/MainDemoController.gd`
- Verify: `backend/tests/test_ws_protocol.py`
- Verify: `backend/tests/test_session_runtime.py`
- Verify: `backend/tests/test_character_service.py`
- Verify: `backend/tests/test_esm_service.py`
- Verify: `backend/tests/test_siming_service.py`
- Verify: `backend/tests/test_demo_script.py`

- [ ] **Step 1: Confirm the role split is visible in scene/docs**

Run:

```powershell
Select-String -Path scenes/phase0/MainDemo.tscn,docs/sample-scene-setup.md -Pattern 'CharacterA|CharacterB|CharacterC|player-driven|AI-driven|intervener|observer|control'
```

Expected: the scene and docs encode the A/B/C relationship model explicitly.

- [ ] **Step 2: Confirm the execution shell exposes the new control surface**

Run:

```powershell
Select-String -Path scripts/character/CharacterReplica.gd -Pattern 'set_driver_mode|set_move_target|clear_move_target|set_look_target|clear_look_target|perform_action'
```

Expected: the shared shell has explicit driver/control entrypoints.

- [ ] **Step 3: Run backend regression**

Run:

```powershell
python -m pytest -v
```

Workdir:

```text
backend
```

Expected: existing backend tests still pass.

- [ ] **Step 4: Run Godot scene load verification**

Run:

```powershell
& 'E:\下载\Godot_v4.6.3-stable_win64.exe\Godot_v4.6.3-stable_win64_console.exe' --path 'D:\Users\User\Documents\paralls-phase-0-demo' --scene 'res://scenes/phase0/MainDemo.tscn' --quit-after 200 --verbose --render-thread safe
```

Expected: scene loads without script parse errors.

- [ ] **Step 5: Run the autotest loop again**

Run:

```powershell
$env:PHASE0_AUTOTEST='1'
$env:PHASE0_AUTOTEST_SCREENSHOT='D:\Users\User\Documents\paralls-phase-0-demo\.harness\logs\phase05-upgrade-autotest.png'
& 'E:\下载\Godot_v4.6.3-stable_win64.exe\Godot_v4.6.3-stable_win64_console.exe' --path 'D:\Users\User\Documents\paralls-phase-0-demo' --scene 'res://scenes/phase0/MainDemo.tscn' --quit-after 400 --verbose --render-thread safe
```

Expected: the current Phase 0 loop still runs to dialogue, interaction, environment reaction, Siming response, and screenshot save.

## Self-Review

### Spec coverage

- Shared A/B/C role substrate: covered in Tasks 2 and 3.
- AI vs player driving split: covered in Tasks 2 and 3.
- mixabridge-heavy role: covered in Task 4.
- homebuilder-heavy scene upgrade: covered in Tasks 5 and 6.
- A controls, B observes, C intervenes: covered in Tasks 3 and 5.
- Reuse of main-project materials: covered in Task 1.
- Preserve Phase 0 loop: covered in Task 7.

No spec gaps found.

### Placeholder scan

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- All tasks include exact file paths and explicit commands or content blocks.

### Type consistency

- `driver_mode`, `set_move_target`, `set_look_target`, and `perform_action` are used consistently across shell and verification tasks.
- A/B/C split is described consistently as AI / AI / player-driven.
