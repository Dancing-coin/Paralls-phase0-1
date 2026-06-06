# Player Root Motion Locomotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the player-controlled knight locomotion stack so `CharacterC` has correct, fast, believable root-motion-driven movement with gait cycling, crouch locomotion, two jump variants, and visible UI state.

**Architecture:** Keep the current hidden `Player` shell plus visible `CharacterC` shell split. Move all grounded horizontal locomotion authority to calibrated root motion extracted from knight clips, while the hidden `Player` keeps collision, gravity, jump shell, and camera ownership. Introduce an explicit locomotion intent layer so keyboard input maps to `stance`, `gait`, and `jump_type` instead of directly mutating clip names.

**Tech Stack:** Godot 4.x, GDScript, existing `JehenoThirdPersonController`, current knight GLB animation set, Python verification audit, pytest.

---

## File Structure

### Primary runtime files

- Modify: `scripts/player/Phase0PlayerBridge.gd`
  - Read keyboard locomotion intent
  - Manage gait cycling, crouch toggle, and jump modifier state
  - Feed normalized locomotion intent into `CharacterC`
  - Push corrected root motion back into hidden `Player`
- Modify: `scripts/character/CharacterReplica.gd`
  - Hold player locomotion intent state
  - Select execution state for standing, crouch, and jump variants
  - Consume calibrated root motion from `KnightRoleSkin`
  - Publish locomotion status to UI/debug display
- Modify: `scripts/character/KnightRoleSkin.gd`
  - Add locomotion clip calibration metadata
  - Normalize root motion forward axis
  - Support gait-specific speed and distance tuning
  - Expose current clip and clip-state data
- Modify: `scripts/phase0/MainDemoController.gd`
  - Keep autotest aligned with new movement and state display
  - Ensure existing interaction and failed-interaction verification still works
- Modify: `PLAYER_CONTROLS.md`
  - Update keyboard contract and locomotion mode explanation

### Supporting runtime files

- Modify: `scripts/ui/DebugOverlay.gd`
  - Show stance, gait, jump mode, current clip, and root motion state
- Modify: `addons/JehenoThirdPersonController/PlayerCharacter/StateMachine/player_character_script.gd`
  - Keep bridge hooks stable for pre/post `move_and_slide()` integration

### Verification files

- Modify: `backend/tests/test_verification_audit.py`
  - Lock locomotion verification language around new gait/crouch/jump observability
- Modify: `backend/app/verification_audit.py`
  - Evaluate locomotion state evidence from autotest logs
- Modify: `scripts/verification/verify_phase0.py`
  - Reuse current Phase 0 verification path and capture updated logs

### Optional small split if file pressure rises

- Create: `scripts/player/PlayerLocomotionState.gd`
  - Only if `Phase0PlayerBridge.gd` becomes too large while adding stance/gait/jump bookkeeping

---

## Task 1: Lock The New Locomotion Contract In Verification

**Files:**
- Modify: `backend/tests/test_verification_audit.py`
- Modify: `backend/app/verification_audit.py`

- [ ] **Step 1: Write the failing audit test for gait and crouch observability**

```python
def test_phase0_audit_requires_locomotion_state_evidence() -> None:
    report = evaluate_phase0_audit(
        pytest_passed=True,
        scene_load_ok=True,
        main_log="""
        [LocalPresentationBus] backend_connected:ws://127.0.0.1:8010/ws
        [LocalPresentationBus] phase0_dialogue_target:char_a
        [LocalPresentationBus] dialogue_applied:char_a
        [LocalPresentationBus] object_state:obj_letter:object interaction accepted
        [LocalPresentationBus] environment_state:alerted
        [LocalPresentationBus] attention_applied:char_b
        [LocalPresentationBus] voice_stub_played
        [LocalPresentationBus] player_root_motion_step:char_c
        [LocalPresentationBus] patrol_root_motion_step:char_a
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-main.png:0
        """,
        focus_log="""
        [LocalPresentationBus] phase0_focus_autotest_begin
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-focus.png:0
        """,
        main_screenshot_exists=True,
        focus_screenshot_exists=True,
        interaction_source="world_result = esm_service.resolve_interaction(event, is_in_range=False)",
        voice_controller_source="func play_stub_voice(_payload: Dictionary) -> void:\n    _bus_log(\"voice_stub_played\")",
        player_bridge_source="func set_gait_mode(next_mode: String) -> void:\n    locomotion_gait = next_mode",
        character_replica_source="func get_locomotion_status() -> Dictionary:\n    return {\"gait\": gait, \"stance\": stance, \"jump_type\": jump_type}",
    )

    results = _index_by_id(report["results"])

    assert results["locomotion_state_ui"]["status"] == "missing"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_verification_audit.py::test_phase0_audit_requires_locomotion_state_evidence -q`

