# Mind Core Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining gap between the current strengthened character runtime and a genuinely complete character mind core by unifying cognition semantics, formalizing goal-state artifacts, and finishing goal repair/recovery behavior.

**Architecture:** This plan assumes the earlier `2026-06-29` foundation, `L1`, memory, `L2/L3`, and execution-preservation plans have largely landed. It does not redo those passes. It replaces the remaining loose-dict and scenario-heuristic seams with typed mind-state artifacts, a unified cognition-update engine, and a goal system that can persist, reorganize, and repair itself under pressure.

**Tech Stack:** Python, Pydantic, pytest, current `CharacterAgentRuntime`, model gateway, current observability and verification scripts.

---

### Task 1: Formalize typed goal and mind-state runtime artifacts

**Files:**
- Create: `backend/app/character_agent/models/goal_runtime.py`
- Modify: `backend/app/character_agent/models/__init__.py`
- Modify: `backend/app/models/character_agent_runtime.py`
- Modify: `backend/app/character_agent/gateway/output_validator.py`
- Test: `backend/tests/test_character_mind_core_models.py`
- Test: `backend/tests/test_character_agent_runtime_models.py`

- [ ] **Step 1: Write the failing typed-model tests**

```python
from app.character_agent.models.goal_runtime import (
    CharacterActiveGoalFrame,
    CharacterGoalHint,
    CharacterGoalStateRecord,
)


def test_goal_hint_is_a_typed_runtime_object() -> None:
    hint = CharacterGoalHint(
        goal="protect_secret",
        source="social_signal",
        strength=0.86,
        evidence_tags=["guarded_attention", "target_knows_sensitive_object"],
    )
    assert hint.goal == "protect_secret"
    assert hint.evidence_tags == ["guarded_attention", "target_knows_sensitive_object"]


def test_active_goal_frame_tracks_long_mid_and_immediate_layers() -> None:
    frame = CharacterActiveGoalFrame(
        primary_goal="protect_secret",
        long_term_goal="preserve_order",
        mid_term_strategy="contain_exposure",
        immediate_goal="withhold_until_private",
        supporting_goals=["clarify_intent"],
        blockers=["char_b_public_presence"],
        goal_sources=["l2_goal_hint:social_signal"],
        urgency="high",
    )
    assert frame.mid_term_strategy == "contain_exposure"


def test_goal_state_record_tracks_repair_and_recovery_metadata() -> None:
    record = CharacterGoalStateRecord(
        actor_id="char_c",
        primary_goal="protect_secret",
        long_term_goal="preserve_order",
        mid_term_strategy="repair_cover_story",
        immediate_goal="withdraw",
        supporting_goals=["preserve_optionality"],
        blockers=["target_already_suspicious"],
        goal_sources=["knowledge_state", "l2_goal_hint:social_signal"],
        urgency="high",
        transition_kind="repairing",
        transition_reason_tags=["strategy_blocked", "social_signal_reappraisal"],
    )
    assert record.transition_kind == "repairing"
```

- [ ] **Step 2: Run the focused model suites to verify failure**

Run: `pytest backend/tests/test_character_mind_core_models.py backend/tests/test_character_agent_runtime_models.py -v`
Expected: `FAIL` because typed goal/runtime artifacts do not yet exist.

- [ ] **Step 3: Add the typed goal-runtime models**

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CharacterGoalHint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str
    source: str
    strength: float = Field(ge=0.0, le=1.0)
    evidence_tags: list[str] = Field(default_factory=list)


class CharacterActiveGoalFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_goal: str = ""
    long_term_goal: str = ""
    mid_term_strategy: str = ""
    immediate_goal: str = ""
    supporting_goals: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    goal_sources: list[str] = Field(default_factory=list)
    urgency: str = "low"


class CharacterGoalStateRecord(CharacterActiveGoalFrame):
    actor_id: str
    transition_kind: str = "initial"
    transition_reason_tags: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Thread the typed artifacts through the runtime-facing models and validator**

