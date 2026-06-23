# Observatory UI Lightweight Debug Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the Godot-side `Character Director Observatory` into a lightweight developer-only default layout with actor-follow overhead cards, a right-side current-actor detail rail, and a thin bottom latest-events strip while keeping heavy director/script surfaces behind explicit modes.

**Architecture:** Reuse the existing `CharacterDirectorState`, `ObservatoryRoot`, and current observatory payload families. Replace the default multi-panel flat layout with a three-layer composition: actor-local overhead cards, one fixed right-side detail rail for the selected actor, and a bottom strip limited to the latest three entries. Keep `DirectorMonitorPanel`, `SimingDirectorBoard`, `ScriptTimelinePanel`, and `DialogueSceneLedger` as explicit expanded debug surfaces only.

**Tech Stack:** Godot 4.6 GDScript, existing `ObservatoryRoot.tscn`, current `CharacterDirectorState.gd`, existing observatory UI scripts, pytest static tests, Godot project harness verification.

---

## File Structure

### Existing files to modify

- `scripts/ui/ActorStateTags.gd`
  - Stop rendering a left-side fixed summary block.
  - Become the overhead card manager that attaches compact state cards to scene actors.

- `scripts/ui/CharacterObserverPanel.gd`
  - Stop acting as a generic large text dump.
  - Become the single right-side fixed detail rail for the current observed actor.

- `scripts/ui/WorldOutcomeTrace.gd`
  - Stop acting as a tall left-bottom list.
  - Become a thin bottom event strip that renders the latest 3 entries across world / Siming / script sources.

- `scripts/ui/DirectorMonitorPanel.gd`
  - Keep as expanded director-mode surface only.
  - Reposition and reduce default collision with the lightweight layout.

- `scripts/ui/SimingDirectorBoard.gd`
  - Keep as expanded director-mode surface only.
  - Reposition to work as a companion panel, not a default always-on block.

- `scripts/ui/ScriptTimelinePanel.gd`
  - Keep as expanded script-mode surface only.
  - Reposition for explicit replay review.

- `scripts/ui/DialogueSceneLedger.gd`
  - Keep as expanded script-mode surface only.
  - Reposition for explicit replay review.

- `scripts/ui/CharacterDirectorState.gd`
  - Add helper APIs for lightweight layout composition:
    - current selected actor label
    - latest script beat summaries
    - latest Siming summaries
    - merged latest-bottom-strip entries

- `backend/tests/test_actor_state_tags_static.py`
- `backend/tests/test_character_observer_panel_static.py`
- `backend/tests/test_world_outcome_trace_static.py` if absent create it
- `backend/tests/test_director_monitor_panel_static.py`
- `backend/tests/test_script_timeline_panel_static.py`
- `backend/tests/test_dialogue_scene_ledger_static.py`
- `backend/tests/test_siming_director_board_static.py`
- `backend/tests/test_character_director_state_static.py`
- `backend/tests/test_observatory_scene_mount_static.py`

### Existing files to inspect, likely unchanged or only lightly adjusted

- `scenes/phase0/ObservatoryRoot.tscn`
  - Keep mounted in `MainDemo`.
  - May require node ordering or z-order adjustments only.

- `scripts/ui/RelationshipOverlay.gd`
  - Keep the same role.
  - Ensure it still visually coexists with the lightweight layout.

- `scripts/ui/ObservatoryInputController.gd`
  - Keep developer controls unchanged.

---

## Task 1: Freeze Lightweight Layout Contracts With Static Tests

**Files:**
- Modify:
  - `backend/tests/test_actor_state_tags_static.py`
  - `backend/tests/test_character_observer_panel_static.py`
  - `backend/tests/test_director_monitor_panel_static.py`
  - `backend/tests/test_script_timeline_panel_static.py`
  - `backend/tests/test_dialogue_scene_ledger_static.py`
  - `backend/tests/test_siming_director_board_static.py`
  - `backend/tests/test_character_director_state_static.py`