Expected: FAIL because `evaluate_phase0_audit()` does not yet emit `locomotion_state_ui`.

- [ ] **Step 3: Implement minimal audit logic**

```python
locomotion_ui_ok = (
    "locomotion_state:" in main_log
    and "gait=" in main_log
    and "stance=" in main_log
    and "jump=" in main_log
)
results.append(
    _result(
        "locomotion_state_ui",
        "Locomotion state is visible in UI/debug output",
        "proved" if locomotion_ui_ok else "missing",
        ["locomotion_state"] if locomotion_ui_ok else [],
    )
)
```

- [ ] **Step 4: Run the audit test to verify it passes**

Run: `python -m pytest tests/test_verification_audit.py::test_phase0_audit_requires_locomotion_state_evidence -q`

Expected: PASS

- [ ] **Step 5: Run the full audit test file**

Run: `python -m pytest tests/test_verification_audit.py -q`

Expected: PASS with no regressions in existing audit checks

- [ ] **Step 6: Commit**

```bash
git add backend/tests/test_verification_audit.py backend/app/verification_audit.py
git commit -m "Freeze locomotion verification before the player movement rewrite"
```

---

## Task 2: Add Explicit Player Locomotion Intent State

**Files:**
- Modify: `scripts/player/Phase0PlayerBridge.gd`
- Modify: `PLAYER_CONTROLS.md`

- [ ] **Step 1: Write the failing verification audit test for gait cycling evidence**

```python
def test_phase0_audit_accepts_gait_cycle_evidence() -> None:
    report = evaluate_phase0_audit(
        pytest_passed=True,
        scene_load_ok=True,
        main_log="""
        [LocalPresentationBus] locomotion_state:stance=stand gait=brisk_walk jump=none clip=walk_guard rm=active
        [LocalPresentationBus] player_root_motion_step:char_c
        [LocalPresentationBus] patrol_root_motion_step:char_a
        [LocalPresentationBus] voice_stub_played
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-main.png:0
        [LocalPresentationBus] backend_connected:ws://127.0.0.1:8010/ws
        [LocalPresentationBus] dialogue_applied:char_a
        [LocalPresentationBus] object_state:obj_letter:object interaction accepted
        [LocalPresentationBus] environment_state:alerted
        [LocalPresentationBus] attention_applied:char_b
        [LocalPresentationBus] constraint_state_result:distance
        """,
        focus_log="[LocalPresentationBus] phase0_screenshot_saved:D:\\demo-focus.png:0",
        main_screenshot_exists=True,
        focus_screenshot_exists=True,
        interaction_source="world_result = esm_service.resolve_interaction(event, is_in_range=False)",
        voice_controller_source="func play_stub_voice(_payload: Dictionary) -> void:\n    _bus_log(\"voice_stub_played\")",
        player_bridge_source="var locomotion_gait := \"walk\"\nfunc cycle_gait_mode() -> void:\n    pass",
        character_replica_source="func get_locomotion_status() -> Dictionary:\n    return {\"gait\": gait}",
    )
    assert _index_by_id(report["results"])["locomotion_state_ui"]["status"] == "proved"
```

- [ ] **Step 2: Run test to verify it fails for the intended reason**

Run: `python -m pytest tests/test_verification_audit.py::test_phase0_audit_accepts_gait_cycle_evidence -q`

Expected: FAIL before bridge/runtime code exists for this exact state contract

- [ ] **Step 3: Add locomotion intent fields in `Phase0PlayerBridge.gd`**

```gdscript
enum GaitMode {
    AMBLE,
    WALK,
    BRISK_WALK,
}

enum StanceMode {
    STAND,
    CROUCH,
}

var locomotion_gait_mode: int = GaitMode.WALK
var locomotion_stance_mode: int = StanceMode.STAND
var jump_modifier_single_leg := false
```

- [ ] **Step 4: Add keyboard handling for `Z` and `C`**

