# Character L4 Scene Expression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Stage 2 `L4` from a thin execution bridge into a visible basic-expression layer in the live Godot scene while preserving the shared actor ingress and current authority boundaries.

**Architecture:** Reuse the existing `CharacterAgentL4Executor`, `CharacterRuntimeState`, `CharacterPresentationInput`, `CharacterReplica`, and `KnightRoleSkin` path. Deepen the execution semantics by mapping Stage 2 intents and physiology/posture hints onto existing animation, role-state, focus, and spacing seams rather than introducing a new embodiment protocol.

**Tech Stack:** Python backend execution planner, Godot GDScript shared actor stack, pytest static/runtime checks, current verification probes.

---

### Task 1: Enrich backend L4 execution plans for Stage 2 visible semantics

**Files:**
- Modify: `backend/app/character_agent/execution/l4_executor.py`
- Modify: `backend/app/character_agent/execution/l4_adapter.py`
- Test: `backend/tests/test_character_agent_l4_execution.py`
- Test: `backend/tests/test_character_agent_execution_channels.py`

- [ ] **Step 1: Write failing backend execution tests**

```python
from app.character_agent.execution.l4_executor import CharacterAgentL4Executor
from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.models.character_agent_runtime import CharacterInterpretation, CharacterIntentDecision


def test_l4_executor_maps_stage2_withdraw_to_visible_spacing_and_posture() -> None:
    executor = CharacterAgentL4Executor()
    snapshot = CharacterPrivateWorldSnapshot(
        actor_id="char_a",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=10,
        updated_at=10,
        attention_targets=["char_b"],
        vigilance_level="elevated",
    )
    interpretation = CharacterInterpretation(
        actor_id="char_a",
        interpreted_summary="char_b is pressing too hard",
        interpretation_type="social_pressure",
        salience_score=0.8,
        ambiguity_level="low",
        risk_level="medium",
        opportunity_level="low",
        attention_target="char_b",
    )
    decision = CharacterIntentDecision(
        actor_id="char_a",
        selected_intent="withdraw",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale="maintain distance",
    )
    plan = executor.build_execution_plan(snapshot=snapshot, interpretation=interpretation, decision=decision)
    assert plan["social_spatial_channel"]["spacing_behavior"] == "increase_distance"
    assert plan["body_channel"]["posture"] in {"guarded", "attentive_guard"}
```

- [ ] **Step 2: Run backend L4 tests**

Run: `pytest backend/tests/test_character_agent_l4_execution.py backend/tests/test_character_agent_execution_channels.py -v`
Expected: FAIL or only weak coverage around visible spacing/posture semantics.

- [ ] **Step 3: Enrich execution-plan semantics**

```python
"body_channel": {
    "posture": posture,
    "gesture_hint": decision.selected_intent,
    "hesitation_hint": interpretation.ambiguity_level,
},
"social_spatial_channel": {
    "spacing_behavior": spacing_behavior,
    "target_ref": target,
    "orientation_mode": "hold_attention" if target else "hold",
},
"physiology_channel": {
    "breath": breath,
    "guarding": "elevated" if guarding_elevated else "low",
    "state_band": physiology_hint,
},
```

- [ ] **Step 4: Run backend L4 tests**

Run: `pytest backend/tests/test_character_agent_l4_execution.py backend/tests/test_character_agent_execution_channels.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/character_agent/execution/l4_executor.py backend/app/character_agent/execution/l4_adapter.py backend/tests/test_character_agent_l4_execution.py backend/tests/test_character_agent_execution_channels.py
git commit -m "Deepen L4 execution plans into visible Stage 2 semantics

Constraint: Stage 2 needs scene-visible intent semantics without full FACS/Binder rollout
Rejected: Introduce a new embodiment packet family outside current actor ingress | breaks shared actor contract
Confidence: medium
Scope-risk: moderate
Directive: Express richer Stage 2 semantics through current execution-plan shape before adding new channels
Tested: pytest backend/tests/test_character_agent_l4_execution.py backend/tests/test_character_agent_execution_channels.py -v
Not-tested: Godot runtime application of new fields"
```