- Create if missing:
  - `backend/tests/test_world_outcome_trace_static.py`

- [ ] **Step 1.1: Write failing static tests for overhead-card responsibilities**

Add assertions that require `ActorStateTags.gd` to contain all of:

```python
assert "head-follow" not in source.lower()  # no placeholder naming
assert "get_visible_actor_states()" in source
assert "get_viewport().get_camera_3d()" in source
assert "current observed actor" not in source.lower()
assert "意图" in source
assert "目标" in source
assert "原因" in source
```

Refine to concrete strings already expected in repo style:

```python
assert "当前意图" in source
assert "当前目标" in source
assert "原因摘要" in source
```

- [ ] **Step 1.2: Write failing static tests for the right-side detail rail**

Require `CharacterObserverPanel.gd` to render four compact sections:

```python
assert "看到了什么" in source
assert "怎么理解" in source
assert "准备做什么" in source
assert "世界 / 司命反馈" in source
assert "label.position = Vector2(" in source
assert "label.size = Vector2(" in source
```

Require it not to keep the old long left-block layout strings:

```python
assert "他刚刚看见/听见：" not in source
assert "他脑子里记着：" not in source
```

- [ ] **Step 1.3: Write failing static tests for the bottom thin event strip**

Create or extend a `WorldOutcomeTrace` static test that requires:

```python
assert "最近 3 条" in source
assert "世界" in source
assert "司命" in source
assert "节拍" in source
assert "slice(0, 3)" in source or "slice(max(" in source
```

And forbid the old tall generic list behavior:

```python
assert 'for outcome in state.recent_world_outcomes' not in source
```

- [ ] **Step 1.4: Write failing static tests for heavy panels becoming explicit expanded surfaces**

Require:

```python
# DirectorMonitorPanel
assert "state.director_mode" in director_source
assert "state.observatory_enabled and state.director_mode" in director_source

# ScriptTimelinePanel
assert "state.script_mode" in script_source
assert "state.observatory_enabled and state.script_mode" in script_source

# DialogueSceneLedger
assert "state.script_mode" in ledger_source
```

Also require updated wording in `DirectorMonitorPanel.gd` to stay aligned:

```python
assert "当前观察角色：" in director_source
```

- [ ] **Step 1.5: Write failing static tests for new state-center helpers**

Add assertions in `test_character_director_state_static.py` for helper methods:

```python
assert "func get_selected_actor_label() -> String:" in source
assert "func get_latest_bottom_strip_entries() -> Array[Dictionary]:" in source
assert "func get_latest_script_beat_summaries(" in source
assert "func get_latest_siming_summaries(" in source
```

- [ ] **Step 1.6: Run focused tests to verify they fail first**

Run:

```powershell
python -m pytest -q backend/tests/test_actor_state_tags_static.py backend/tests/test_character_observer_panel_static.py backend/tests/test_director_monitor_panel_static.py backend/tests/test_script_timeline_panel_static.py backend/tests/test_dialogue_scene_ledger_static.py backend/tests/test_siming_director_board_static.py backend/tests/test_character_director_state_static.py
```

Expected:

```text
FAIL with missing new lightweight-layout strings / helpers
```

- [ ] **Step 1.7: Commit the failing-test contract**

```powershell
git add backend/tests/test_actor_state_tags_static.py backend/tests/test_character_observer_panel_static.py backend/tests/test_director_monitor_panel_static.py backend/tests/test_script_timeline_panel_static.py backend/tests/test_dialogue_scene_ledger_static.py backend/tests/test_siming_director_board_static.py backend/tests/test_character_director_state_static.py backend/tests/test_world_outcome_trace_static.py
git commit -m "Lock observatory lightweight debug layout contracts

Constraint: Observatory remains developer-only and hidden by default
Rejected: Keep default flat multi-panel layout | still overlaps playfield and obscures testing
Confidence: high
Scope-risk: moderate
Directive: Do not restore always-on multi-panel default layout without re-verifying playfield obstruction
Tested: Focused static observatory UI contract tests (expected red)
Not-tested: Godot runtime layout behavior"
```

