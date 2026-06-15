# Character Actor Near-Term Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the first-stage near-term cleanup from the 2026-06-15 CharacterActor optimization spec without entering the Phase1-facing mid-term implementation.

**Architecture:** This plan stays inside the `Current Demo-Safe Target Architecture` phase. It removes remaining transitional clutter from the Phase 0 bridge and actor runtime shell, strengthens local contract consumption, and updates documentation. It does not implement the second-stage `ControllerPort`, full adapter family, binder-ready stack, full asset-library lookup, or motor-owned root-motion execution mode.

**Tech Stack:** Godot 4.6 scenes, GDScript, FastAPI backend, pytest, Harness verification, existing 2026-06-15 CharacterActor optimization spec and migration docs.

---

## Coverage Against 2026-06-15 Spec Next Steps

This plan intentionally pulls as much of the spec's six `Next Steps` into the near-term pass as is safe for the Phase 0 demo:

1. Slim `Phase0PlayerBridge` by moving shell command dispatch out of the bridge: covered by Task 1.
2. Slim `CharacterReplica` by extracting presentation feedback: covered by Task 2.
3. Introduce controller-port style adapters: covered only as a documented mid-term boundary by Task 4. Do not implement `ControllerPort` in this near-term pass.
4. Move `CharacterPresentationInput` toward stronger typed consumption: covered by Task 3 as a contract-preserving actor-to-skin seam, without replacing the near-term dictionary bridge.
5. Start using frozen asset contracts for lookup when ready: covered by Task 5 as a readiness gate and contract inventory. Do not build the full runtime asset lookup library yet.
6. Preserve motor-owned locomotion truth for future root-motion / hybrid modes: covered by Task 6 as a static guard and docs update.

After Tasks 1-6 are complete and verified, Task 7 must update the spec's `Next Steps` section so completed near-term work is removed from future planning.

### Task 1: Extract Phase 0 Shell Commands From Phase0PlayerBridge

**Files:**
- Create: `scripts/player/Phase0PlayerCommandRelay.gd`
- Modify: `scenes/phase0/PlayerShell.tscn`
- Modify: `scripts/player/PlayerShell.gd`
- Modify: `scripts/player/Phase0PlayerBridge.gd`
- Test: `backend/tests/test_phase0_player_command_relay_static.py`

- [ ] **Step 1: Write the failing static test for command relay ownership**