```python
from app.character_agent.models.goal_runtime import CharacterActiveGoalFrame, CharacterGoalHint


class CharacterInterpretation(BaseModel):
    ...
    goal_hints: list[CharacterGoalHint] = Field(default_factory=list)


class CharacterIntentDecision(BaseModel):
    ...
    active_goal_frame: CharacterActiveGoalFrame | None = None
```

Update `CharacterStructuredOutputValidator` so the model-facing contract normalizes `goal_hints` into typed objects instead of raw `dict[str, object]`.

- [ ] **Step 5: Run the model suites**

Run: `pytest backend/tests/test_character_mind_core_models.py backend/tests/test_character_agent_runtime_models.py -v`
Expected: `PASS`

- [ ] **Step 6: Commit**

```bash
git add backend/app/character_agent/models/goal_runtime.py backend/app/character_agent/models/__init__.py backend/app/models/character_agent_runtime.py backend/app/character_agent/gateway/output_validator.py backend/tests/test_character_mind_core_models.py backend/tests/test_character_agent_runtime_models.py
git commit -m "Formalize typed goal artifacts for the character mind core

Constraint: Complete mind-core closure requires typed goal and mind-state artifacts instead of loose dictionary-only contracts
Rejected: Keep goal hints and active-goal frames as ad-hoc dicts | prevents consistent provenance and repair semantics
Confidence: high
Scope-risk: moderate
Directive: New goal semantics must enter the runtime as typed objects first and only flatten at transport edges when necessary
Tested: pytest backend/tests/test_character_mind_core_models.py backend/tests/test_character_agent_runtime_models.py -v
Not-tested: full runtime integration"
```

### Task 2: Replace scenario-local `L2` heuristics with a unified cognition-update engine

**Files:**
- Create: `backend/app/character_agent/reasoning/cognition_engine.py`
- Modify: `backend/app/character_agent/gateway/model_provider.py`
- Modify: `backend/app/character_agent/reasoning/l2_reasoner.py`
- Modify: `backend/app/character_agent/gateway/prompt_policy.py`
- Test: `backend/tests/test_character_model_provider.py`
- Test: `backend/tests/test_character_agent_l2_reasoning.py`
- Test: `backend/tests/test_character_agent_cognition_writeback.py`

- [ ] **Step 1: Write the failing unified-cognition tests**

```python
def test_local_cognition_engine_emits_typed_goal_hints_with_provenance() -> None:
    output = provider.generate_character_reasoning(
        actor_id="char_c",
        snapshot=snapshot,
        memory_bundle=memory_bundle,
        control_mode="player_priority_assisted",
    )
    protect_secret = next(item for item in output["goal_hints"] if item["goal"] == "protect_secret")
    assert protect_secret["source"] == "social_signal"
    assert "guarded_attention" in protect_secret["evidence_tags"]


def test_world_and_social_updates_share_same_dynamic_state_rule_shape() -> None:
    social = provider.generate_character_reasoning(...)
    world = provider.generate_character_reasoning(...)
    assert set(social["dynamic_state_delta"].keys()) <= {"stress_load", "vigilance_level", "distraction_level", "social_pressure", "masking_pressure"}
    assert set(world["dynamic_state_delta"].keys()) <= {"stress_load", "vigilance_level", "distraction_level", "social_pressure", "masking_pressure"}
```

- [ ] **Step 2: Run the focused suites to verify failure**

Run: `pytest backend/tests/test_character_model_provider.py backend/tests/test_character_agent_l2_reasoning.py backend/tests/test_character_agent_cognition_writeback.py -v`
Expected: `FAIL` because cognition updates are still partially scenario-local and untyped.

- [ ] **Step 3: Add a dedicated cognition-update engine**

```python
class CharacterCognitionEngine:
    def build_update(
        self,
        *,
        actor_id: str,
        snapshot: CharacterPrivateWorldSnapshot,
        memory_bundle: dict[str, object],
        control_mode: str,
    ) -> CharacterCognitionUpdate:
        evidence = self._collect_evidence(...)
        belief_deltas = self._belief_deltas_from_evidence(evidence)
        social_deltas = self._social_deltas_from_evidence(evidence)
        higher_order_deltas = self._higher_order_deltas_from_evidence(evidence)
        dynamic_state_delta = self._dynamic_state_delta_from_evidence(evidence)
        goal_hints = self._goal_hints_from_evidence(evidence)
        return CharacterCognitionUpdate(...)
```