---

## Task 2: Add State-Center Helpers For Lightweight Composition

**Files:**
- Modify:
  - `scripts/ui/CharacterDirectorState.gd`
- Test:
  - `backend/tests/test_character_director_state_static.py`

- [ ] **Step 2.1: Implement selected-actor label helper**

Add a helper like:

```gdscript
func get_selected_actor_label() -> String:
	return _actor_label(selected_actor_id)
```

Add a local mapper:

```gdscript
func _actor_label(actor_id: String) -> String:
	if actor_id == "char_a":
		return "角色A"
	if actor_id == "char_b":
		return "角色B"
	if actor_id == "char_c":
		return "玩家角色"
	return actor_id
```

- [ ] **Step 2.2: Implement script-beat summary helper**

Add:

```gdscript
func get_latest_script_beat_summaries(limit: int = 3) -> Array[String]:
	var rows: Array[String] = []
	var beats := get_recent_script_beats()
	var start := max(beats.size() - limit, 0)
	for beat in beats.slice(start, beats.size()):
		rows.append(str(beat.get("dramatic_summary", "") or ""))
	return rows
```

- [ ] **Step 2.3: Implement Siming summary helper**

Add:

```gdscript
func get_latest_siming_summaries(limit: int = 3) -> Array[String]:
	var rows: Array[String] = []
	var events := get_recent_siming_events()
	var start := max(events.size() - limit, 0)
	for event in events.slice(start, events.size()):
		rows.append(str(event.get("summary", "") or ""))
	return rows
```

- [ ] **Step 2.4: Implement merged bottom-strip helper**

Add:

```gdscript
func get_latest_bottom_strip_entries() -> Array[Dictionary]:
	var rows: Array[Dictionary] = []
	for outcome in get_recent_world_outcomes():
		rows.append({
			"type": "世界",
			"summary": str(outcome.get("dramatic_consequence_summary", "") or outcome.get("world_change_summary", "") or outcome.get("settlement_status", "") or ""),
			"producer_ts": int(outcome.get("producer_ts", 0)),
		})
	for event in get_recent_siming_events():
		rows.append({
			"type": "司命",
			"summary": str(event.get("summary", "") or ""),
			"producer_ts": int(event.get("producer_ts", 0)),
		})
	for beat in get_recent_script_beats():
		rows.append({
			"type": "节拍",
			"summary": str(beat.get("dramatic_summary", "") or ""),
			"producer_ts": int(beat.get("producer_ts", 0)),
		})
	rows.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return int(a.get("producer_ts", 0)) > int(b.get("producer_ts", 0))
	)
	if rows.size() > 3:
		rows = _dictionary_array(rows.slice(0, 3))
	return rows
```

- [ ] **Step 2.5: Run focused tests and verify green**

Run:

```powershell
python -m pytest -q backend/tests/test_character_director_state_static.py
```

Expected:

```text
PASS
```

- [ ] **Step 2.6: Commit**

```powershell
git add scripts/ui/CharacterDirectorState.gd backend/tests/test_character_director_state_static.py
git commit -m "Add lightweight observatory state helpers

Constraint: UI must reuse existing observatory payload families without new backend coupling
Rejected: Compute layout summaries independently in every panel | duplicates logic and diverges formatting
Confidence: high
Scope-risk: narrow
Directive: Keep summary helpers presentation-oriented; do not move gameplay authority into this state center
Tested: python -m pytest -q backend/tests/test_character_director_state_static.py
Not-tested: Godot runtime visual behavior"
```

---

## Task 3: Convert ActorStateTags Into Overhead Actor Cards

**Files:**
- Modify:
  - `scripts/ui/ActorStateTags.gd`
- Test:
  - `backend/tests/test_actor_state_tags_static.py`

