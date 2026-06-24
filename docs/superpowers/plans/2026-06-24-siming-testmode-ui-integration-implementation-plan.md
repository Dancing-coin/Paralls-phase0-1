# Siming Testmode UI Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate merged mainline `Siming` runtime signals cleanly into the current developer/test-mode UI so autotest, focus-autotest, observatory default layout, and expanded director/script surfaces can all verify `Siming` influence as part of the live dramatic loop.

**Architecture:** Reuse the current observatory stack (`CharacterDirectorState`, `ObservatoryRoot`, `SimingDirectorBoard`, `CharacterObserverPanel`, `WorldOutcomeTrace`, `ScriptTimelinePanel`, `DialogueSceneLedger`) and the existing `MainDemoController` autotest/focus-autotest entrypoints. Do not add a parallel debug UI. Instead, deepen the current UI so merged `Siming` data is visible in the lightweight default layout, explorable in expanded debug modes, and provable through the current verification probes.

**Tech Stack:** Godot 4.6 GDScript, current `MainDemo.tscn` / `ObservatoryRoot.tscn`, merged `Siming` backend observatory payloads, pytest static tests, Godot/runtime verification scripts.

---

## File Structure

### Existing files to modify

- `scripts/ui/CharacterDirectorState.gd`
  - keep as the one UI-state center
  - extend helper surfaces for merged `Siming` summaries, actor-targeted `Siming` influence, and autotest-readable rows

- `scripts/ui/CharacterObserverPanel.gd`
  - show the currently observed actor’s latest `Siming` pressure/catalyst impact clearly in the right-side rail

- `scripts/ui/ActorStateTags.gd`
  - surface a compact `Siming` influence line or badge in overhead actor cards when a role is under active `Siming` influence

- `scripts/ui/WorldOutcomeTrace.gd`
  - ensure bottom strip merges latest `Siming` summaries cleanly with world/script events

- `scripts/ui/SimingDirectorBoard.gd`
  - upgrade from “latest snapshot dump” to a test-readable director station that exposes path, target, band, no-action reason, and downstream status coherently

- `scripts/ui/DirectorMonitorPanel.gd`
  - include explicit `Siming`-to-role influence summaries when in director mode

- `scripts/ui/ScriptTimelinePanel.gd`
  - carry `Siming` summaries into dramatic-beat rows in a way that is easy to verify from probes

- `scripts/ui/DialogueSceneLedger.gd`
  - expose whether nearby dialogue rows were under `Siming`-driven attention/pressure context

- `scripts/phase0/MainDemoController.gd`
  - ensure autotest/focus-autotest and observatory actor switching keep `Siming` UI readable during test runs

- `scripts/verification/CharacterDirectorObservatoryProbe.gd`
  - extend observatory proof so it explicitly checks `Siming` presence in both lightweight and expanded surfaces

- `scripts/verification/verify_character_director_observatory.py`
- `scripts/verification/verify_phase0.py`
  - treat stronger `Siming` UI evidence as first-class verification truth

### Existing tests to modify

- `backend/tests/test_character_director_state_static.py`
- `backend/tests/test_character_observer_panel_static.py`
- `backend/tests/test_actor_state_tags_static.py`
- `backend/tests/test_world_outcome_trace_static.py`
- `backend/tests/test_director_monitor_panel_static.py`
- `backend/tests/test_script_timeline_panel_static.py`
- `backend/tests/test_dialogue_scene_ledger_static.py`
- `backend/tests/test_siming_director_board_static.py`
- `backend/tests/test_verification_audit.py`
- `scripts/verification/tests/test_character_agent_execution_verify.py` only if report wording changes

---

### Task 1: Freeze Siming testmode UI contracts with static tests

**Files:**
- Modify:
  - `backend/tests/test_character_director_state_static.py`
  - `backend/tests/test_character_observer_panel_static.py`
  - `backend/tests/test_actor_state_tags_static.py`
  - `backend/tests/test_world_outcome_trace_static.py`
  - `backend/tests/test_director_monitor_panel_static.py`
  - `backend/tests/test_script_timeline_panel_static.py`
  - `backend/tests/test_dialogue_scene_ledger_static.py`
  - `backend/tests/test_siming_director_board_static.py`

