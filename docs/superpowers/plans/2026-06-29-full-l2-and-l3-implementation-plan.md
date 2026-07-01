# Full L2 And L3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current partial interpretation and narrow planning stack into a model-led character mind cognition layer with belief updates, higher-order reasoning, persistent multi-goal portfolio state, optional background cognition, supervised reappraisal controls, broad action-space generation, unified control arbitration, and explicit continuity-floor downgrade semantics.

**Architecture:** This plan assumes the foundation and five-pool memory work are landed first. `L2` becomes a model-led cognition harness rather than a summary service or local rule brain; `L3` becomes a model-led action-possibility-space manager rather than a narrow demo-first selector or local final arbiter. The goal layer is upgraded from a single active frame to a persistent multi-goal portfolio that is written after each turn and reinjected into later `L2/L3` model contexts. On top of the foreground event loop, the runtime gains an optional low-frequency background cognition loop controlled by supervision state and external authorization for medium / strong governance. Execution remains light but the mind contract becomes complete and embodiment-ready.

**Tech Stack:** Python, model gateway, current runtime loop, pytest, Pydantic.

---

### Task 1: Make `L2` a model-led cognition-update harness

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

- [ ] **Step 4: Remove local replacement-cognition ownership from `L2`**

Explicitly separate:

- context assembly
- model invocation
- structured validation
- writeback application

from forbidden local semantic ownership such as:

- locally deciding what another actor means
- locally generating new belief / social / higher-order deltas as a fallback equivalent to model thought
- locally fabricating fresh goal hints while presenting them as normal cognition

Replace local replacement cognition with:

- retry same provider
- retry alternate provider
- emit explicit `cognition_unavailable` status
- enter continuity-floor downgrade state when needed

- [ ] **Step 5: Add `L2` writeback application hooks**

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

- [ ] **Step 6: Add failure-state tests**

Run / add focused tests proving:

- strict online route surfaces provider failure
- `L2` does not silently replace failed model cognition with local heuristic cognition
- continuity-floor state is explicit in runtime outputs and observability

- [ ] **Step 7: Run the `L2` suites**

Run: `pytest backend/tests/test_character_agent_l2_reasoning.py backend/tests/test_character_agent_cognition_writeback.py -v`
Expected: `PASS`

- [ ] **Step 8: Commit**

```bash
git add backend/app/character_agent/reasoning/l2_reasoner.py backend/app/models/character_agent_runtime.py backend/app/character_agent/gateway/prompt_policy.py backend/tests/test_character_agent_l2_reasoning.py backend/tests/test_character_agent_cognition_writeback.py
git commit -m "Make L2 a model-led cognition harness

Constraint: Character mind-core semantics require subjective interpretation to belong to the model rather than a hidden local rule brain
Rejected: Keep local cognition engine as semantic fallback | silently replaces role thought with heuristics
Confidence: medium
Scope-risk: broad
Directive: Local code may validate and downgrade, but it may not fabricate replacement cognition while claiming normal L2 semantics
Tested: pytest backend/tests/test_character_agent_l2_reasoning.py backend/tests/test_character_agent_cognition_writeback.py -v
Not-tested: Godot runtime observability"
```

### Task 2: Make `L3` a model-led action-possibility-space manager

**Files:**
- Modify: `backend/app/character_agent/planning/l3_planner.py`
- Modify: `backend/app/character_agent/models/goal_runtime.py`
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

Replace local final-arbiter logic with:

- model-produced candidate set
- model-produced selected intent
- model-produced multi-goal portfolio, dominant-goal identity, and preserved/suppressed goal sets
- local execution-feasibility and authority validation
- explicit re-ask / reject / continuity-floor downgrade when the selected intent is invalid

Local code may still translate between planner contracts and execution contracts, but it must not retain final semantic ownership of what the role should do.

Task 2 also owns the planning-side goal contract:

- `L3` must accept persisted current goal state and short goal-history context from runtime
- `L3` must send that context into the model prompt rather than replacing it with a local single-goal shell
- `L3` may keep a narrow continuity shell only when no persisted goal state exists or the model is unavailable

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