### Task 2: Apply Stage 2 execution semantics in `CharacterRuntimeState` and `CharacterReplica`

**Files:**
- Modify: `scripts/character/CharacterRuntimeState.gd`
- Modify: `scripts/character/CharacterReplica.gd`
- Test: `backend/tests/test_character_runtime_state_extraction_static.py`
- Test: `backend/tests/test_character_actor_bridge_static.py`

- [ ] **Step 1: Write failing actor-ingress tests**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_runtime_state_reads_physiology_and_focus_from_execution_plan() -> None:
    source = (ROOT / "scripts" / "character" / "CharacterRuntimeState.gd").read_text(encoding="utf-8")
    assert "CharacterPresentationInputRef.get_physiology_hint(agent_presentation_input)" in source
    assert "resolve_focus_target_lookup" in source


def test_character_replica_applies_execution_side_effects_from_runtime_state() -> None:
    source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(encoding="utf-8")
    assert "runtime_state.get_execution_side_effect_role_state_effects" in source
    assert "runtime_state.get_execution_side_effect_physiology_hint" in source
```

- [ ] **Step 2: Run tests**

Run: `pytest backend/tests/test_character_runtime_state_extraction_static.py backend/tests/test_character_actor_bridge_static.py -v`
Expected: FAIL after new backend L4 semantics are added but not yet consumed here.

- [ ] **Step 3: Extend runtime-state side-effect mapping**

```gdscript
func build_agent_execution_side_effect_plan(
	dialogue_role_state: String,
	interaction_role_state: String,
	focus_role_state: String,
	attention_role_state: String,
) -> Dictionary:
	return {
		"focus_target_lookup": resolve_focus_target_lookup(CharacterPresentationInputRef.get_focus_target_id(agent_presentation_input)),
		"physiology_hint": CharacterPresentationInputRef.get_physiology_hint(agent_presentation_input),
		"role_state_effects": build_agent_role_state_effects(
			dialogue_role_state,
			interaction_role_state,
			focus_role_state,
			attention_role_state,
		),
		"active_command_type": CharacterPresentationInputRef.get_active_command_type(agent_presentation_input),
	}
```

- [ ] **Step 4: Extend `CharacterReplica` application**

```gdscript
var physiology_hint: String = runtime_state.get_execution_side_effect_physiology_hint(execution_side_effect_plan)
if not physiology_hint.is_empty():
	_emit_physiology_state_fact(physiology_hint)

for effect: Dictionary in runtime_state.get_execution_side_effect_role_state_effects(execution_side_effect_plan):
	var state_name: String = runtime_state.get_role_state_effect_name(effect)
	if not state_name.is_empty():
		_trigger_role_state(state_name, hold_duration)
```

- [ ] **Step 5: Run static actor-ingress tests**

Run: `pytest backend/tests/test_character_runtime_state_extraction_static.py backend/tests/test_character_actor_bridge_static.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/character/CharacterRuntimeState.gd scripts/character/CharacterReplica.gd backend/tests/test_character_runtime_state_extraction_static.py backend/tests/test_character_actor_bridge_static.py
git commit -m "Apply Stage 2 execution semantics through shared actor ingress

