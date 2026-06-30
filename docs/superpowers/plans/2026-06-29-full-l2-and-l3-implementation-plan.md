# Full L2 And L3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current partial interpretation and narrow planning stack into a complete character mind cognition layer with belief updates, higher-order reasoning, broad action-space generation, and unified control arbitration.

**Architecture:** This plan assumes the foundation and five-pool memory work are landed first. `L2` becomes a cognition update engine rather than a summary service; `L3` becomes a true action-possibility-space manager rather than a narrow demo-first selector. Execution remains light but the mind contract becomes complete and embodiment-ready.

**Tech Stack:** Python, model gateway, current runtime loop, pytest, Pydantic.

---

### Task 1: Turn `L2` into a full cognition-update layer

**Files:**
- Modify: `backend/app/character_agent/reasoning/l2_reasoner.py`
- Modify: `backend/app/models/character_agent_runtime.py`
- Modify: `backend/app/character_agent/gateway/prompt_policy.py`
- Test: `backend/tests/test_character_agent_l2_reasoning.py`
- Test: `backend/tests/test_character_agent_cognition_writeback.py`

- [ ] **Step 1: Write the failing cognition-update tests**

```python
from app.services.character_agent_l2 import CharacterAgentL2Service


def test_l2_returns_belief_social_higher_order_and_dynamic_deltas() -> None:
    service = CharacterAgentL2Service()
    output = service.map_reasoning_output(
        actor_id="char_a",
        output={
            "interpreted_summary": "char_b is probing",
            "interpretation_type": "social_signal",
            "salience_score": 0.8,
            "ambiguity_level": "medium",
            "risk_level": "medium",
            "opportunity_level": "low",
            "attention_target": "char_b",
            "inner_prompt_candidate": "stay guarded",
            "belief_deltas": [{"proposition_key": "char_b:is_probing", "state": "suspected"}],
            "social_deltas": [{"entity_id": "char_b", "suspicion_baseline": 0.8}],
            "higher_order_deltas": [{"subject_actor_id": "char_b", "meta_belief": "char_b suspects char_c knows more"}],
            "dynamic_state_delta": {"social_pressure": 0.7},
        },
    )
    assert output.belief_deltas[0]["proposition_key"] == "char_b:is_probing"
    assert output.dynamic_state_delta["social_pressure"] == 0.7
```

- [ ] **Step 2: Run the focused test to verify failure**

Run: `pytest backend/tests/test_character_agent_l2_reasoning.py::test_l2_returns_belief_social_higher_order_and_dynamic_deltas -v`
Expected: `FAIL` because the current interpretation model does not expose these fields.

- [ ] **Step 3: Extend the structured `L2` output shape**

```python
belief_deltas: list[dict[str, object]] = Field(default_factory=list)
social_deltas: list[dict[str, object]] = Field(default_factory=list)
higher_order_deltas: list[dict[str, object]] = Field(default_factory=list)
dynamic_state_delta: dict[str, float] = Field(default_factory=dict)
reasoning_trace_summary: str | None = None
```

Thread the same fields through:

- output validator defaults
- prompt required keys
- `CharacterAgentL2Service.map_reasoning_output(...)`

- [ ] **Step 4: Add `L2` writeback application hooks**

```python
def apply_cognition_update(
    self,
    *,
    actor_id: str,
    interpretation: CharacterInterpretation,
) -> None:
    for delta in interpretation.belief_deltas:
        ...
    for delta in interpretation.social_deltas:
        ...
    for delta in interpretation.higher_order_deltas:
        ...
    if interpretation.dynamic_state_delta:
        ...
```

Wire this into the runtime immediately after interpretation is produced, before `L3` planning runs.

- [ ] **Step 5: Run the `L2` suites**

Run: `pytest backend/tests/test_character_agent_l2_reasoning.py backend/tests/test_character_agent_cognition_writeback.py -v`
Expected: `PASS`

- [ ] **Step 6: Commit**

```bash
git add backend/app/character_agent/reasoning/l2_reasoner.py backend/app/models/character_agent_runtime.py backend/app/character_agent/gateway/prompt_policy.py backend/tests/test_character_agent_l2_reasoning.py backend/tests/test_character_agent_cognition_writeback.py
git commit -m "Upgrade L2 into a cognition update layer

Constraint: Complete mind core requires L2 to update belief, social, higher-order, and dynamic state rather than only summarize events
Rejected: Keep L2 as a passive interpretation shell | leaves memory archival and blocks full planning
Confidence: medium
Scope-risk: broad
Directive: Any new reasoning field must either affect downstream planning or be removed as dead narrative metadata
Tested: pytest backend/tests/test_character_agent_l2_reasoning.py backend/tests/test_character_agent_cognition_writeback.py -v
Not-tested: Godot runtime observability"
```

### Task 2: Expand `L3` into a true action-possibility-space manager

**Files:**
- Modify: `backend/app/character_agent/planning/l3_planner.py`
- Modify: `backend/app/character_agent/planning/triple_filter.py`
- Test: `backend/tests/test_character_agent_l3_planning.py`
- Test: `backend/tests/test_character_agent_triple_filter.py`
- Test: `backend/tests/test_character_agent_control_modes.py`

- [ ] **Step 1: Write the failing broad-candidate test**