Create `backend/tests/test_phase0_player_command_relay_static.py`:

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_phase0_player_command_relay_owns_demo_shell_commands() -> None:
    relay_source = (ROOT / "scripts" / "player" / "Phase0PlayerCommandRelay.gd").read_text(
        encoding="utf-8"
    )
    bridge_source = (ROOT / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(
        encoding="utf-8"
    )
    shell_scene = (ROOT / "scenes" / "phase0" / "PlayerShell.tscn").read_text(
        encoding="utf-8"
    )

    assert "func handle_shell_action_event(event: InputEvent) -> void:" in relay_source
    assert "dialogue_action" in relay_source
    assert "interact_action" in relay_source
    assert "gait_cycle_action" in relay_source
    assert "crouch_toggle_action" in relay_source
    assert "guard_pose_action" in relay_source
    assert "sword_swing_action" in relay_source
    assert "shield_block_action" in relay_source
    assert "func trigger_dialogue() -> void:" in bridge_source
    assert "func trigger_interaction() -> void:" in bridge_source
    assert "func cycle_gait_mode() -> void:" in bridge_source
    assert "func toggle_crouch_mode() -> void:" in bridge_source
    assert "func trigger_role_action(action_tag: String) -> void:" in bridge_source
    assert "func trigger_combat_action(action_tag: String) -> void:" in bridge_source
    assert "func handle_shell_action_event(event: InputEvent) -> void:" not in bridge_source
    assert "@export var dialogue_action" not in bridge_source
    assert "@export var interact_action" not in bridge_source
    assert "@export var guard_pose_action" not in bridge_source
    assert "@export var sword_swing_action" not in bridge_source
    assert "@export var shield_block_action" not in bridge_source
    assert '[node name="Phase0PlayerCommandRelay"' in shell_scene
```

- [ ] **Step 2: Run the test to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_phase0_player_command_relay_static.py
```

Expected: FAIL because `Phase0PlayerCommandRelay.gd` does not exist and `Phase0PlayerBridge.gd` still owns shell command event handling.

- [ ] **Step 3: Add the command relay**

Create `scripts/player/Phase0PlayerCommandRelay.gd`:

```gdscript
extends Node

@export var dialogue_action := "phase0_submit_dialogue"
@export var interact_action := "phase0_interact"
@export var gait_cycle_action := "phase0_cycle_walk_mode"
@export var crouch_toggle_action := "phase0_toggle_crouch"
@export var guard_pose_action := "phase0_knight_guard_pose"
@export var observe_pose_action := "phase0_knight_observe_pose"
@export var speak_pose_action := "phase0_knight_speak_pose"
@export var inspect_pose_action := "phase0_knight_inspect_pose"
@export var alert_pose_action := "phase0_knight_alert_pose"
@export var ambient_pose_action := "phase0_knight_ambient_pose"
@export var sword_swing_action := "phase0_sword_swing"
@export var shield_block_action := "phase0_shield_block"

@onready var embodiment: Node = $"../Phase0Embodiment"
@onready var player_bridge: Node = $"../Phase0InputBridge"

var sword_swing_pressed := false
var shield_block_pressed := false

func handle_shell_action_event(event: InputEvent) -> void:
	if player_bridge == null:
		return
	if event.is_action_pressed(gait_cycle_action) and player_bridge.has_method("cycle_gait_mode"):
		player_bridge.cycle_gait_mode()
	if event.is_action_pressed(crouch_toggle_action) and player_bridge.has_method("toggle_crouch_mode"):
		player_bridge.toggle_crouch_mode()
	if event.is_action_pressed(dialogue_action):
		if embodiment and embodiment.has_method("trigger_dialogue_feedback"):
			embodiment.trigger_dialogue_feedback()
		_call_bridge_role_action("speak")
		if player_bridge.has_method("trigger_dialogue"):
			player_bridge.trigger_dialogue()
	if event.is_action_pressed(interact_action):
		if embodiment and embodiment.has_method("trigger_interact_feedback"):
			embodiment.trigger_interact_feedback()
		_call_bridge_role_action("inspect")
		if player_bridge.has_method("trigger_interaction"):
			player_bridge.trigger_interaction()
	if event.is_action_pressed(guard_pose_action):
		_call_bridge_role_action("guard")
	if event.is_action_pressed(observe_pose_action):
		_call_bridge_role_action("observe")
	if event.is_action_pressed(speak_pose_action):
		_call_bridge_role_action("speak")
	if event.is_action_pressed(inspect_pose_action):
		_call_bridge_role_action("inspect")
	if event.is_action_pressed(alert_pose_action):
		_call_bridge_role_action("alert")
	if event.is_action_pressed(ambient_pose_action):
		_call_bridge_role_action("ambient")
	if event.is_action_pressed(sword_swing_action):
		if not sword_swing_pressed:
			_call_bridge_combat_action("sword_swing")
		sword_swing_pressed = true
	elif event.is_action_released(sword_swing_action):
		sword_swing_pressed = false
	if event.is_action_pressed(shield_block_action):
		if not shield_block_pressed:
			_call_bridge_combat_action("shield_block")
		shield_block_pressed = true
	elif event.is_action_released(shield_block_action):
		shield_block_pressed = false

func _call_bridge_role_action(action_tag: String) -> void:
	if player_bridge and player_bridge.has_method("trigger_role_action"):
		player_bridge.trigger_role_action(action_tag)

func _call_bridge_combat_action(action_tag: String) -> void:
	if player_bridge and player_bridge.has_method("trigger_combat_action"):
		player_bridge.trigger_combat_action(action_tag)
```

- [ ] **Step 4: Wire the relay in the player shell scene and shell script**

Update `scenes/phase0/PlayerShell.tscn` to mount `Phase0PlayerCommandRelay`.

Add the relay script resource near the existing player script resources:

```gdscene
[ext_resource type="Script" path="res://scripts/player/Phase0PlayerCommandRelay.gd" id="4_command_relay"]
```

Add the relay node as a sibling of `Phase0InputBridge`:

```gdscene
[node name="Phase0PlayerCommandRelay" type="Node" parent="."]
script = ExtResource("4_command_relay")
```

If the scene header's `load_steps` is stale after adding the resource, let Godot resave the scene or increment it by one.

Update `scripts/player/PlayerShell.gd` so `_forward_shell_action_event()` forwards to:

```gdscript
for child_name in ["Phase0InputBridge", "Phase0PlayerCommandRelay"]:
	var target := get_node_or_null(child_name)
	if target and target.has_method("handle_shell_action_event"):
		target.handle_shell_action_event(event)
```

- [ ] **Step 5: Narrow `Phase0PlayerBridge.gd`**

Remove demo-shell command event ownership from `Phase0PlayerBridge.gd`:

```text
- exported dialogue/interact/gait/crouch/pose/combat action strings
- handle_shell_action_event
- gait/crouch shell command dispatch
- direct embodiment feedback calls
- keyboard action-map combat dispatch
- keyboard role-pose dispatch
```

Keep bridge responsibilities:

```text
- set_human_intent_frame
- combat event adaptation
- player shell <-> CharacterReplica sync
- forced locomotion helpers used by autotest
- trigger_dialogue / trigger_interaction as callable action methods
- cycle_gait_mode / toggle_crouch_mode wrappers over the existing gait/stance helpers
- trigger_role_action(action_tag) wrapper over the existing role action helper
- trigger_combat_action(action_tag) wrapper over the existing combat action helper
```

Add public wrappers instead of leaving shell event parsing in the bridge:

```gdscript
func cycle_gait_mode() -> void:
	_cycle_gait_mode()

func toggle_crouch_mode() -> void:
	_toggle_crouch_mode()

func trigger_dialogue() -> void:
	var main_demo := _get_main_demo()
	if main_demo != null and main_demo.has_method("submit_dialogue"):
		main_demo.submit_dialogue()

func trigger_interaction() -> void:
	var main_demo := _get_main_demo()
	if main_demo != null and main_demo.has_method("submit_interaction"):
		main_demo.submit_interaction()

func trigger_role_action(action_tag: String) -> void:
	_trigger_character_c_action(action_tag)

func trigger_combat_action(action_tag: String) -> void:
	_trigger_combat_action(action_tag)
```

- [ ] **Step 6: Run focused verification**

Run:

```powershell
python -m pytest -q backend\tests\test_phase0_player_command_relay_static.py backend\tests\test_character_controller_boundary_static.py backend\tests\test_player_combat_action_static.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add scripts/player/Phase0PlayerCommandRelay.gd scenes/phase0/PlayerShell.tscn scripts/player/PlayerShell.gd scripts/player/Phase0PlayerBridge.gd backend/tests/test_phase0_player_command_relay_static.py
@'
Extract Phase 0 shell action routing from the player bridge

The player shell keeps raw input ownership, while a dedicated relay owns action-map command dispatch. The bridge keeps callable adapter methods so dialogue, interaction, pose, and combat paths remain available without retaining shell-event parsing.

Constraint: Phase 0 demo must not lose existing dialogue, interaction, pose, or combat action-map paths.
Confidence: medium
Scope-risk: moderate
Directive: Keep action-map dispatch in Phase0PlayerCommandRelay unless a later ControllerPort migration replaces the seam.
Tested: python -m pytest -q backend\tests\test_phase0_player_command_relay_static.py backend\tests\test_character_controller_boundary_static.py backend\tests\test_player_combat_action_static.py
Not-tested: Godot editor/runtime unless the focused verification is followed by a Godot harness run.
'@ | Set-Content -Encoding UTF8 .git\near-term-task1-commit.txt
git commit -F .git\near-term-task1-commit.txt
Remove-Item .git\near-term-task1-commit.txt
```

### Task 2: Extract Runtime Feedback From CharacterReplica

**Files:**
- Create: `scripts/character/CharacterRuntimeFeedback.gd`
- Modify: `scenes/phase0/CharacterReplica.tscn`
- Modify: `scripts/character/CharacterReplica.gd`
- Test: `backend/tests/test_character_runtime_feedback_static.py`

- [ ] **Step 1: Write the failing static test for feedback extraction**

Create `backend/tests/test_character_runtime_feedback_static.py`:

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_visible_runtime_feedback_is_not_owned_by_character_replica() -> None:
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )
    feedback_source = (ROOT / "scripts" / "character" / "CharacterRuntimeFeedback.gd").read_text(
        encoding="utf-8"
    )
    scene_source = (ROOT / "scenes" / "phase0" / "CharacterReplica.tscn").read_text(
        encoding="utf-8"
    )

    assert "class_name CharacterRuntimeFeedback" in feedback_source
    assert "func show_combat_feedback(text: String) -> void:" in feedback_source
    assert "func update_nameplate(" in feedback_source
    assert "@onready var nameplate" not in replica_source
    assert "combat_feedback_timer" not in replica_source
    assert "combat_feedback_text" not in replica_source
    assert "func _update_nameplate() -> void:" not in replica_source
    assert "func _show_combat_feedback(text: String) -> void:" not in replica_source
    assert "func _update_combat_feedback(delta: float) -> void:" not in replica_source
    assert '[node name="CharacterRuntimeFeedback"' in scene_source