```gdscript
@export var gait_cycle_action := "phase0_cycle_walk_mode"
@export var crouch_toggle_action := "phase0_toggle_crouch"

if event.is_action_pressed(gait_cycle_action):
    _cycle_gait_mode()
if event.is_action_pressed(crouch_toggle_action):
    _toggle_crouch_mode()
```

- [ ] **Step 5: Add minimal helper methods**

```gdscript
func _cycle_gait_mode() -> void:
    if locomotion_stance_mode == StanceMode.CROUCH:
        return
    locomotion_gait_mode = (locomotion_gait_mode + 1) % 3

func _toggle_crouch_mode() -> void:
    locomotion_stance_mode = StanceMode.CROUCH if locomotion_stance_mode == StanceMode.STAND else StanceMode.STAND
```

- [ ] **Step 6: Expose a structured locomotion intent packet to `CharacterC`**

```gdscript
func _build_locomotion_intent(move_direction: Vector3) -> Dictionary:
    return {
        "stance": "crouch" if locomotion_stance_mode == StanceMode.CROUCH else "stand",
        "gait": _resolve_gait_name(move_direction),
        "jump_type": _resolve_jump_type(),
        "move_direction": move_direction,
    }
```

- [ ] **Step 7: Update `PLAYER_CONTROLS.md`**

```md
- `Z`: cycle `amble -> walk -> brisk walk`
- `C`: toggle crouch
- `Shift + WASD`: run while standing
- `Shift + WASD + Space`: single-leg jump
- `WASD + Space`: two-foot jump
```

- [ ] **Step 8: Run verification audit tests again**

Run: `python -m pytest tests/test_verification_audit.py -q`

Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add scripts/player/Phase0PlayerBridge.gd PLAYER_CONTROLS.md
git commit -m "Introduce explicit locomotion intent for the knight player controls"
```

---

## Task 3: Calibrate Knight Root Motion Direction, Distance, And Gait Bands

**Files:**
- Modify: `scripts/character/KnightRoleSkin.gd`
- Modify: `scripts/character/CharacterReplica.gd`

- [ ] **Step 1: Write the failing root-motion calibration audit test**

```python
def test_phase0_audit_requires_root_motion_and_locomotion_ui_together() -> None:
    report = evaluate_phase0_audit(
        pytest_passed=True,
        scene_load_ok=True,
        main_log="""
        [LocalPresentationBus] backend_connected:ws://127.0.0.1:8010/ws
        [LocalPresentationBus] dialogue_applied:char_a
        [LocalPresentationBus] object_state:obj_letter:object interaction accepted
        [LocalPresentationBus] environment_state:alerted
        [LocalPresentationBus] attention_applied:char_b
        [LocalPresentationBus] voice_stub_played
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-main.png:0
        """,
        focus_log="[LocalPresentationBus] phase0_screenshot_saved:D:\\demo-focus.png:0",
        main_screenshot_exists=True,
        focus_screenshot_exists=True,
        interaction_source="world_result = esm_service.resolve_interaction(event, is_in_range=False)",
        voice_controller_source="func play_stub_voice(_payload: Dictionary) -> void:\n    _bus_log(\"voice_stub_played\")",
        player_bridge_source="func before_player_shell_move(delta: float) -> void:\n    _apply_player_root_motion_drive(delta)",
        character_replica_source="func consume_player_root_motion_request(delta: float) -> Vector3:\n    return Vector3.ZERO",
    )
    results = _index_by_id(report["results"])
    assert results["player_root_motion_chain"]["status"] == "missing"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_verification_audit.py::test_phase0_audit_requires_root_motion_and_locomotion_ui_together -q`

Expected: FAIL because locomotion runtime evidence is not yet present

- [ ] **Step 3: Add clip calibration metadata in `KnightRoleSkin.gd`**

```gdscript
const ROOT_MOTION_PROFILE := {
    "walk_guard": {
        "forward_axis_sign": -1.0,
        "distance_scale": 1.0,
        "speed_scale": 1.0,
    },
    "run_charge": {
        "forward_axis_sign": -1.0,
        "distance_scale": 1.0,
        "speed_scale": 1.0,
    },
}
```

- [ ] **Step 4: Add gait-aware playback helpers**

```gdscript
func set_locomotion_profile(state_name: String, gait_name: String) -> void:
    set_state(state_name)
    var clip_name := current_clip
    var speed_scale := _resolve_gait_speed_scale(clip_name, gait_name)
    animation_player.speed_scale = speed_scale