- [ ] **Step 3.1: Replace the single fixed left-side label with per-actor card nodes**

Refactor to manage a dictionary of labels keyed by actor id:

```gdscript
var actor_cards := {}
```

Add per-frame refresh hooks:

```gdscript
func _process(_delta: float) -> void:
	_refresh_card_positions()
```

- [ ] **Step 3.2: Build compact card text**

Implement helpers:

```gdscript
func _build_primary_line(actor_id: String, payload: Dictionary) -> String:
	return "%s | %s" % [
		_actor_label(actor_id),
		str(payload.get("state_label", "") or "状态未知"),
	]

func _build_secondary_line(payload: Dictionary) -> String:
	return "当前意图：%s -> 当前目标：%s" % [
		str(payload.get("current_intent", "") or "暂无"),
		str(payload.get("focus_target", "") or "暂无"),
	]

func _build_reason_line(payload: Dictionary) -> String:
	return "原因摘要：%s" % str(payload.get("why_now_summary", "") or "暂无")
```

- [ ] **Step 3.3: Only expand the currently observed actor card**

Use:

```gdscript
var selected_actor_id := str(state.selected_actor_id)
```

Rule:

```gdscript
if actor_id == selected_actor_id:
	card_label.text = "\n".join([primary, secondary, reason])
else:
	card_label.text = "\n".join([primary, secondary])
```

- [ ] **Step 3.4: Position cards above actors using the viewport camera**

Use:

```gdscript
var camera := get_viewport().get_camera_3d()
var actor_node := state.resolve_target_node(actor_id)
```

Project actor head anchor:

```gdscript
var world_point := actor_node.global_position + Vector3(0.0, 2.15, 0.0)
var screen_point := camera.unproject_position(world_point)
```

Apply distance-based simplification:

```gdscript
var camera_distance := camera.global_position.distance_to(world_point)
if camera_distance > 18.0:
	card_label.text = primary
```

- [ ] **Step 3.5: Run focused tests and verify green**

Run:

```powershell
python -m pytest -q backend/tests/test_actor_state_tags_static.py
```

Expected:

```text
PASS
```

- [ ] **Step 3.6: Commit**

```powershell
git add scripts/ui/ActorStateTags.gd backend/tests/test_actor_state_tags_static.py
git commit -m "Convert observatory actor tags into overhead cards

Constraint: Developer-only debug readability must improve without changing runtime authority
Rejected: Keep left-side actor summary block | character-bound information stays detached from the actor
Confidence: medium
Scope-risk: moderate
Directive: Keep overhead cards compact; do not turn them into full debug panels
Tested: python -m pytest -q backend/tests/test_actor_state_tags_static.py
Not-tested: Clustered runtime overlap behavior"
```

---

## Task 4: Convert CharacterObserverPanel Into The Right Detail Rail

**Files:**
- Modify:
  - `scripts/ui/CharacterObserverPanel.gd`
- Test:
  - `backend/tests/test_character_observer_panel_static.py`

- [ ] **Step 4.1: Move the panel to the right side and fix its size**

Set:

```gdscript
label.position = Vector2(980, 48)
label.size = Vector2(340, 420)
```

- [ ] **Step 4.2: Replace the old full dump with four compact sections**

Build:

```gdscript
label.text = "\n\n".join(
	[
		"看到了什么\n%s" % _compact_value(payload.get("perception_summary", ""), "暂无明显感知"),
		"怎么理解\n%s" % _compact_value(payload.get("interpretation_summary", ""), "暂无判断"),
		"准备做什么\n%s" % _compact_value(_resolve_action_summary(payload), "暂无执行"),
		"世界 / 司命反馈\n%s" % _compact_value(_resolve_feedback_summary(payload), "暂无反馈"),
	]
)
```

- [ ] **Step 4.3: Add compact value helpers so sections stay short**

Use:

```gdscript
func _compact_value(value: Variant, fallback: String) -> String:
	var text := str(value or "")
	if text.is_empty():
		return fallback
	if text.length() > 72:
		return "%s..." % text.substr(0, 72)
	return text
```

And:

```gdscript
func _resolve_action_summary(payload: Dictionary) -> String:
	var decision := str(payload.get("decision_summary", "") or "")
	var execution := str(payload.get("execution_summary", "") or "")
	if not execution.is_empty():
		return execution
	return decision

func _resolve_feedback_summary(payload: Dictionary) -> String:
	var outcome := str(payload.get("latest_outcome_summary", "") or "")
	var siming := str(payload.get("latest_siming_summary", "") or "")
	if not outcome.is_empty() and not siming.is_empty():
		return "%s | %s" % [outcome, siming]
	if not outcome.is_empty():
		return outcome
	return siming
```

- [ ] **Step 4.4: Run focused tests and verify green**

Run:

```powershell
python -m pytest -q backend/tests/test_character_observer_panel_static.py
```

Expected:

```text
PASS
```

- [ ] **Step 4.5: Commit**

```powershell
git add scripts/ui/CharacterObserverPanel.gd backend/tests/test_character_observer_panel_static.py
git commit -m "Refactor observatory observer panel into right detail rail

Constraint: Default debug mode must prioritize active playfield observation over exhaustive text
Rejected: Keep full thought-chain dump in default panel | too dense and overlaps other surfaces
Confidence: high
Scope-risk: narrow
Directive: Keep the right rail focused on the selected actor only
Tested: python -m pytest -q backend/tests/test_character_observer_panel_static.py
Not-tested: Runtime line wrapping aesthetics"
```

---

## Task 5: Convert WorldOutcomeTrace Into A Thin Bottom Strip

**Files:**
- Modify:
  - `scripts/ui/WorldOutcomeTrace.gd`
- Test:
  - `backend/tests/test_world_outcome_trace_static.py`

- [ ] **Step 5.1: Reposition and shrink the panel**

Set:

```gdscript
label.position = Vector2(24, 648)
label.size = Vector2(1290, 72)
```

- [ ] **Step 5.2: Render only the latest three merged entries**

Use:

```gdscript
var rows := state.get_latest_bottom_strip_entries()
```

Render:

```gdscript
for row in rows:
	lines.append("[%s] %s" % [
		str(row.get("type", "") or ""),
		str(row.get("summary", "") or "暂无摘要"),
	])
label.text = "最近 3 条\n%s" % "\n".join(lines)
```

- [ ] **Step 5.3: Keep it developer-only but default-observatory-visible**

Keep:

```gdscript
visible = bool(state.observatory_enabled)
```

Do not gate it behind director or script mode.

- [ ] **Step 5.4: Run focused tests and verify green**

Run:

```powershell
python -m pytest -q backend/tests/test_world_outcome_trace_static.py
```

Expected:

```text
PASS
```

- [ ] **Step 5.5: Commit**

```powershell
git add scripts/ui/WorldOutcomeTrace.gd backend/tests/test_world_outcome_trace_static.py
git commit -m "Convert observatory world trace into bottom event strip

Constraint: Default debug layout keeps a thin global context strip without blocking the scene
Rejected: Keep full-height outcome panel | wastes space and competes with actor observation
Confidence: high
Scope-risk: narrow
Directive: Keep strip content summary-only; deep inspection belongs in explicit replay panels
Tested: python -m pytest -q backend/tests/test_world_outcome_trace_static.py
Not-tested: Runtime color/contrast tuning"
```

---

## Task 6: Reposition Heavy Panels Behind Explicit Expanded Modes

**Files:**
- Modify:
  - `scripts/ui/DirectorMonitorPanel.gd`
  - `scripts/ui/SimingDirectorBoard.gd`
  - `scripts/ui/ScriptTimelinePanel.gd`
  - `scripts/ui/DialogueSceneLedger.gd`