```python
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.models.character_agent_runtime import CharacterInterpretation


def test_l3_candidate_generation_supports_broad_role_action_space() -> None:
    planner = CharacterAgentL3Service()
    plan = planner.build_intent_plan(
        interpretation=CharacterInterpretation(
            actor_id="char_a",
            interpreted_summary="char_b may be testing whether the letter can be exposed",
            interpretation_type="social_signal",
            salience_score=0.82,
            ambiguity_level="medium",
            risk_level="medium",
            opportunity_level="medium",
            attention_target="char_b",
            inner_prompt_candidate="preserve optionality",
        ),
        control_mode="agent_full_auto",
    )
    assert "withhold" in plan["candidates"]
    assert "seek_private_distance" in plan["candidates"]
    assert "break_contact" in plan["candidates"]
    assert "pause" in plan["candidates"]
    assert "defer" in plan["candidates"]
```

- [ ] **Step 2: Run the targeted test to verify failure**

Run: `pytest backend/tests/test_character_agent_l3_planning.py::test_l3_candidate_generation_supports_broad_role_action_space -v`
Expected: `FAIL` because the current candidate generator is still narrow.

- [ ] **Step 3: Broaden candidate generation and selection mapping**

```python
candidates = [
    "observe",
    "inspect_object",
    "self_protect",
    "pause",
    "defer",
    "withhold",
]
if interpretation.attention_target:
    candidates.extend(
        [
            "ask_probe",
            "share_info",
            "speak_private",
            "follow_target",
            "seek_private_distance",
            "break_contact",
            "withdraw",
            "approach",
        ]
    )
if interpretation.opportunity_level in {"medium", "high"}:
    candidates.append("speak_public")
```

Extend `_map_candidate_to_intent(...)` and scoring rules so the new candidates survive beyond generation.

- [ ] **Step 4: Make filter logic consume higher-order and dynamic-state inputs**

```python
higher_order_memories = self._list_entries(memory_bundle.get("higher_order_memories"))
dynamic_state = self._dict_entry(working_memory_state.get("dynamic_state"))

if candidate == "share_info" and dynamic_state.get("masking_pressure", 0.0) >= 0.7:
    notes.append("high masking pressure suppresses disclosure")

if candidate == "ask_probe" and any(
    entry.get("subject_actor_id") == attention_target for entry in higher_order_memories
):
    score += 0.09
```

- [ ] **Step 5: Run the planning and control suites**

Run: `pytest backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_agent_triple_filter.py backend/tests/test_character_agent_control_modes.py -v`
Expected: `PASS`

- [ ] **Step 6: Commit**

```bash
git add backend/app/character_agent/planning/l3_planner.py backend/app/character_agent/planning/triple_filter.py backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_agent_triple_filter.py backend/tests/test_character_agent_control_modes.py
git commit -m "Expand L3 into a full role action-space planner

Constraint: Complete mind core requires broad candidate generation and filtering beyond the demo-era narrow action set
Rejected: Keep adding one-off candidates only when demo beats demand them | freezes L3 as a slice-specific selector
Confidence: medium
Scope-risk: broad
Directive: Treat silence, delay, distancing, concealment, and break-contact as first-class outcomes, not edge-case fallbacks
Tested: pytest backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_agent_triple_filter.py backend/tests/test_character_agent_control_modes.py -v
Not-tested: full scene runtime"
```

### Task 3: Complete control arbitration across AI, player-priority, away-conservative, and scripted modes

**Files:**
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/app/models/character_agent_runtime.py`
- Test: `backend/tests/test_character_agent_runtime.py`
- Test: `backend/tests/test_character_agent_char_c_suggestion_mode.py`
- Test: `backend/tests/test_character_actor_autonomy_modes.py`

- [ ] **Step 1: Write the failing control-arbitration test**

```python
from app.services.character_agent_runtime import CharacterAgentRuntime


def test_player_priority_mode_keeps_l1_l2_l3_running_but_suppresses_forced_execution() -> None:
    runtime = CharacterAgentRuntime()
    runtime.set_control_mode("char_c", "player_priority_assisted")
    assert runtime.get_control_mode("char_c") == "player_priority_assisted"
    assert runtime.supports_actor("char_c")
```

- [ ] **Step 2: Run the targeted test to verify failure if the mode contract is incomplete**

Run: `pytest backend/tests/test_character_agent_char_c_suggestion_mode.py backend/tests/test_character_actor_autonomy_modes.py -v`
Expected: `FAIL` if any path still bypasses the unified control contract.

- [ ] **Step 3: Add explicit arbitration helpers in runtime**

```python
def _should_emit_execution(self, actor_id: str, mode: str, selected_intent: str) -> bool:
    if mode == "player_priority_assisted":
        return False
    if mode == "away_conservative_takeover":
        return selected_intent in {"observe", "pause", "defer", "self_protect", "withdraw"}
    return True
```

Use the helper in all ingress families so perception and planning still run even when execution is suppressed.

- [ ] **Step 4: Run the runtime/control suites**

Run: `pytest backend/tests/test_character_agent_runtime.py backend/tests/test_character_agent_char_c_suggestion_mode.py backend/tests/test_character_actor_autonomy_modes.py -v`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add backend/app/character_agent/runtime/runtime_loop.py backend/app/models/character_agent_runtime.py backend/tests/test_character_agent_runtime.py backend/tests/test_character_agent_char_c_suggestion_mode.py backend/tests/test_character_actor_autonomy_modes.py
git commit -m "Complete unified control arbitration for the character mind core

Constraint: Player-priority and away-takeover must stay within the same role species while preserving full perception and planning
Rejected: Split player and AI roles into separate runtime brains | violates mainline role-core architecture
Confidence: medium
Scope-risk: moderate
Directive: Arbitration may suppress execution authority, but it must not suppress cognition layers silently
Tested: pytest backend/tests/test_character_agent_runtime.py backend/tests/test_character_agent_char_c_suggestion_mode.py backend/tests/test_character_actor_autonomy_modes.py -v
Not-tested: Godot observability"
```