```

- [ ] **Step 5: Normalize root motion direction in `CharacterReplica.gd`**

```gdscript
var corrected_forward := move_direction.normalized()
var root_motion_step: Vector3 = _consume_role_root_motion_world_delta()
var projected := root_motion_step.dot(corrected_forward)
var motion_amount := abs(projected)
if motion_amount <= 0.0001:
    motion_amount = root_motion_step.length()
var requested_step: Vector3 = corrected_forward * motion_amount
```

- [ ] **Step 6: Introduce standing gait bands in `CharacterReplica.gd`**

```gdscript
match player_gait:
    "amble":
        _set_role_asset_locomotion("walk", "amble")
    "walk":
        _set_role_asset_locomotion("walk", "walk")
    "brisk_walk":
        _set_role_asset_locomotion("walk", "brisk_walk")
    "run":
        _set_role_asset_locomotion("run", "run")
```

- [ ] **Step 7: Add locomotion state getter for UI and logging**

```gdscript
func get_locomotion_status() -> Dictionary:
    return {
        "stance": player_stance,
        "gait": player_gait,
        "jump_type": player_jump_type,
        "clip": current_clip,
        "root_motion_active": last_root_motion_world_delta.length() > 0.0001,
    }
```

- [ ] **Step 8: Emit runtime locomotion evidence**

```gdscript
_bus_log(
    "locomotion_state:stance=%s gait=%s jump=%s clip=%s rm=%s" % [
        player_stance,
        player_gait,
        player_jump_type,
        current_clip,
        "active" if last_root_motion_world_delta.length() > 0.0001 else "inactive",
    ]
)
```

- [ ] **Step 9: Run audit tests**

Run: `python -m pytest tests/test_verification_audit.py -q`

Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add scripts/character/KnightRoleSkin.gd scripts/character/CharacterReplica.gd
git commit -m "Correct knight root motion direction and standing gait calibration"
```

---

## Task 4: Implement Crouch Toggle, Crouch Movement, And UI Status

**Files:**
- Modify: `scripts/character/CharacterReplica.gd`
- Modify: `scripts/ui/DebugOverlay.gd`

- [ ] **Step 1: Write the failing audit test for locomotion UI**

```python
def test_phase0_audit_proves_locomotion_state_ui() -> None:
    report = evaluate_phase0_audit(
        pytest_passed=True,
        scene_load_ok=True,
        main_log="""
        [LocalPresentationBus] backend_connected:ws://127.0.0.1:8010/ws
        [LocalPresentationBus] locomotion_state:stance=crouch gait=walk jump=none clip=walk_guard rm=active
        [LocalPresentationBus] player_root_motion_step:char_c
        [LocalPresentationBus] patrol_root_motion_step:char_a
        [LocalPresentationBus] dialogue_applied:char_a
        [LocalPresentationBus] object_state:obj_letter:object interaction accepted
        [LocalPresentationBus] environment_state:alerted
        [LocalPresentationBus] attention_applied:char_b
        [LocalPresentationBus] voice_stub_played
        [LocalPresentationBus] constraint_state_result:distance
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-main.png:0
        """,
        focus_log="[LocalPresentationBus] phase0_screenshot_saved:D:\\demo-focus.png:0",
        main_screenshot_exists=True,
        focus_screenshot_exists=True,
        interaction_source="world_result = esm_service.resolve_interaction(event, is_in_range=False)",
        voice_controller_source="func play_stub_voice(_payload: Dictionary) -> void:\n    _bus_log(\"voice_stub_played\")",
        player_bridge_source="func _toggle_crouch_mode() -> void:\n    pass",
        character_replica_source="func get_locomotion_status() -> Dictionary:\n    return {\"stance\": \"crouch\"}",
    )
    assert _index_by_id(report["results"])["locomotion_state_ui"]["status"] == "proved"
```

- [ ] **Step 2: Run test to verify it fails first if UI log format is absent**

Run: `python -m pytest tests/test_verification_audit.py::test_phase0_audit_proves_locomotion_state_ui -q`

Expected: FAIL until runtime/UI output matches

- [ ] **Step 3: Add crouch state in `CharacterReplica.gd`**

