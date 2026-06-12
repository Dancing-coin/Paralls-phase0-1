# Character Actor Control And Locomotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the shared Character Actor control/motor/locomotion substrate so player control follows the locked camera/body model and presentation follows motor-owned motion state.

**Architecture:** Normalize human input into a Godot-local `CharacterIntentFrame`, route that through a motor-owned displacement path, publish `CharacterMotionState`, and make `KnightRoleSkin` consume motion/presentation parameters instead of acting as the movement authority. Preserve root-motion diagnostics while freezing physics as the displacement owner.

**Tech Stack:** Godot scenes and GDScript, existing player bridge/controller scripts, `KnightRoleSkin`, static pytest audits for GDScript/scene contracts, harness verification.

---

### Task 1: Introduce A Motor-Owned Actor Control Skeleton

**Files:**
- Create: `scripts/character/CharacterMotor.gd`
- Modify: `scenes/phase0/CharacterBase.tscn`
- Create: `backend/tests/test_character_motor_static_contract.py`

- [ ] **Step 1: Write the failing static motor contract tests**

Add tests that lock the intended scene/script ownership:

```python
assert 'class_name CharacterMotor' in motor_source
assert 'move_and_slide()' in motor_source
assert 'CharacterMotor.gd' in character_base_scene
```

- [ ] **Step 2: Run the static tests to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_character_motor_static_contract.py
```

Expected before implementation: fail because the dedicated motor script does not yet exist.

- [ ] **Step 3: Create the motor script with the ownership boundary**

Start with the minimal skeleton:

```gdscript
class_name CharacterMotor
extends Node

func apply_intent_frame(body: CharacterBody3D, frame: Dictionary, delta: float) -> Dictionary:
    body.move_and_slide()
    return {}
```

Attach the new motor node/script in `CharacterBase.tscn`.

- [ ] **Step 4: Re-run the static tests**

Run:

```powershell
python -m pytest -q backend\tests\test_character_motor_static_contract.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/character/CharacterMotor.gd scenes/phase0/CharacterBase.tscn backend/tests/test_character_motor_static_contract.py
git commit -m "Introduce a motor-owned Character Actor control skeleton"
```

### Task 2: Normalize Human Input Into Intent Frames

**Files:**
- Modify: `scripts/player/PlayerController.gd`
- Modify: `scripts/player/Phase0PlayerBridge.gd`
- Modify: `scripts/player/PlayerShell.gd`
- Create: `backend/tests/test_player_control_static_contract.py`

- [ ] **Step 1: Write the failing control normalization tests**

Add static assertions that the player path now speaks in normalized movement/facing terms:

```python
assert "move_local" in player_controller_source
assert "desired_facing_yaw" in phase0_bridge_source
assert "CharacterMotionState" in player_shell_source or "motion_state" in player_shell_source
```

- [ ] **Step 2: Run the static tests to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_player_control_static_contract.py
```

Expected before implementation: fail because the current player path still uses older bridge-specific semantics.

- [ ] **Step 3: Refactor player input into a normalized frame**

Target shape inside the player path:

```gdscript
var intent_frame := {
    "controller_source": "human",
    "move_local": Vector2(input_x, input_y),
    "desired_facing_yaw": facing_yaw,
    "gait": current_gait,
    "action": current_action,
}
```

- [ ] **Step 4: Keep mouse/body coupling locked**

Do not reintroduce a free orbit or hybrid controller. Preserve:

```text
mouse X -> actor/body yaw + camera yaw
mouse Y -> camera pitch only
```

- [ ] **Step 5: Re-run the static tests**

Run:

```powershell
python -m pytest -q backend\tests\test_player_control_static_contract.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/player/PlayerController.gd scripts/player/Phase0PlayerBridge.gd scripts/player/PlayerShell.gd backend/tests/test_player_control_static_contract.py
git commit -m "Normalize the player path into Character Actor intent frames"
```

### Task 3: Move Displacement Ownership To `CharacterMotor`

**Files:**
- Modify: `scripts/player/PlayerShell.gd`
- Modify: `scripts/player/Phase0PlayerBridge.gd`
- Modify: `scripts/character/CharacterMotor.gd`
- Create: `backend/tests/test_character_motor_ownership_audit.py`

- [ ] **Step 1: Write the failing ownership audit**

Add checks that `move_and_slide()` and velocity mutation live in the motor path rather than multiple gameplay scripts:

```python
assert player_shell_source.count("move_and_slide(") == 0
assert motor_source.count("move_and_slide(") >= 1
```

- [ ] **Step 2: Run the audit to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_character_motor_ownership_audit.py
```

Expected before implementation: fail because displacement is still owned by the player shell path.

- [ ] **Step 3: Refactor displacement through the motor**

Move normal runtime ownership into the motor script:

```gdscript
func apply_intent_frame(body: CharacterBody3D, frame: Dictionary, delta: float) -> Dictionary:
    var move_local := frame.get("move_local", Vector2.ZERO)
    var forward := -body.global_basis.z
    var right := body.global_basis.x
    var move_world := forward * move_local.y + right * move_local.x
    body.velocity.x = move_world.x
    body.velocity.z = move_world.z
    body.move_and_slide()
    return {
        "velocity_world": body.velocity,
    }