```

- [ ] **Step 2: Run the test to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_character_runtime_feedback_static.py
```

Expected: FAIL because `CharacterReplica.gd` still owns nameplate/combat feedback logic.

- [ ] **Step 3: Add the feedback node**

Create `scripts/character/CharacterRuntimeFeedback.gd`:

```gdscript
extends Node

class_name CharacterRuntimeFeedback

@onready var nameplate: Label3D = $"../Nameplate"

var combat_feedback_timer := 0.0
var combat_feedback_text := ""

func show_combat_feedback(text: String) -> void:
	combat_feedback_text = text
	combat_feedback_timer = 0.6

func tick(delta: float, actor_id: String, attention_active: bool, environment_attention: bool, source_visual_fact: bool, focus_visual_active: bool) -> void:
	if combat_feedback_timer > 0.0:
		combat_feedback_timer = max(combat_feedback_timer - delta, 0.0)
		if combat_feedback_timer <= 0.0:
			combat_feedback_text = ""
	update_nameplate(actor_id, attention_active, environment_attention, source_visual_fact, focus_visual_active)

func update_nameplate(actor_id: String, attention_active: bool, environment_attention: bool, source_visual_fact: bool, focus_visual_active: bool) -> void:
	if nameplate == null:
		return
	if combat_feedback_timer > 0.0:
		nameplate.text = "%s %s" % [actor_id.to_upper(), combat_feedback_text]
		nameplate.modulate = Color(1.0, 0.35, 0.25, 1.0) if combat_feedback_text == "SWING" else Color(0.3, 0.8, 1.0, 1.0)
		return
	if not attention_active:
		nameplate.text = actor_id.to_upper()
		nameplate.modulate = Color(1.0, 1.0, 1.0, 1.0)
		return
	if environment_attention and not focus_visual_active:
		nameplate.text = "%s ?" % actor_id.to_upper()
		nameplate.modulate = Color(1.0, 0.62, 0.28, 1.0)
		return
	if source_visual_fact and not focus_visual_active:
		nameplate.text = "%s ~" % actor_id.to_upper()
		nameplate.modulate = Color(0.55, 0.92, 1.0, 1.0)
		return
	nameplate.text = "%s !" % actor_id.to_upper()
	nameplate.modulate = Color(1.0, 0.92, 0.45, 1.0)
```