- [ ] **Step 4: Route local/offline `L2` generation through the engine instead of hand-built case patches**

```python
engine = CharacterCognitionEngine()
update = engine.build_update(
    actor_id=actor_id,
    snapshot=snapshot,
    memory_bundle=memory_bundle,
    control_mode=control_mode,
)
return {
    "belief_deltas": update.belief_deltas,
    "social_deltas": update.social_deltas,
    "higher_order_deltas": update.higher_order_deltas,
    "dynamic_state_delta": update.dynamic_state_delta,
    "goal_hints": [item.model_dump() for item in update.goal_hints],
    "reasoning_trace_summary": update.reasoning_trace_summary,
}
```

Also update prompt-policy guidance so online model output is held to the same structured goal-hint and provenance contract.

- [ ] **Step 5: Run the cognition suites**

Run: `pytest backend/tests/test_character_model_provider.py backend/tests/test_character_agent_l2_reasoning.py backend/tests/test_character_agent_cognition_writeback.py -v`
Expected: `PASS`

- [ ] **Step 6: Commit**

```bash
git add backend/app/character_agent/reasoning/cognition_engine.py backend/app/character_agent/gateway/model_provider.py backend/app/character_agent/reasoning/l2_reasoner.py backend/app/character_agent/gateway/prompt_policy.py backend/tests/test_character_model_provider.py backend/tests/test_character_agent_l2_reasoning.py backend/tests/test_character_agent_cognition_writeback.py
git commit -m "Unify L2 cognition updates behind one evidence engine

Constraint: Complete mind core requires one cognition-update logic across social, world, body, and Siming evidence families
Rejected: Keep extending offline reasoning through one-off scenario patches | grows behavior without closing architecture
Confidence: medium
Scope-risk: broad
Directive: New cognition behavior must enter through the shared evidence-to-update engine, not through isolated case branches
Tested: pytest backend/tests/test_character_model_provider.py backend/tests/test_character_agent_l2_reasoning.py backend/tests/test_character_agent_cognition_writeback.py -v
Not-tested: live online-model behavior"
```

### Task 3: Complete layered goal-state persistence and repair/recovery semantics

**Files:**
- Modify: `backend/app/character_agent/planning/l3_planner.py`
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/app/character_agent/storage/goal_state_store.py`
- Test: `backend/tests/test_character_agent_l3_planning.py`
- Test: `backend/tests/test_character_agent_runtime.py`
- Test: `backend/tests/test_character_mind_core_storage.py`

- [ ] **Step 1: Write the failing goal-repair tests**

```python
def test_l3_active_goal_frame_includes_mid_term_strategy() -> None:
    plan = planner.build_intent_plan(...)
    assert plan["active_goal_frame"]["mid_term_strategy"]


def test_goal_state_event_records_repair_transition_when_strategy_is_rebuilt_after_blocker() -> None:
    runtime = CharacterAgentRuntime()
    ...
    goal_events = [entry for entry in runtime.get_session_timeline("char_a") if entry["event_type"] == "goal_state_event"]
    assert goal_events[-1]["payload"]["transition_kind"] in {"repairing", "recovering"}
    assert "strategy_blocked" in goal_events[-1]["payload"]["transition_reason_tags"]