Constraint: Stage 2 must keep CharacterRuntimeState and CharacterReplica as the one local execution ingress family
Rejected: Apply new semantics directly in BackendBridge or scene nodes | bypasses actor runtime boundary
Confidence: medium
Scope-risk: moderate
Directive: New L4 semantics must remain readable as runtime-state-driven side effects
Tested: pytest backend/tests/test_character_runtime_state_extraction_static.py backend/tests/test_character_actor_bridge_static.py -v
Not-tested: live Godot scene"
```

### Task 3: Surface visible minimal expression in `KnightRoleSkin` and runtime verification

**Files:**
- Modify: `scripts/character/KnightRoleSkin.gd`
- Modify: `scripts/verification/CharacterAgentExecutionProbe.gd`
- Modify: `scripts/verification/verify_character_agent_execution.py`
- Test: `backend/tests/test_character_final_actor_contracts_static.py`
- Test: `scripts/verification/tests/test_character_agent_execution_probe_static.py`

- [ ] **Step 1: Write failing presentation-contract tests**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_knight_role_skin_reads_stage2_action_and_physiology_contracts() -> None:
    source = (ROOT / "scripts" / "character" / "KnightRoleSkin.gd").read_text(encoding="utf-8")
    assert "CharacterPresentationInputRef.get_requested_action(current_presentation_contract)" in source
    assert "CharacterPresentationInputRef.get_active_command_type(current_presentation_contract)" in source
```

- [ ] **Step 2: Run focused tests**

Run: `pytest backend/tests/test_character_final_actor_contracts_static.py scripts/verification/tests/test_character_agent_execution_probe_static.py -v`
Expected: FAIL if `KnightRoleSkin` does not yet visibly respond to new Stage 2 contract semantics.

- [ ] **Step 3: Add minimal visible mapping in role skin**

```gdscript
func apply_presentation_input(next_input: Dictionary) -> void:
	current_presentation_contract = CharacterPresentationInputRef.normalize(next_input)
	...
	var requested_action := CharacterPresentationInputRef.get_requested_action(current_presentation_contract)
	var active_command_type := CharacterPresentationInputRef.get_active_command_type(current_presentation_contract)
	var equipment_gait_hint := CharacterPresentationInputRef.get_equipment_gait_hint(current_presentation_contract)
	if not requested_action.is_empty():
		presentation_gait = CharacterPresentationInputRef.get_action_gait_hint(current_presentation_contract, presentation_gait)
	elif not active_command_type.is_empty() and not focus_target_id.is_empty():
		presentation_gait = CharacterPresentationInputRef.get_action_gait_hint(current_presentation_contract, presentation_gait)
	elif not equipment_gait_hint.is_empty():
		presentation_gait = equipment_gait_hint
```

- [ ] **Step 4: Extend probe expectations**

```gdscript
const EXECUTION_PAYLOAD_DIRECT_MARKER := "character_agent_execution_probe:execution_payload_direct=true"
const CONSUMER_SEEN_MARKER := "character_agent_execution_probe:consumer_seen=true"
```

Expected verification addition: prove the runtime still consumes the execution contract after the richer Stage 2 semantics land.

- [ ] **Step 5: Run static and probe verification**

Run:
`pytest backend/tests/test_character_final_actor_contracts_static.py scripts/verification/tests/test_character_agent_execution_probe_static.py -v`

Then:
`python scripts/verification/verify_character_agent_execution.py`

Expected: PASS and report still shows `overall_character_agent_execution_passed=True`.

- [ ] **Step 6: Commit**

```bash
git add scripts/character/KnightRoleSkin.gd scripts/verification/CharacterAgentExecutionProbe.gd scripts/verification/verify_character_agent_execution.py backend/tests/test_character_final_actor_contracts_static.py scripts/verification/tests/test_character_agent_execution_probe_static.py
git commit -m "Verify Stage 2 visible expression through shared scene contracts

Constraint: Stage 2 must remain visible in the live scene without full embodiment-chain expansion
Rejected: Declare Stage 2 done from backend tests alone | misses the actual 3D expression requirement
Confidence: medium
Scope-risk: moderate
Directive: Keep runtime proof tied to the shared character-agent execution contract
Tested: pytest backend/tests/test_character_final_actor_contracts_static.py scripts/verification/tests/test_character_agent_execution_probe_static.py -v; python scripts/verification/verify_character_agent_execution.py
Not-tested: full broad phase0 profile after all plans land"
```