Refactor this so the local layer becomes guardrail-oriented rather than replacement-planner-oriented:

- use local state to constrain affordances
- use local state to reject impossible or disallowed actions
- do not use local state to silently outvote a valid model plan and substitute a locally preferred social tactic

- [ ] **Step 5: Run the planning and control suites**

Run: `pytest backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_agent_triple_filter.py backend/tests/test_character_agent_control_modes.py -v`
Expected: `PASS`

- [ ] **Step 6: Commit**

```bash
git add backend/app/character_agent/planning/l3_planner.py backend/app/character_agent/planning/triple_filter.py backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_agent_triple_filter.py backend/tests/test_character_agent_control_modes.py
git commit -m "Make L3 a model-led role action-space planner

Constraint: Role planning semantics must remain with the model; local code may constrain plans but may not own final intent selection
Rejected: Keep hybrid local selection after model planning | preserves a hidden local planner as the true arbiter
Confidence: medium
Scope-risk: broad
Directive: Treat continuity-floor actions as explicit downgrade outcomes, not as evidence that local planning is semantically equivalent to model planning
Tested: pytest backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_agent_triple_filter.py backend/tests/test_character_agent_control_modes.py -v
Not-tested: full scene runtime"
```

### Task 3: Complete control arbitration and continuity-floor downgrade semantics

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

Task 3 also owns cross-turn goal continuity:

- runtime must persist the full goal portfolio after each `L3` decision
- runtime must pass `current_goal_state` and `goal_state_history` back into later `L2` and `L3` turns
- continuity-floor decisions must preserve an explicit minimal goal portfolio rather than collapsing back into an untyped single-goal string
- runtime must expose a background cognition switch and per-role background mode so idle thought can be disabled when compute budget demands it
- runtime must support weak supervision by default and externally authorized medium / strong supervision for background cognition
- background cognition ticks should primarily update internal cognition / goals rather than directly emitting action commands
- scheduled background cognition should run through a public runtime scheduling entry instead of remaining an ad-hoc helper
- unresolved tensions and supervision authorizations should be recoverable from durable session history after reload
- background cognition should write an explicit durable agenda state so later turns can inherit latent tendency / watch focus
- background cognition should maintain a persistent agenda pool rather than replacing state with a single latest-summary field
- external systems should be able to authorize or clear supervision through a real runtime ingress surface rather than only via in-process calls

Use the helper in all ingress families so perception and planning still run even when execution is suppressed.

Also add explicit downgrade helpers:

```python
def _continuity_floor_action(self, *, mode: str, latest_state: dict[str, object]) -> str:
    ...
```

Allowed downgrade outcomes must stay narrow:

- observe
- hold
- stay_silent
- self_protect
- withdraw

Disallowed downgrade outcomes include any action that would imply fresh social or strategic reasoning, such as:

- ask_probe
- share_info
- speak_public
- speak_private
- follow_target
- complex concealment tactics inferred locally

- [ ] **Step 4: Run the runtime/control suites**

Run: `pytest backend/tests/test_character_agent_runtime.py backend/tests/test_character_agent_char_c_suggestion_mode.py backend/tests/test_character_actor_autonomy_modes.py -v`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add backend/app/character_agent/runtime/runtime_loop.py backend/app/models/character_agent_runtime.py backend/tests/test_character_agent_runtime.py backend/tests/test_character_agent_char_c_suggestion_mode.py backend/tests/test_character_actor_autonomy_modes.py
git commit -m "Add explicit continuity-floor arbitration to the character mind core

Constraint: Model-unavailable states must remain honest about lost cognition while preserving low-risk runtime continuity
Rejected: Let local fallback continue producing rich role decisions | disguises degraded runtime as intact character thought
Confidence: medium
Scope-risk: moderate
Directive: Arbitration may suppress execution authority or enter continuity-floor mode, but it must not silently invent replacement cognition or planning
Tested: pytest backend/tests/test_character_agent_runtime.py backend/tests/test_character_agent_char_c_suggestion_mode.py backend/tests/test_character_actor_autonomy_modes.py -v
Not-tested: Godot observability"
```