```

- [ ] **Step 2: Run the focused goal suites to verify failure**

Run: `pytest backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_agent_runtime.py backend/tests/test_character_mind_core_storage.py -v`
Expected: `FAIL` because mid-term strategy and repair/recovery semantics are not yet formalized.

- [ ] **Step 3: Deepen the planner’s goal activator**

```python
active_goal_frame = CharacterActiveGoalFrame(
    primary_goal=primary_goal,
    long_term_goal=long_term_goal,
    mid_term_strategy=self._derive_mid_term_strategy(...),
    immediate_goal=immediate_goal,
    supporting_goals=supporting_goals,
    blockers=blockers,
    goal_sources=goal_sources,
    urgency=urgency,
)
```

Add scoring rules that favor `pause`, `defer`, `withdraw`, `withhold`, or private-redirection candidates when the active frame is blocked and enters repair mode.

- [ ] **Step 4: Persist typed goal state and emit repair/recovery transition semantics**

```python
if previous.primary_goal == current.primary_goal and strategy_blocked and current.mid_term_strategy != previous.mid_term_strategy:
    transition_kind = "repairing"
elif previous.transition_kind == "repairing" and blockers_cleared:
    transition_kind = "recovering"
```

Update `CharacterGoalStateStore` to round-trip typed `CharacterGoalStateRecord` objects and preserve history entries with transition metadata intact.

- [ ] **Step 5: Run the goal suites**

Run: `pytest backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_agent_runtime.py backend/tests/test_character_mind_core_storage.py -v`
Expected: `PASS`

- [ ] **Step 6: Commit**

```bash
git add backend/app/character_agent/planning/l3_planner.py backend/app/character_agent/runtime/runtime_loop.py backend/app/character_agent/storage/goal_state_store.py backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_agent_runtime.py backend/tests/test_character_mind_core_storage.py
git commit -m "Complete goal layering and repair semantics in the mind core

Constraint: Complete role mind requires goal continuity, reorganization, and repair rather than one-step intent selection only
Rejected: Leave goal state as current-plus-history diffs without repair semantics | cannot describe blocked-strategy recovery honestly
Confidence: medium
Scope-risk: broad
Directive: Goal transitions must describe strategic change, not only field change
Tested: pytest backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_agent_runtime.py backend/tests/test_character_mind_core_storage.py -v
Not-tested: websocket observability"
```

### Task 4: Preserve assisted-mode, observability, and verification carry-through for the final mind contract

**Files:**
- Modify: `backend/app/models/character_agent_runtime.py`
- Modify: `backend/app/services/character_agent_debug_projection.py`
- Modify: `backend/tests/test_character_agent_char_c_suggestion_mode.py`
- Modify: `backend/tests/test_character_agent_debug_projection.py`
- Modify: `backend/tests/test_ws_protocol.py`
- Modify: `scripts/verification/verify_character_director_observatory.py`

- [ ] **Step 1: Write the failing carry-through tests**

```python
def test_player_priority_suggestion_packet_preserves_mid_term_strategy_and_transition_semantics() -> None:
    packet = packets[0]["payload"]
    assert "mid_term_strategy" in packet
    assert "transition_kind" in packet
    assert "transition_reason_tags" in packet


def test_debug_projection_surfaces_goal_repair_state() -> None:
    snapshot = projector.project_actor_state("char_c")
    assert "goal_state" in snapshot
    assert "mid_term_strategy" in snapshot["goal_state"]