- [ ] **Step 1: Write failing tests for state-center Siming helpers**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_character_director_state_exposes_siming_summary_helpers() -> None:
    source = (ROOT / "scripts" / "ui" / "CharacterDirectorState.gd").read_text(encoding="utf-8")
    assert "func get_latest_siming_summaries(limit: int = 3) -> Array[String]:" in source
    assert "func get_latest_bottom_strip_entries() -> Array[Dictionary]:" in source
    assert "func get_recent_siming_events() -> Array[Dictionary]:" in source
```

- [ ] **Step 2: Write failing tests for actor-local Siming visibility**

```python
def test_actor_state_tags_mentions_siming_influence_when_present() -> None:
    source = (ROOT / "scripts" / "ui" / "ActorStateTags.gd").read_text(encoding="utf-8")
    assert "司命影响" in source
```

- [ ] **Step 3: Write failing tests for selected-actor rail Siming feedback**

```python
def test_character_observer_panel_has_world_and_siming_feedback_section() -> None:
    source = (ROOT / "scripts" / "ui" / "CharacterObserverPanel.gd").read_text(encoding="utf-8")
    assert "世界 / 司命反馈" in source
    assert "latest_siming_summary" in source
```

- [ ] **Step 4: Write failing tests for thin bottom strip Siming rows**

```python
def test_world_outcome_trace_bottom_strip_keeps_siming_rows() -> None:
    source = (ROOT / "scripts" / "ui" / "WorldOutcomeTrace.gd").read_text(encoding="utf-8")
    assert "司命" in source
    assert "get_latest_bottom_strip_entries" in source
```

- [ ] **Step 5: Write failing tests for expanded director/script surfaces**

```python
def test_siming_director_board_stays_a_first_class_director_surface() -> None:
    source = (ROOT / "scripts" / "ui" / "SimingDirectorBoard.gd").read_text(encoding="utf-8")
    assert "司命为什么这么做" in source
    assert "司命这步现在走到哪了" in source


def test_script_timeline_mentions_siming_summaries() -> None:
    source = (ROOT / "scripts" / "ui" / "ScriptTimelinePanel.gd").read_text(encoding="utf-8")
    assert "司命侧摘要" in source


def test_dialogue_ledger_mentions_siming_alignment_context() -> None:
    source = (ROOT / "scripts" / "ui" / "DialogueSceneLedger.gd").read_text(encoding="utf-8")
    assert "司命" in source
```

- [ ] **Step 6: Run focused static tests**

Run:

```powershell
python -m pytest -q backend/tests/test_character_director_state_static.py backend/tests/test_character_observer_panel_static.py backend/tests/test_actor_state_tags_static.py backend/tests/test_world_outcome_trace_static.py backend/tests/test_director_monitor_panel_static.py backend/tests/test_script_timeline_panel_static.py backend/tests/test_dialogue_scene_ledger_static.py backend/tests/test_siming_director_board_static.py
```

Expected:

```text
FAIL with missing Siming UI strings/helpers where the current UI is still too thin
```

- [ ] **Step 7: Commit**

```powershell
git add backend/tests/test_character_director_state_static.py backend/tests/test_character_observer_panel_static.py backend/tests/test_actor_state_tags_static.py backend/tests/test_world_outcome_trace_static.py backend/tests/test_director_monitor_panel_static.py backend/tests/test_script_timeline_panel_static.py backend/tests/test_dialogue_scene_ledger_static.py backend/tests/test_siming_director_board_static.py
git commit -m "Lock Siming testmode UI integration contracts

Constraint: Siming UI must stay inside the current observatory/testmode surfaces
Rejected: Create a separate Siming-only debug HUD | duplicates state and fragments verification
Confidence: high
Scope-risk: moderate
Directive: Keep Siming visibility layered across lightweight and expanded debug surfaces
Tested: Focused static Siming UI contract tests (expected red)
Not-tested: Godot runtime behavior"
```

### Task 2: Strengthen `CharacterDirectorState` as the one Siming UI state center

**Files:**
- Modify: `scripts/ui/CharacterDirectorState.gd`
- Test: `backend/tests/test_character_director_state_static.py`

- [ ] **Step 1: Add helper APIs for actor-targeted Siming summaries**

```gdscript
func get_selected_actor_latest_siming_summary() -> String:
	var actor_state: Dictionary = get_selected_actor_state()
	return str(actor_state.get("latest_siming_summary", "") or "")