- [ ] **Step 4: Delegate feedback from `CharacterReplica.gd`**

Mount `CharacterRuntimeFeedback` in `scenes/phase0/CharacterReplica.tscn`.

Add the feedback script resource near the existing character script resources:

```gdscene
[ext_resource type="Script" path="res://scripts/character/CharacterRuntimeFeedback.gd" id="7_runtime_feedback"]
```

Add the feedback node as a direct child of `CharacterReplica`, preferably after `Nameplate` so the sibling path remains obvious:

```gdscene
[node name="CharacterRuntimeFeedback" type="Node" parent="."]
script = ExtResource("7_runtime_feedback")
```

If the scene header's `load_steps` is stale after adding the resource, let Godot resave the scene or increment it by one.

In `CharacterReplica.gd`:

```gdscript
@onready var runtime_feedback: Node = $CharacterRuntimeFeedback
```

Remove the direct `Nameplate` ownership and feedback state from `CharacterReplica.gd`:

```text
- @onready var nameplate
- combat_feedback_timer
- combat_feedback_text
- _update_nameplate()
- _show_combat_feedback()
- _update_combat_feedback()
```

Replace direct combat feedback mutation with:

```gdscript
if runtime_feedback and runtime_feedback.has_method("show_combat_feedback"):
	runtime_feedback.show_combat_feedback("SWING")
```

Use the same call with `"BLOCK"` for shield feedback.

Replace direct nameplate updates with:

```gdscript
if runtime_feedback and runtime_feedback.has_method("tick"):
	runtime_feedback.tick(delta, actor_id, attention_active, environment_attention, source_visual_fact, focus_attention_visual_timer > 0.0)
```

For non-physics points that previously refreshed the nameplate immediately, call the same method with `0.0` for `delta`.

- [ ] **Step 5: Run focused verification**

Run:

```powershell
python -m pytest -q backend\tests\test_character_runtime_feedback_static.py backend\tests\test_character_runtime_boundary_static.py backend\tests\test_player_combat_action_static.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add scripts/character/CharacterRuntimeFeedback.gd scenes/phase0/CharacterReplica.tscn scripts/character/CharacterReplica.gd backend/tests/test_character_runtime_feedback_static.py
@'
Extract visible CharacterActor feedback from the runtime shell

Runtime feedback now lives behind a dedicated scene node so CharacterReplica can stay focused on actor runtime state instead of owning nameplate and transient combat feedback presentation.

Constraint: Phase 0 needs the same visible feedback behavior after the extraction.
Confidence: medium
Scope-risk: moderate
Directive: Do not reintroduce nameplate or combat feedback state directly into CharacterReplica.
Tested: python -m pytest -q backend\tests\test_character_runtime_feedback_static.py backend\tests\test_character_runtime_boundary_static.py backend\tests\test_player_combat_action_static.py
Not-tested: Godot editor/runtime unless the focused verification is followed by a Godot harness run.
'@ | Set-Content -Encoding UTF8 .git\near-term-task2-commit.txt
git commit -F .git\near-term-task2-commit.txt
Remove-Item .git\near-term-task2-commit.txt
```

### Task 3: Strengthen Near-Term Presentation Contract Consumption

**Files:**
- Read: `scripts/character/CharacterPresentationInput.gd`
- Read: `scripts/character/CharacterReplica.gd`
- Modify: `scripts/character/KnightRoleSkin.gd`
- Test: `backend/tests/test_character_near_term_presentation_contract_static.py`

- [ ] **Step 1: Write the failing static test for near-term presentation contract use**