```

- [ ] **Step 4: Re-run the ownership audit**

Run:

```powershell
python -m pytest -q backend\tests\test_character_motor_ownership_audit.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/player/PlayerShell.gd scripts/player/Phase0PlayerBridge.gd scripts/character/CharacterMotor.gd backend/tests/test_character_motor_ownership_audit.py
git commit -m "Move Character Actor displacement ownership into CharacterMotor"
```

### Task 4: Publish Motion State And Make Presentation Follow It

**Files:**
- Modify: `scripts/character/KnightRoleSkin.gd`
- Modify: `scripts/character/CharacterReplica.gd`
- Modify: `scripts/character/CharacterMotor.gd`
- Create: `backend/tests/test_character_motion_state_static.py`

- [ ] **Step 1: Write the failing motion-state tests**

Add assertions that the presentation path consumes motion-oriented parameters instead of raw input as its source of truth:

```python
assert "move_local_actual" in motor_source or "velocity_world" in motor_source
assert "speed" in knight_role_skin_source
assert "move_x" in knight_role_skin_source or "move_y" in knight_role_skin_source
```

- [ ] **Step 2: Run the motion-state tests to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_character_motion_state_static.py
```

Expected before implementation: fail because the motion-state path is incomplete.

- [ ] **Step 3: Publish `CharacterMotionState`-style data from the motor**

Return a dictionary that carries:

```gdscript
{
    "position": body.global_position,
    "velocity_world": body.velocity,
    "move_local_actual": move_local,
    "gait_actual": frame.get("gait", "walk"),
    "grounded": body.is_on_floor(),
}
```

- [ ] **Step 4: Update `CharacterReplica.gd` and `KnightRoleSkin.gd` to consume motion state**

Use a distilled presentation input:

```gdscript
var presentation_input := {
    "move_x": motion_state.get("move_local_actual", Vector2.ZERO).x,
    "move_y": motion_state.get("move_local_actual", Vector2.ZERO).y,
    "speed": motion_state.get("velocity_world", Vector3.ZERO).length(),
    "gait": motion_state.get("gait_actual", "walk"),
}
```

- [ ] **Step 5: Re-run the motion-state tests**

Run:

```powershell
python -m pytest -q backend\tests\test_character_motion_state_static.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/character/KnightRoleSkin.gd scripts/character/CharacterReplica.gd scripts/character/CharacterMotor.gd backend/tests/test_character_motion_state_static.py
git commit -m "Drive Character Actor presentation from motor-owned motion state"
```

### Task 5: Enforce Locked Control Rules And Locomotion Targets

**Files:**
- Modify: `scripts/player/CameraOcclusionFader.gd` only if camera mounting needs adjustment
- Modify: `scripts/player/PlayerController.gd`
- Modify: `scripts/character/KnightRoleSkin.gd`
- Create: `backend/tests/test_character_control_rules_static.py`

- [ ] **Step 1: Write the failing control-rule audit**

Add assertions that the code reflects locked yaw/pitch semantics and locomotion-direction support:

```python
assert "camera pitch" in control_spec_text or "look_pitch" in player_controller_source
assert "strafe" in knight_role_skin_source.lower() or "move_x" in knight_role_skin_source
assert "backpedal" in control_spec_text or "move_y" in knight_role_skin_source
```

- [ ] **Step 2: Run the static audit to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_character_control_rules_static.py
```

Expected before implementation: fail until the player/controller/presentation path reflects the locked control rules.

- [ ] **Step 3: Keep the camera/body rule locked**

Check the player code against this invariant:

```text
camera forward yaw == body forward yaw == aim forward yaw
```

Reject any implementation that lets `A/D` rotate the body independently during baseline locomotion.

- [ ] **Step 4: Expose locomotion parameters needed for strafe and backpedal**

Use presentation inputs like:

```gdscript
anim_tree.set("parameters/Locomotion/blend_position", Vector2(move_x, move_y))
```

or the local equivalent already used by the project.

- [ ] **Step 5: Re-run the static audit**

Run:

```powershell
python -m pytest -q backend\tests\test_character_control_rules_static.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/player/PlayerController.gd scripts/character/KnightRoleSkin.gd scripts/player/CameraOcclusionFader.gd backend/tests/test_character_control_rules_static.py
git commit -m "Enforce locked Character Actor control rules and locomotion targets"
```

### Task 6: Final Verification

**Files:**
- Modify: `scripts/verification/verify_phase0.py` only if verified gaps require it
- Modify: `docs/demo-script.md` only if the verified player-visible control flow changes

- [ ] **Step 1: Run focused tests**

Run:

```powershell
python -m pytest -q backend\tests\test_character_motor_static_contract.py backend\tests\test_player_control_static_contract.py backend\tests\test_character_motor_ownership_audit.py backend\tests\test_character_motion_state_static.py backend\tests\test_character_control_rules_static.py
```

Expected: PASS.

- [ ] **Step 2: Run project verification**

Run:

```powershell
python scripts/verification/harness.py --profile godot-project
python scripts/verification/harness.py --profile phase0
```

Expected:

- Godot project integrity passes
- Phase 0 loop remains green

- [ ] **Step 3: Commit**

```bash
git add scripts/verification/verify_phase0.py docs/demo-script.md
git commit -m "Verify the Character Actor control and locomotion substrate"
```