func get_selected_actor_recent_siming_reasons(limit: int = 2) -> Array[String]:
	var rows: Array[String] = []
	for event in get_recent_siming_events():
		var target_ref := str(event.get("target_ref", "") or "")
		if target_ref == selected_actor_id:
			rows.append(str(event.get("reason_summary", "") or event.get("summary", "") or ""))
	if rows.size() > limit:
		rows = rows.slice(rows.size() - limit, rows.size())
	return rows
```

- [ ] **Step 2: Add merged bottom-strip builder that preserves `Siming` ordering**

```gdscript
func get_latest_bottom_strip_entries() -> Array[Dictionary]:
	var rows: Array[Dictionary] = []
	# keep current world + siming + script merge
	# preserve descending producer_ts ordering
	# cap to three rows
```

- [ ] **Step 3: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_character_director_state_static.py
```

Expected:

```text
PASS
```

- [ ] **Step 4: Commit**

```powershell
git add scripts/ui/CharacterDirectorState.gd backend/tests/test_character_director_state_static.py
git commit -m "Deepen observatory state helpers for Siming testmode visibility

Constraint: Siming UI must reuse the existing observatory state center
Rejected: Let each panel recalculate Siming summaries independently | causes drift and verification mismatch
Confidence: high
Scope-risk: narrow
Directive: Keep Siming helpers presentation-oriented and side-effect free
Tested: python -m pytest -q backend/tests/test_character_director_state_static.py
Not-tested: runtime panel formatting"
```

### Task 3: Surface Siming influence in lightweight default layout

**Files:**
- Modify:
  - `scripts/ui/ActorStateTags.gd`
  - `scripts/ui/CharacterObserverPanel.gd`
  - `scripts/ui/WorldOutcomeTrace.gd`
- Test:
  - `backend/tests/test_actor_state_tags_static.py`
  - `backend/tests/test_character_observer_panel_static.py`
  - `backend/tests/test_world_outcome_trace_static.py`

- [ ] **Step 1: Add compact Siming influence line to overhead actor cards**

```gdscript
func _build_reason_line(payload: Dictionary) -> String:
	var siming_summary := str(payload.get("latest_siming_summary", "") or "")
	if siming_summary.is_empty():
		return "原因摘要：%s" % str(payload.get("why_now_summary", "") or "暂无")
	return "原因摘要：%s | 司命影响：%s" % [
		str(payload.get("why_now_summary", "") or "暂无"),
		siming_summary,
	]
```

- [ ] **Step 2: Expand selected-actor rail feedback section**

```gdscript
func _resolve_feedback_summary(payload: Dictionary) -> String:
	var outcome := str(payload.get("latest_outcome_summary", "") or "")
	var siming := str(payload.get("latest_siming_summary", "") or "")
	if not outcome.is_empty() and not siming.is_empty():
		return "%s | %s" % [outcome, siming]
	if not outcome.is_empty():
		return outcome
	return siming
```

- [ ] **Step 3: Keep bottom strip Siming rows concise and top-ranked by recency**

```gdscript
label.text = "最近 3 条\n%s" % "\n".join(lines)
# lines may contain [世界], [司命], [节拍]
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_actor_state_tags_static.py backend/tests/test_character_observer_panel_static.py backend/tests/test_world_outcome_trace_static.py
```

Expected:

```text
PASS
```

- [ ] **Step 5: Commit**

```powershell
git add scripts/ui/ActorStateTags.gd scripts/ui/CharacterObserverPanel.gd scripts/ui/WorldOutcomeTrace.gd backend/tests/test_actor_state_tags_static.py backend/tests/test_character_observer_panel_static.py backend/tests/test_world_outcome_trace_static.py
git commit -m "Show Siming influence in the lightweight observatory layout

Constraint: Default testmode layout must keep Siming legible without overwhelming the playfield
Rejected: Reserve Siming for director mode only | hides active catalyst effects during movement/testing
Confidence: medium
Scope-risk: moderate
Directive: Keep lightweight Siming summaries one-line and actor-centric
Tested: python -m pytest -q backend/tests/test_actor_state_tags_static.py backend/tests/test_character_observer_panel_static.py backend/tests/test_world_outcome_trace_static.py
Not-tested: clustered runtime readability"
```