Create `backend/tests/test_character_near_term_presentation_contract_static.py`:

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_near_term_presentation_input_contract_is_consumed_at_actor_to_skin_boundary() -> None:
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )
    role_skin_source = (ROOT / "scripts" / "character" / "KnightRoleSkin.gd").read_text(
        encoding="utf-8"
    )
    contract_source = (ROOT / "scripts" / "character" / "CharacterPresentationInput.gd").read_text(
        encoding="utf-8"
    )

    assert "PRESENTATION_INPUT_KEYS" in contract_source
    assert '"motion_state"' in role_skin_source
    assert '"action_state"' in role_skin_source
    assert '"equipment_state"' in role_skin_source
    assert "CharacterPresentationInput" in role_skin_source
    assert "_build_player_presentation_input" in replica_source
```

- [ ] **Step 2: Run the test to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_character_near_term_presentation_contract_static.py
```

Expected: FAIL because `KnightRoleSkin.gd` still mainly consumes flattened near-term fields.

- [ ] **Step 3: Keep flattened fields but preserve the full contract at the skin boundary**

Update `KnightRoleSkin.gd` without deleting the existing flat-field fallback behavior.

Add the contract preload near the other top-level preloads:

```gdscript
const CharacterPresentationInputRef = preload("res://scripts/character/CharacterPresentationInput.gd")
```

Add a stored copy near the other presentation state variables:

```gdscript
var current_presentation_contract: Dictionary = {}
```

Then update the start of the existing `apply_presentation_input()` function to preserve the formal contract and still consume the current normalized flat payload:

```gdscript
func apply_presentation_input(next_input: Dictionary) -> void:
	current_presentation_contract = CharacterPresentationInputRef.normalize(next_input)
	var normalized := _normalize_presentation_input(next_input)
	var motion_state: Dictionary = current_presentation_contract.get("motion_state", {})
	var move_local_actual: Variant = motion_state.get("move_local_actual", Vector2.ZERO)
	var _action_state: Dictionary = current_presentation_contract.get("action_state", {})
	var _equipment_state: Dictionary = current_presentation_contract.get("equipment_state", {})

	move_x = float(normalized.get("move_x", move_local_actual.x if move_local_actual is Vector2 else 0.0))
	move_y = float(normalized.get("move_y", move_local_actual.y if move_local_actual is Vector2 else 0.0))
	speed = float(normalized.get("speed", motion_state.get("speed_actual", 0.0)))
	presentation_gait = str(normalized.get("gait", motion_state.get("gait_actual", "walk")))
```

Keep `action_state` and `equipment_state` as explicit local contract reads even if the near-term skin does not yet apply every field; this proves the actor-to-skin seam receives the full contract without forcing a Phase1 typed pipeline.

Keep the old flat fields for demo safety. The improvement is preserving the formal contract at the L3 -> L5 seam.

- [ ] **Step 4: Run focused verification**

Run:

```powershell
python -m pytest -q backend\tests\test_character_near_term_presentation_contract_static.py backend\tests\test_character_presentation_modifier_static.py backend\tests\test_knight_locomotion_pose_refinement_static.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add scripts/character/KnightRoleSkin.gd backend/tests/test_character_near_term_presentation_contract_static.py
@'
Preserve CharacterPresentationInput at the skin boundary

The near-term skin keeps consuming the current flat fallback payload while storing and reading the formal presentation contract at the actor-to-skin seam. This strengthens the boundary without forcing a Phase1 typed pipeline.

Constraint: Demo-safe migration must keep existing KnightRoleSkin locomotion behavior stable.
Confidence: medium
Scope-risk: narrow
Directive: Keep flat fallback fields until the typed presentation pipeline has runtime consumers.
Tested: python -m pytest -q backend\tests\test_character_near_term_presentation_contract_static.py backend\tests\test_character_presentation_modifier_static.py backend\tests\test_knight_locomotion_pose_refinement_static.py
Not-tested: Full Godot runtime animation inspection.
'@ | Set-Content -Encoding UTF8 .git\near-term-task3-commit.txt
git commit -F .git\near-term-task3-commit.txt
Remove-Item .git\near-term-task3-commit.txt
```

### Task 4: Document But Do Not Implement The Mid-Term ControllerPort Boundary

**Files:**
- Modify: `docs/character/character-control-chain.md`
- Modify: `docs/character/character-actor-migration-status.md`
- Test: `backend/tests/test_character_mid_term_boundary_docs_static.py`

- [ ] **Step 1: Write the failing docs test**

Create `backend/tests/test_character_mid_term_boundary_docs_static.py`:

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_mid_term_controller_port_is_documented_but_not_implemented_in_near_term_cleanup() -> None:
    control_doc = (ROOT / "docs" / "character" / "character-control-chain.md").read_text(
        encoding="utf-8"
    )
    migration_doc = (ROOT / "docs" / "character" / "character-actor-migration-status.md").read_text(
        encoding="utf-8"
    )

    assert "ControllerPort" in control_doc
    assert "mid-term" in control_doc.lower()
    assert "not implemented in the near-term cleanup" in migration_doc
    assert not (ROOT / "scripts" / "character" / "CharacterControllerPort.gd").exists()