```

- [ ] **Step 2: Run the focused carry-through suites to verify failure**

Run: `pytest backend/tests/test_character_agent_char_c_suggestion_mode.py backend/tests/test_character_agent_debug_projection.py backend/tests/test_ws_protocol.py -v`
Expected: `FAIL` because the remaining goal-state closure data is not yet carried through all surfaces.

- [ ] **Step 3: Extend suggestion packets and observability snapshots**

```python
payload["mid_term_strategy"] = decision.mid_term_strategy
payload["transition_kind"] = latest_goal_state.transition_kind
payload["transition_reason_tags"] = latest_goal_state.transition_reason_tags
```

Update the debug projection so knowledge, higher-order, dynamic-state, and goal-state views stay aligned with the newly typed runtime artifacts.

- [ ] **Step 4: Refresh the observability verifier**

Run: `python scripts/verification/verify_character_director_observatory.py`
Expected: `overall_character_director_observatory_passed=True`

- [ ] **Step 5: Run the carry-through suites**

Run: `pytest backend/tests/test_character_agent_char_c_suggestion_mode.py backend/tests/test_character_agent_debug_projection.py backend/tests/test_ws_protocol.py -v`
Expected: `PASS`

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/character_agent_runtime.py backend/app/services/character_agent_debug_projection.py backend/tests/test_character_agent_char_c_suggestion_mode.py backend/tests/test_character_agent_debug_projection.py backend/tests/test_ws_protocol.py scripts/verification/verify_character_director_observatory.py
git commit -m "Carry final goal-state semantics through assisted and observability paths

Constraint: Player-priority and observability surfaces must expose the same mind-core truth as full-auto runtime paths
Rejected: Finish goal semantics only inside planner/runtime internals | leaves assisted control and audit surfaces semantically behind
Confidence: medium
Scope-risk: moderate
Directive: Any field required to explain current mind state must survive into suggestion and observability surfaces unless explicitly proven redundant
Tested: pytest backend/tests/test_character_agent_char_c_suggestion_mode.py backend/tests/test_character_agent_debug_projection.py backend/tests/test_ws_protocol.py -v; python scripts/verification/verify_character_director_observatory.py
Not-tested: full phase0 smoke"
```

### Task 5: Run end-to-end proof for mind-core closure without regressing the smoke path

**Files:**
- Modify only if verification reveals drift
- Test: `backend/tests/test_character_agent_runtime.py`
- Test: `backend/tests/test_character_model_provider.py`
- Test: `backend/tests/test_character_agent_l3_planning.py`
- Test: `backend/tests/test_character_agent_char_c_suggestion_mode.py`
- Test: `backend/tests/test_character_agent_debug_projection.py`
- Test: `scripts/verification/verify_character_agent_execution.py`
- Test: `scripts/verification/verify_character_director_observatory.py`
- Test: `scripts/verification/verify_phase0.py`

- [ ] **Step 1: Run the backend closure suites**

Run: `pytest backend/tests/test_character_mind_core_models.py backend/tests/test_character_agent_runtime_models.py backend/tests/test_character_model_provider.py backend/tests/test_character_agent_l2_reasoning.py backend/tests/test_character_agent_cognition_writeback.py backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_agent_runtime.py backend/tests/test_character_agent_char_c_suggestion_mode.py backend/tests/test_character_agent_debug_projection.py -v`
Expected: `PASS`

- [ ] **Step 2: Run the preserved runtime verifiers**

Run: `python scripts/verification/verify_character_agent_execution.py`
Expected: `overall_character_agent_execution_passed=True`

Run: `python scripts/verification/verify_character_director_observatory.py`
Expected: `overall_character_director_observatory_passed=True`

Run: `python scripts/verification/verify_phase0.py`
Expected: fresh report under `.harness/verification/phase0-report.md` with `Overall: True`

- [ ] **Step 3: Run the full backend suite**

Run: `python -m pytest -q`
Expected: `PASS`

- [ ] **Step 4: Commit**

```bash
git add .
git commit -m "Prove complete character mind core closure without losing the smoke path

Constraint: Final mind-core claims must keep shared-actor ingress and Phase 0 smoke proof alive
Rejected: Declare completion from targeted cognition suites only | leaves preserved runtime path unproven
Confidence: medium
Scope-risk: broad
Directive: Do not claim complete character mind core until backend closure suites, observability proof, execution proof, and fresh phase0 smoke are all green together
Tested: pytest backend/tests/test_character_mind_core_models.py backend/tests/test_character_agent_runtime_models.py backend/tests/test_character_model_provider.py backend/tests/test_character_agent_l2_reasoning.py backend/tests/test_character_agent_cognition_writeback.py backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_agent_runtime.py backend/tests/test_character_agent_char_c_suggestion_mode.py backend/tests/test_character_agent_debug_projection.py -v; python scripts/verification/verify_character_agent_execution.py; python scripts/verification/verify_character_director_observatory.py; python scripts/verification/verify_phase0.py; python -m pytest -q
Not-tested: Godot editor-interactive scene inspection outside harness"
```