### Task 4: Deepen expanded director/script surfaces for Siming verification

**Files:**
- Modify:
  - `scripts/ui/SimingDirectorBoard.gd`
  - `scripts/ui/DirectorMonitorPanel.gd`
  - `scripts/ui/ScriptTimelinePanel.gd`
  - `scripts/ui/DialogueSceneLedger.gd`
- Test:
  - `backend/tests/test_siming_director_board_static.py`
  - `backend/tests/test_director_monitor_panel_static.py`
  - `backend/tests/test_script_timeline_panel_static.py`
  - `backend/tests/test_dialogue_scene_ledger_static.py`

- [ ] **Step 1: Keep `SimingDirectorBoard` as a first-class director station**

```gdscript
func _build_director_rows(payload: Dictionary) -> Array[String]:
	return [
		"司命现在看到的公平问题：%s" % ...,
		"司命正在考虑的出手方案：%s" % ...,
		"司命最后怎么决定：%s" % ...,
		"司命走的是哪条路：%s" % ...,
		"司命这次出手属于哪一类：%s" % ...,
		"司命盯上的对象是：%s" % ...,
		"司命为什么这么做：%s" % ...,
		"司命这步现在走到哪了：%s" % ...,
	]
```

- [ ] **Step 2: Add Siming influence summary to director monitor**

```gdscript
var siming_lines: Array[String] = []
if siming_board and siming_board.has_method("_build_director_rows"):
	siming_lines = siming_board._build_director_rows(state.call("get_latest_siming_state"))
```

- [ ] **Step 3: Thread Siming summaries into script surfaces**

```gdscript
"司命侧摘要=%s" % JSON.stringify(beat.get("siming_summaries", []))
```

and add ledger-side mention of whether the pairwise exchange sits under active Siming pressure.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
python -m pytest -q backend/tests/test_siming_director_board_static.py backend/tests/test_director_monitor_panel_static.py backend/tests/test_script_timeline_panel_static.py backend/tests/test_dialogue_scene_ledger_static.py
```

Expected:

```text
PASS
```

- [ ] **Step 5: Commit**

```powershell
git add scripts/ui/SimingDirectorBoard.gd scripts/ui/DirectorMonitorPanel.gd scripts/ui/ScriptTimelinePanel.gd scripts/ui/DialogueSceneLedger.gd backend/tests/test_siming_director_board_static.py backend/tests/test_director_monitor_panel_static.py backend/tests/test_script_timeline_panel_static.py backend/tests/test_dialogue_scene_ledger_static.py
git commit -m "Deepen expanded observatory surfaces for Siming verification

Constraint: Expanded modes must remain the authoritative deep-inspection surfaces for Siming
Rejected: Collapse all Siming detail into the lightweight default layout | loses deliberate debug hierarchy
Confidence: high
Scope-risk: moderate
Directive: Keep director/script mode semantics distinct even when both expose Siming context
Tested: python -m pytest -q backend/tests/test_siming_director_board_static.py backend/tests/test_director_monitor_panel_static.py backend/tests/test_script_timeline_panel_static.py backend/tests/test_dialogue_scene_ledger_static.py
Not-tested: multi-panel runtime overlap"
```

### Task 5: Align autotest/focus-autotest flow and verification probes with stronger Siming UI evidence

**Files:**
- Modify:
  - `scripts/phase0/MainDemoController.gd`
  - `scripts/verification/CharacterDirectorObservatoryProbe.gd`
  - `scripts/verification/verify_character_director_observatory.py`
  - `scripts/verification/verify_phase0.py`
  - `backend/app/verification_audit.py`
- Test:
  - `backend/tests/test_verification_audit.py`
  - `scripts/verification/tests/test_character_agent_execution_verify.py` if needed

- [ ] **Step 1: Add failing verification expectations**

```python
def test_verification_audit_accepts_siming_ui_presence_in_observatory() -> None:
    # extend current observatory proof expectations to require Siming payloads
    ...
```

Expected new proof surface:
- selected actor UI can show latest Siming summary
- director workstation contains populated Siming rows
- bottom strip can include Siming row

- [ ] **Step 2: Ensure `MainDemoController` keeps observatory actor sync readable during focus-autotest**

```gdscript
func _sync_observatory_view_actor() -> void:
	observatory_view_actor_id = "char_c"
	...