```gdscript
var player_stance := "stand"

func set_player_stance(next_stance: String) -> void:
    player_stance = next_stance
    if player_stance == "crouch":
        posture_target = Vector3(0.0, -0.22, 0.0)
    else:
        posture_target = Vector3.ZERO
```

- [ ] **Step 4: Add crouch locomotion behavior**

```gdscript
if player_stance == "crouch":
    if move_direction.length() > 0.001:
        _set_role_asset_locomotion("walk", "crouch_walk")
    else:
        _set_role_asset_state_if_free(idle_role_state)
```

- [ ] **Step 5: Add UI/debug overlay state line**

```gdscript
func set_locomotion_status(status: Dictionary) -> void:
    var line := "Locomotion | Stance=%s | Gait=%s | Jump=%s | Clip=%s | RM=%s" % [
        status.get("stance", ""),
        status.get("gait", ""),
        status.get("jump_type", ""),
        status.get("clip", ""),
        status.get("root_motion_active", false),
    ]
    _append_or_replace_line("locomotion", line)
```

- [ ] **Step 6: Wire status publishing from `CharacterReplica` to UI**

```gdscript
var bus := _get_bus()
if bus and bus.has_method("log_debug"):
    bus.log_debug("locomotion_state:stance=%s gait=%s jump=%s clip=%s rm=%s" % [...])
```

- [ ] **Step 7: Run audit tests**

Run: `python -m pytest tests/test_verification_audit.py -q`

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add scripts/character/CharacterReplica.gd scripts/ui/DebugOverlay.gd
git commit -m "Add crouch locomotion and visible locomotion status output"
```

---

## Task 5: Implement Two Jump Variants On The Current Knight Asset

**Files:**
- Modify: `scripts/player/Phase0PlayerBridge.gd`
- Modify: `scripts/character/CharacterReplica.gd`
- Modify: `addons/JehenoThirdPersonController/PlayerCharacter/StateMachine/player_character_script.gd`

- [ ] **Step 1: Write the failing audit test for jump mode UI evidence**

```python
def test_phase0_audit_accepts_single_leg_jump_ui() -> None:
    report = evaluate_phase0_audit(
        pytest_passed=True,
        scene_load_ok=True,
        main_log="""
        [LocalPresentationBus] locomotion_state:stance=stand gait=run jump=single_leg clip=jump_command rm=active
        [LocalPresentationBus] backend_connected:ws://127.0.0.1:8010/ws
        [LocalPresentationBus] dialogue_applied:char_a
        [LocalPresentationBus] object_state:obj_letter:object interaction accepted
        [LocalPresentationBus] environment_state:alerted
        [LocalPresentationBus] attention_applied:char_b
        [LocalPresentationBus] voice_stub_played
        [LocalPresentationBus] player_root_motion_step:char_c
        [LocalPresentationBus] patrol_root_motion_step:char_a
        [LocalPresentationBus] constraint_state_result:distance
        [LocalPresentationBus] phase0_screenshot_saved:D:\\demo-main.png:0
        """,
        focus_log="[LocalPresentationBus] phase0_screenshot_saved:D:\\demo-focus.png:0",
        main_screenshot_exists=True,
        focus_screenshot_exists=True,
        interaction_source="world_result = esm_service.resolve_interaction(event, is_in_range=False)",
        voice_controller_source="func play_stub_voice(_payload: Dictionary) -> void:\n    _bus_log(\"voice_stub_played\")",
        player_bridge_source="func _resolve_jump_type() -> String:\n    return \"single_leg\"",
        character_replica_source="func get_locomotion_status() -> Dictionary:\n    return {\"jump_type\": \"single_leg\"}",
    )
    assert _index_by_id(report["results"])["locomotion_state_ui"]["status"] == "proved"
```

- [ ] **Step 2: Run test to verify it fails before implementation if jump status is absent**

Run: `python -m pytest tests/test_verification_audit.py::test_phase0_audit_accepts_single_leg_jump_ui -q`

Expected: FAIL until jump status is emitted at runtime

- [ ] **Step 3: Add jump intent resolution in `Phase0PlayerBridge.gd`**

```gdscript
func _resolve_jump_type() -> String:
    if not Input.is_action_pressed(player.jump_action):
        return "none"
    if forced_run_state or Input.is_action_pressed(player.run_action):
        return "single_leg"
    return "two_foot"