- Test:
  - `backend/tests/test_director_monitor_panel_static.py`
  - `backend/tests/test_siming_director_board_static.py`
  - `backend/tests/test_script_timeline_panel_static.py`
  - `backend/tests/test_dialogue_scene_ledger_static.py`

- [ ] **Step 6.1: Reposition director-mode pair to the upper-right region**

Suggested:

```gdscript
# DirectorMonitorPanel.gd
label.position = Vector2(760, 48)
label.size = Vector2(560, 280)

# SimingDirectorBoard.gd
label.position = Vector2(760, 340)
label.size = Vector2(560, 180)
```

- [ ] **Step 6.2: Reposition script-mode pair to the lower-right review region**

Suggested:

```gdscript
# ScriptTimelinePanel.gd
label.position = Vector2(760, 48)
label.size = Vector2(560, 320)

# DialogueSceneLedger.gd
label.position = Vector2(760, 380)
label.size = Vector2(560, 240)
```

- [ ] **Step 6.3: Preserve mode gating and updated wording**

Ensure:

```gdscript
visible = bool(state.observatory_enabled and state.director_mode)
visible = bool(state.observatory_enabled and state.script_mode)
```

And keep:

```gdscript
"当前观察角色：%s"
```

- [ ] **Step 6.4: Run focused tests and verify green**

Run:

```powershell
python -m pytest -q backend/tests/test_director_monitor_panel_static.py backend/tests/test_siming_director_board_static.py backend/tests/test_script_timeline_panel_static.py backend/tests/test_dialogue_scene_ledger_static.py
```

Expected:

```text
PASS
```

- [ ] **Step 6.5: Commit**

```powershell
git add scripts/ui/DirectorMonitorPanel.gd scripts/ui/SimingDirectorBoard.gd scripts/ui/ScriptTimelinePanel.gd scripts/ui/DialogueSceneLedger.gd backend/tests/test_director_monitor_panel_static.py backend/tests/test_siming_director_board_static.py backend/tests/test_script_timeline_panel_static.py backend/tests/test_dialogue_scene_ledger_static.py
git commit -m "Gate heavy observatory panels behind explicit debug modes

Constraint: Deep audit surfaces remain available but must not dominate default testing layout
Rejected: Remove heavy panels entirely | would regress director/script inspection depth
Confidence: high
Scope-risk: moderate
Directive: Default mode is lightweight; expanded mode is deliberate
Tested: python -m pytest -q backend/tests/test_director_monitor_panel_static.py backend/tests/test_siming_director_board_static.py backend/tests/test_script_timeline_panel_static.py backend/tests/test_dialogue_scene_ledger_static.py
Not-tested: Runtime panel stacking order"
```

---

## Task 7: Verify Scene Wiring And Lightweight Default Behavior

**Files:**
- Inspect / lightly modify only if needed:
  - `scenes/phase0/ObservatoryRoot.tscn`
  - `backend/tests/test_observatory_scene_mount_static.py`

- [ ] **Step 7.1: Confirm `ObservatoryRoot` still mounts all observatory nodes**

Run:

```powershell
python -m pytest -q backend/tests/test_observatory_scene_mount_static.py
```

Expected:

```text
PASS
```

- [ ] **Step 7.2: If layering order causes issues, adjust node order in `ObservatoryRoot.tscn`**

Preserve all required nodes:

```text
CharacterDirectorState
ActorStateTags
RelationshipOverlay
CharacterObserverPanel
DirectorMonitorPanel
SimingDirectorBoard
ScriptTimelinePanel
DialogueSceneLedger
WorldOutcomeTrace
ObservatoryInputController
```

- [ ] **Step 7.3: Re-run mount static test**

Run:

```powershell
python -m pytest -q backend/tests/test_observatory_scene_mount_static.py
```

Expected:

```text
PASS
```

- [ ] **Step 7.4: Commit**