```

Expected behavior: test runs do not accidentally hide `Siming` context behind a stale selected actor.

- [ ] **Step 3: Extend observatory probe markers**

```gdscript
const DIRECTOR_CAST_WORLD_SIMING_OK_MARKER := "character_director_observatory_probe:director_cast_world_siming_populated=true"
```

Add checks that:
- selected actor state has Siming summary when expected
- director board and script timeline both contain Siming content

- [ ] **Step 4: Run focused verification tests**

Run:

```powershell
python -m pytest -q backend/tests/test_verification_audit.py
python scripts/verification/verify_character_director_observatory.py
```

Expected:

```text
PASS and observatory report remains green with stronger Siming evidence
```

- [ ] **Step 5: Run broader runtime verification**

Run:

```powershell
python scripts/verification/harness.py --profile phase0
```

Expected:

```text
overall_strict_phase0_passed=True
```

- [ ] **Step 6: Commit**

```powershell
git add scripts/phase0/MainDemoController.gd scripts/verification/CharacterDirectorObservatoryProbe.gd scripts/verification/verify_character_director_observatory.py scripts/verification/verify_phase0.py backend/app/verification_audit.py backend/tests/test_verification_audit.py
git commit -m "Align testmode verification with stronger Siming observatory evidence

Constraint: Siming UI integration is only complete when test/autotest verification can prove it
Rejected: Treat Siming UI as manual-only debug polish | leaves no durable evidence path
Confidence: medium
Scope-risk: moderate
Directive: Keep Siming verification tied to current observatory and phase0 proof surfaces
Tested: python -m pytest -q backend/tests/test_verification_audit.py; python scripts/verification/verify_character_director_observatory.py; python scripts/verification/harness.py --profile phase0
Not-tested: very long runtime sessions"
```

### Task 6: Final integration verification

**Files:**
- No required code changes

- [ ] **Step 1: Run the full focused UI/static suite**

Run:

```powershell
python -m pytest -q backend/tests/test_character_director_state_static.py backend/tests/test_character_observer_panel_static.py backend/tests/test_actor_state_tags_static.py backend/tests/test_world_outcome_trace_static.py backend/tests/test_director_monitor_panel_static.py backend/tests/test_script_timeline_panel_static.py backend/tests/test_dialogue_scene_ledger_static.py backend/tests/test_siming_director_board_static.py backend/tests/test_verification_audit.py
```

Expected:

```text
PASS
```

- [ ] **Step 2: Run broad backend verification**

Run:

```powershell
python -m pytest -v
```

Expected:

```text
PASS or only unrelated pre-existing failures if already present
```

- [ ] **Step 3: Run Godot/runtime verification**

Run:

```powershell
python scripts/verification/harness.py --profile godot-project
python scripts/verification/harness.py --profile phase0
python scripts/verification/verify_character_director_observatory.py
```

Expected:

```text
overall_godot_project_passed=True
overall_strict_phase0_passed=True
overall_character_director_observatory_passed=True
```

- [ ] **Step 4: Manual sanity check**

Verify:

```text
1. default lightweight debug layout shows Siming in the bottom strip when present
2. selected actor rail shows latest Siming summary when relevant
3. actor overhead card can surface a compact Siming influence line
4. director mode shows populated Siming station rows
5. script mode shows Siming summaries in beat-oriented review
6. focus-autotest / autotest runs do not leave Siming UI empty when backend emitted relevant Siming events
```

- [ ] **Step 5: Commit final polish if needed**

```powershell
git add .
git commit -m "Finish Siming integration across testmode observatory UI

Constraint: Siming must be visible in the same developer/test surfaces already used to verify actor behavior
Rejected: Keep Siming only as backend truth and not UI-verifiable | breaks practical runtime inspection
Confidence: medium
Scope-risk: moderate
Directive: Any future testmode UI change must preserve Siming visibility across lightweight and expanded modes
Tested: Focused static UI suite, python -m pytest -v, godot-project harness, phase0 harness, observatory verifier, manual runtime sanity check
Not-tested: alternative scene layouts beyond current MainDemo"
```