```

- [ ] **Step 4: Pass jump intent into `CharacterC`**

```gdscript
character_c.begin_player_control_frame(
    player.global_position,
    move_direction,
    look_target,
    player.is_on_floor(),
    wants_run,
    _resolve_jump_type()
)
```

- [ ] **Step 5: Add jump execution branching in `CharacterReplica.gd`**

```gdscript
if player_jump_type == "single_leg":
    _trigger_role_state("jump", 0.22)
    player_shell_velocity *= 1.08
elif player_jump_type == "two_foot":
    _trigger_role_state("jump", 0.32)
```

- [ ] **Step 6: Keep `Player` shell hooks compatible**

```gdscript
func _physics_process(delta: float):
    modify_physics_properties()
    if external_motion_driver and external_motion_driver.has_method("before_player_shell_move"):
        external_motion_driver.before_player_shell_move(delta)
    move_and_slide()
    if external_motion_driver and external_motion_driver.has_method("after_player_shell_move"):
        external_motion_driver.after_player_shell_move(delta)
```

- [ ] **Step 7: Run audit tests**

Run: `python -m pytest tests/test_verification_audit.py -q`

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add scripts/player/Phase0PlayerBridge.gd scripts/character/CharacterReplica.gd addons/JehenoThirdPersonController/PlayerCharacter/StateMachine/player_character_script.gd
git commit -m "Differentiate two-foot and single-leg jump intent for the knight player shell"
```

---

## Task 6: Run Full Verification And Update Runtime Docs

**Files:**
- Modify: `scripts/verification/verify_phase0.py`
- Modify: `PLAYER_CONTROLS.md`
- Modify: `docs/demo-script.md`

- [ ] **Step 1: Update verification file comments or artifact expectations if needed**

```python
report = evaluate_phase0_audit(
    ...,
    player_bridge_source=read_text(project_root / "scripts" / "player" / "Phase0PlayerBridge.gd"),
    character_replica_source=read_text(project_root / "scripts" / "character" / "CharacterReplica.gd"),
)
```

- [ ] **Step 2: Update control documentation to reflect the final keyboard contract**

```md
- `Z`: cycle `Amble -> Walk -> Brisk Walk`
- `C`: crouch / stand
- `Shift + WASD`: run
- `WASD + Space`: two-foot jump
- `Shift + WASD + Space`: single-leg jump
- on-screen locomotion state now reports stance, gait, jump, clip, and root motion state
```

- [ ] **Step 3: Update demo script with the locomotion check sequence**

```md
1. Press `WASD` and confirm forward-facing walk matches input direction
2. Tap `Z` three times and confirm amble / walk / brisk walk visibly differ
3. Hold `Shift + WASD` and confirm run speed clearly exceeds brisk walk
4. Press `C`, confirm crouch, move slowly with `WASD`, then press `C` again to stand
5. Trigger `WASD + Space` and `Shift + WASD + Space` to compare jump feel
```

- [ ] **Step 4: Run backend verification tests**

Run: `python -m pytest tests/test_verification_audit.py -q`

Expected: PASS

- [ ] **Step 5: Run full Phase 0 verification**

Run: `python scripts/verification/verify_phase0.py`

Expected:

```text
overall_strict_phase0_passed=True
player_root_motion_chain=proved
npc_root_motion_patrol=proved
locomotion_state_ui=proved
```

- [ ] **Step 6: Commit**

```bash
git add scripts/verification/verify_phase0.py PLAYER_CONTROLS.md docs/demo-script.md
git commit -m "Document and verify the new root-motion keyboard locomotion flow"
```

---

## Self-Review

### Spec Coverage

- root motion direction correction: covered in Task 3
- step amplitude and speed normalization: covered in Task 3
- gait cycling with `Z`: covered in Task 2 and Task 3
- crouch toggle and crouch locomotion: covered in Task 4
- two jump variants: covered in Task 5
- UI locomotion state display: covered in Task 4
- verification and docs: covered in Task 6

### Placeholder Scan

- no `TBD`
- no `TODO`
- no “similar to above” indirections
- each runtime task names exact files and commands

### Type Consistency

- `stance`, `gait`, and `jump_type` remain the canonical locomotion terms throughout
- `player_root_motion_chain`, `npc_root_motion_patrol`, and `locomotion_state_ui` stay consistent with audit naming
- `Phase0PlayerBridge -> CharacterReplica -> KnightRoleSkin` remains the root motion flow in every task