```powershell
git add scenes/phase0/ObservatoryRoot.tscn backend/tests/test_observatory_scene_mount_static.py
git commit -m "Preserve observatory scene wiring for lightweight layout

Constraint: MainDemo wiring must remain stable while UI responsibilities shift
Rejected: Introduce a second observatory root scene | unnecessary duplication
Confidence: high
Scope-risk: narrow
Directive: Keep scene wiring stable; refactor behavior in scripts first
Tested: python -m pytest -q backend/tests/test_observatory_scene_mount_static.py
Not-tested: In-editor node z-index visuals"
```

---

## Task 8: Full Verification And Runtime Sanity

**Files:**
- No required code changes
- Verification outputs under `.harness/verification/`

- [ ] **Step 8.1: Run all touched static observatory tests**

Run:

```powershell
python -m pytest -q backend/tests/test_actor_state_tags_static.py backend/tests/test_character_observer_panel_static.py backend/tests/test_world_outcome_trace_static.py backend/tests/test_director_monitor_panel_static.py backend/tests/test_script_timeline_panel_static.py backend/tests/test_dialogue_scene_ledger_static.py backend/tests/test_siming_director_board_static.py backend/tests/test_character_director_state_static.py backend/tests/test_observatory_scene_mount_static.py backend/tests/test_observatory_input_controller_static.py
```

Expected:

```text
PASS
```

- [ ] **Step 8.2: Run broader backend test verification**

Run:

```powershell
python -m pytest -v
```

Expected:

```text
PASS, or only pre-existing unrelated failures if any already exist on main
```

- [ ] **Step 8.3: Run Godot project verification**

Run:

```powershell
python scripts/verification/harness.py --profile godot-project
```

Expected:

```text
overall_godot_project_passed=True
```

- [ ] **Step 8.4: Run phase0 verification**

Run:

```powershell
python scripts/verification/harness.py --profile phase0
```

Expected:

```text
No new observatory layout regressions beyond any known pre-existing observatory population gaps
```

- [ ] **Step 8.5: Manual Godot runtime sanity check**

Verify interactively:

```text
1. F6 opens the lightweight default layout only
2. Overhead cards appear above actors
3. Selected actor gets the extra reason line
4. Right rail follows Tab-selected actor
5. Bottom strip shows only latest 3 entries
6. F7 reveals director-heavy surfaces
7. F9 reveals script-heavy surfaces
8. All observatory UI remains hidden by default until developer toggle
```

- [ ] **Step 8.6: Commit final verification-related adjustments**

```powershell
git add .
git commit -m "Finish lightweight observatory debug layout

Constraint: Observatory remains a developer-only testing surface, not player UI
Rejected: Preserve current overlapping default panel stack | fails active observation use case
Confidence: medium
Scope-risk: moderate
Directive: Any future observatory UI growth must protect playfield readability first
Tested: Focused observatory pytest suite, python -m pytest -v, godot-project harness, phase0 harness, manual Godot sanity check
Not-tested: Long-session runtime readability across every scene configuration"
```

---

## Spec Coverage Review

Spec requirement -> task mapping:

- developer-only / hidden-by-default -> Tasks 6 and 8
- overhead character cards -> Task 3
- right-side current-actor rail -> Task 4
- bottom thin strip with latest 3 -> Tasks 2 and 5
- heavy director/script surfaces behind explicit modes -> Task 6
- reuse existing observatory state and payloads -> Task 2
- no gameplay logic / authority change -> All tasks limit to UI/state helpers only

No uncovered spec requirement remains.

---

## Placeholder Scan

Checked for:

- `TODO`
- `TBD`
- “appropriate handling”
- “similar to”
- missing commands
- missing file paths

None intentionally remain.

---

## Type Consistency Review

- `get_selected_actor_label() -> String`
- `get_latest_script_beat_summaries(limit: int = 3) -> Array[String]`
- `get_latest_siming_summaries(limit: int = 3) -> Array[String]`
- `get_latest_bottom_strip_entries() -> Array[Dictionary]`

Names are reused consistently across tasks.