```

- [ ] **Step 2: Run the test to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_character_mid_term_boundary_docs_static.py
```

Expected: FAIL because the docs do not yet explicitly say that `ControllerPort` is a mid-term boundary and not part of this near-term cleanup.

- [ ] **Step 3: Update docs**

Add to `docs/character/character-control-chain.md`:

```markdown
## Mid-Term ControllerPort Boundary

`ControllerPort` is a Phase1-facing mid-term boundary. The near-term cleanup keeps `PlayerShell` and `Phase0PlayerBridge` as the demo-safe implementation seam and does not create adapter classes yet.
```

Add to `docs/character/character-actor-migration-status.md`:

```markdown
`ControllerPort` is intentionally not implemented in the near-term cleanup. It remains a mid-term target after the Phase 0 bridge and runtime shell are slimmer.
```

- [ ] **Step 4: Run docs tests**

Run:

```powershell
python -m pytest -q backend\tests\test_character_mid_term_boundary_docs_static.py
python scripts/verification/harness.py --profile docs
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add docs/character/character-control-chain.md docs/character/character-actor-migration-status.md backend/tests/test_character_mid_term_boundary_docs_static.py
@'
Document the deferred CharacterActor ControllerPort boundary

The near-term cleanup records ControllerPort as a mid-term seam instead of implementing adapter classes prematurely. This keeps the Phase 0 bridge stable while preventing future work from mistaking the omission for an architecture gap.

Constraint: Near-term cleanup must not enter the Phase1-facing adapter family.
Confidence: high
Scope-risk: narrow
Directive: Do not add CharacterControllerPort.gd during this near-term pass.
Tested: python -m pytest -q backend\tests\test_character_mid_term_boundary_docs_static.py; python scripts/verification/harness.py --profile docs
Not-tested: Runtime behavior, because this task is documentation-only.
'@ | Set-Content -Encoding UTF8 .git\near-term-task4-commit.txt
git commit -F .git\near-term-task4-commit.txt
Remove-Item .git\near-term-task4-commit.txt
```

### Task 5: Add The Asset Contract Lookup Readiness Gate

**Files:**
- Modify: `docs/character/character-asset-integration.md`
- Modify: `docs/character/character-actor-migration-status.md`
- Test: `backend/tests/test_character_asset_lookup_readiness_static.py`

- [ ] **Step 1: Write the failing static test for asset lookup readiness**

Create `backend/tests/test_character_asset_lookup_readiness_static.py`:

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_asset_contracts_have_a_near_term_lookup_readiness_gate() -> None:
    asset_doc = (ROOT / "docs" / "character" / "character-asset-integration.md").read_text(
        encoding="utf-8"
    )
    migration_doc = (ROOT / "docs" / "character" / "character-actor-migration-status.md").read_text(
        encoding="utf-8"
    )

    assert "## Near-Term Asset Lookup Readiness Gate" in asset_doc
    assert "`CharacterAssetBindingProfile`" in asset_doc
    assert "`CharacterEquipmentBindingProfile`" in asset_doc
    assert "`CharacterActionAssetDescriptor`" in asset_doc
    assert "contract-only in this near-term cleanup" in migration_doc
    assert (ROOT / "scripts" / "character" / "CharacterAssetBindingProfile.gd").exists()
    assert (ROOT / "scripts" / "character" / "CharacterEquipmentBindingProfile.gd").exists()
    assert (ROOT / "scripts" / "character" / "CharacterActionAssetDescriptor.gd").exists()
    assert not (ROOT / "scripts" / "character" / "CharacterAssetLibrary.gd").exists()
```

- [ ] **Step 2: Run the test to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_character_asset_lookup_readiness_static.py
```

Expected: FAIL because the docs do not yet state the near-term readiness gate and migration status does not explicitly say asset lookup remains contract-only.

- [ ] **Step 3: Update asset integration docs**

Add to `docs/character/character-asset-integration.md` before `## Long-Term Direction`:

```markdown
## Near-Term Asset Lookup Readiness Gate

The frozen contract files are the only near-term asset-library surface:

- `CharacterAssetBindingProfile`
- `CharacterEquipmentBindingProfile`
- `CharacterActionAssetDescriptor`

Near-term cleanup may reference these contracts in docs, tests, and integration checklists, but it must not add a full runtime `CharacterAssetLibrary` or generalized model lookup path yet.

The repository is ready to start actual runtime lookup only after:

1. at least two role skins need different skeleton or equipment bindings
2. the Phase 0 demo remains green with the current hardcoded knight path
3. a new lookup path can prove fallback behavior for missing model, skeleton, equipment, and action entries
4. the lookup result still feeds the shared `CharacterActor` substrate rather than creating a model-specific runtime species
```

Add to `docs/character/character-actor-migration-status.md` under `Still Transitional`:

```markdown
- asset lookup remains contract-only in this near-term cleanup; do not add `CharacterAssetLibrary.gd` until multiple role skins require real lookup and fallback behavior
```

- [ ] **Step 4: Run focused verification**

Run:

```powershell
python -m pytest -q backend\tests\test_character_asset_lookup_readiness_static.py backend\tests\test_character_asset_contract_static.py
python scripts/verification/harness.py --profile docs
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add docs/character/character-asset-integration.md docs/character/character-actor-migration-status.md backend/tests/test_character_asset_lookup_readiness_static.py
@'
Gate CharacterActor asset lookup behind readiness criteria

The frozen asset contracts remain the near-term integration surface, while full runtime lookup is deferred until multiple role skins and fallback behavior justify the extra system.

Constraint: Phase 0 must not grow a generalized asset library before the demo needs it.
Confidence: high
Scope-risk: narrow
Directive: Do not add CharacterAssetLibrary.gd until the documented readiness gate is satisfied.
Tested: python -m pytest -q backend\tests\test_character_asset_lookup_readiness_static.py backend\tests\test_character_asset_contract_static.py; python scripts/verification/harness.py --profile docs
Not-tested: Runtime asset swapping, because lookup remains contract-only.
'@ | Set-Content -Encoding UTF8 .git\near-term-task5-commit.txt
git commit -F .git\near-term-task5-commit.txt
Remove-Item .git\near-term-task5-commit.txt
```

### Task 6: Guard Motor-Owned Locomotion For Future Root Motion

**Files:**
- Modify: `docs/character/character-actor-architecture.md`
- Modify: `docs/character/character-actor-migration-status.md`
- Test: `backend/tests/test_character_locomotion_motor_ownership_guard_static.py`

- [ ] **Step 1: Write the failing static test for root-motion ownership**

Create `backend/tests/test_character_locomotion_motor_ownership_guard_static.py`:

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_root_motion_and_hybrid_modes_remain_motor_owned() -> None:
    motor_source = (ROOT / "scripts" / "character" / "CharacterMotor.gd").read_text(
        encoding="utf-8"
    )
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )
    skin_source = (ROOT / "scripts" / "character" / "KnightRoleSkin.gd").read_text(
        encoding="utf-8"
    )
    architecture_doc = (ROOT / "docs" / "character" / "character-actor-architecture.md").read_text(
        encoding="utf-8"
    )
    migration_doc = (ROOT / "docs" / "character" / "character-actor-migration-status.md").read_text(
        encoding="utf-8"
    )

    assert "body.velocity.x =" in motor_source
    assert "body.velocity.z =" in motor_source
    assert "move_and_slide(" in motor_source
    assert "_consume_role_root_motion_world_delta" in replica_source
    assert "last_root_motion_world_delta" in replica_source
    assert "consume_root_motion_delta" in skin_source
    assert "move_and_slide(" not in skin_source
    assert "global_position +=" not in skin_source
    assert "## Root-Motion Ownership Guard" in architecture_doc
    assert "CharacterMotor remains the only normal owner of baseline displacement" in architecture_doc
    assert "Future root-motion and hybrid work must be motor-owned" in architecture_doc
    assert "CharacterReplica direct root-motion displacement remains transitional" in migration_doc
```

- [ ] **Step 2: Run the test to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_character_locomotion_motor_ownership_guard_static.py
```

Expected: FAIL because the docs do not yet include the explicit root-motion ownership guard text or the transitional warning about current actor-shell root-motion displacement.

- [ ] **Step 3: Update locomotion ownership docs**

Add to `docs/character/character-actor-architecture.md` after `## Future LocomotionExecutionMode`:

````markdown
## Root-Motion Ownership Guard

CharacterMotor remains the only normal owner of baseline displacement.

`KnightRoleSkin` may expose sampled root-motion deltas, and `CharacterReplica` may coordinate those deltas with actor runtime state, but presentation nodes must not directly move the world body.

Future root-motion and hybrid work must be motor-owned. A complete mid-term `root_motion` or `hybrid` execution mode must preserve this path:

```text
presentation root-motion sample
-> CharacterReplica coordination
-> CharacterMotor-owned displacement
-> CharacterMotionState
```
````

Add to `docs/character/character-actor-migration-status.md` under `Still Transitional`:

```markdown
- CharacterReplica direct root-motion displacement remains transitional; future root-motion and hybrid work must be motor-owned, and presentation must not become the owner of world displacement
```

- [ ] **Step 4: Run focused verification**

Run:

```powershell
python -m pytest -q backend\tests\test_character_locomotion_motor_ownership_guard_static.py backend\tests\test_character_motor_ownership_audit.py backend\tests\test_knight_locomotion_pose_refinement_static.py
python scripts/verification/harness.py --profile docs
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add docs/character/character-actor-architecture.md docs/character/character-actor-migration-status.md backend/tests/test_character_locomotion_motor_ownership_guard_static.py
@'
Guard future CharacterActor root motion behind motor ownership

The docs now state that current actor-shell root-motion displacement is transitional and that future root-motion or hybrid execution must route displacement ownership through CharacterMotor.

Constraint: Near-term cleanup must not implement the full LocomotionExecutionMode stack.
Confidence: high
Scope-risk: narrow
Directive: Presentation may sample deltas, but future world displacement ownership belongs in CharacterMotor.
Tested: python -m pytest -q backend\tests\test_character_locomotion_motor_ownership_guard_static.py backend\tests\test_character_motor_ownership_audit.py backend\tests\test_knight_locomotion_pose_refinement_static.py; python scripts/verification/harness.py --profile docs
Not-tested: Full root-motion runtime migration, intentionally deferred.
'@ | Set-Content -Encoding UTF8 .git\near-term-task6-commit.txt
git commit -F .git\near-term-task6-commit.txt
Remove-Item .git\near-term-task6-commit.txt
```

### Task 7: Final Verification And Near-Term Cleanup Closeout

**Files:**
- Modify if needed:
  - `docs/character/character-actor-migration-status.md`
  - `docs/character/character-debug-and-verification.md`
  - `docs/superpowers/specs/2026-06-15-character-actor-architecture-optimization-design.md`

- [ ] **Step 1: Run full verification**

Run:

```powershell
python -m pytest -v
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile godot-project
python scripts/verification/harness.py --profile phase0
```

Expected:

- all repository tests pass
- docs and godot-project remain green
- strict Phase 0 remains green

- [ ] **Step 2: Update closeout docs**

Record:

```text
- `Phase0PlayerBridge` no longer owns shell command dispatch
- visible runtime feedback moved out of `CharacterReplica`
- `CharacterPresentationInput` is preserved at the actor-to-skin boundary
- `ControllerPort` remains a documented mid-term target, not a near-term implementation
- asset lookup remains gated behind explicit readiness criteria
- future root-motion / hybrid work remains motor-owned
- remaining work before Phase1-facing mid-term can begin
```

- [ ] **Step 3: Update the spec Next Steps to avoid repeated planning**

In `docs/superpowers/specs/2026-06-15-character-actor-architecture-optimization-design.md`, replace the existing `## Next Steps` list with:

```markdown
## Next Steps

After the near-term cleanup closeout, do not re-plan the completed near-term work:

- `Phase0PlayerBridge` shell command dispatch has been extracted
- `CharacterReplica` visible runtime feedback has been split out
- `CharacterPresentationInput` is preserved at the actor-to-skin boundary
- `ControllerPort` has been documented as a mid-term boundary and intentionally not implemented in the near-term cleanup
- asset lookup has a documented readiness gate and remains contract-only until multiple role skins require real lookup
- future root-motion / hybrid work has a motor-owned displacement guard

Remaining follow-up should start from the Phase1-facing mid-term target:

1. Implement explicit `ControllerPort` adapters only when the next runtime slice needs human / agent / program control ports.
2. Replace near-term dictionary bridging with a stronger typed presentation pipeline when runtime consumers are ready.
3. Build actual asset lookup only after multiple role skins require binding profiles and fallback behavior.
4. Expand `LocomotionExecutionMode` into real root-motion or hybrid execution only while preserving `CharacterMotor` as displacement owner.
5. Keep Phase 0 demo verification green before and after each mid-term slice.
```

- [ ] **Step 4: Run final verification again after doc closeout**

Run:

```powershell
python -m pytest -v
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile godot-project
python scripts/verification/harness.py --profile phase0
```

Expected:

- all repository tests pass
- docs and godot-project remain green
- strict Phase 0 remains green
- `Next Steps` no longer repeats near-term work that has already been completed

- [ ] **Step 5: Commit**

```powershell
git add docs/character/character-actor-migration-status.md docs/character/character-debug-and-verification.md docs/character/character-asset-integration.md docs/character/character-actor-architecture.md docs/superpowers/specs/2026-06-15-character-actor-architecture-optimization-design.md
@'
Close the CharacterActor near-term cleanup pass

The closeout records the completed near-term cleanup and rewrites the spec Next Steps so future planning starts from the remaining Phase1-facing mid-term work instead of repeating already-completed cleanup.

Constraint: Completion status must distinguish verified near-term work from deferred mid-term architecture.
Confidence: high
Scope-risk: moderate
Directive: Do not re-plan completed near-term cleanup items after this closeout; start future work from the remaining mid-term list.
Tested: python -m pytest -v; python scripts/verification/harness.py --profile docs; python scripts/verification/harness.py --profile godot-project; python scripts/verification/harness.py --profile phase0
Not-tested: None if all listed verification commands pass.
'@ | Set-Content -Encoding UTF8 .git\near-term-task7-commit.txt
git commit -F .git\near-term-task7-commit.txt
Remove-Item .git\near-term-task7-commit.txt
```
