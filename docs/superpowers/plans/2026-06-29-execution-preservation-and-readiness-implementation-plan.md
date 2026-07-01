# Execution Preservation And Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve a minimal runnable execution path and shared actor ingress while reshaping the upstream mind core, and make the `L4` contracts rich enough for later full embodiment work.

**Architecture:** This plan intentionally does not pursue final embodiment richness. It protects the smoke path and shared actor ingress while broadening upstream execution contracts so future face/body/physiology work can attach without redesigning `L1-L3`.

**Tech Stack:** Python backend, Godot shared actor ingress, pytest, verification scripts, harness.

---

### Task 1: Freeze the upstream `L4` contract as complete even while downstream execution stays light

**Files:**
- Modify: `backend/app/character_agent/execution/l4_executor.py`
- Modify: `backend/app/character_agent/execution/l4_adapter.py`
- Test: `backend/tests/test_character_agent_l4_execution.py`
- Test: `backend/tests/test_character_agent_execution_channels.py`

- [ ] **Step 1: Write the failing contract-completeness test**

```python
from app.character_agent.execution.l4_executor import CharacterAgentL4Executor


def test_l4_execution_plan_exposes_complete_channel_contract_even_when_some_channels_are_light() -> None:
    executor = CharacterAgentL4Executor()
    plan = executor.build_execution_plan(...)
    assert "speech_channel" in plan
    assert "face_channel" in plan
    assert "body_channel" in plan
    assert "social_spatial_channel" in plan
    assert "physiology_channel" in plan
    assert "micro_expression_plan" in plan["face_channel"]
```

- [ ] **Step 2: Run the focused test to verify failure**

Run: `pytest backend/tests/test_character_agent_l4_execution.py::test_l4_execution_plan_exposes_complete_channel_contract_even_when_some_channels_are_light -v`
Expected: `FAIL` if the current contract still carries placeholder-only channel shapes.

- [ ] **Step 3: Extend the execution contract without requiring richer live embodiment yet**

```python
"face_channel": {
    "expression_state": expression_state,
    "micro_expression_plan": micro_expression_plan,
    "facs_ready_tags": facs_ready_tags,
},
"body_channel": {
    "posture": posture,
    "gesture_bias": gesture_bias,
    "motion_emphasis": motion_emphasis,
},
"physiology_channel": {
    "guarding": guarding,
    "hesitation": hesitation,
    "breath_state": breath_state,
    "fatigue_signal": fatigue_signal,
}
```

- [ ] **Step 4: Run the execution contract suites**

Run: `pytest backend/tests/test_character_agent_l4_execution.py backend/tests/test_character_agent_execution_channels.py -v`
Expected: `PASS`

- [ ] **Step 5: Commit**

```bash
git add backend/app/character_agent/execution/l4_executor.py backend/app/character_agent/execution/l4_adapter.py backend/tests/test_character_agent_l4_execution.py backend/tests/test_character_agent_execution_channels.py
git commit -m "Freeze a complete L4 contract while keeping execution light

Constraint: Upstream mind-core completeness must not depend on finishing full embodiment richness first
Rejected: Leave face/body/physiology channels as shallow placeholders until later | forces future redesign of cognition outputs
Confidence: medium
Scope-risk: moderate
Directive: Light downstream embodiment is allowed; shallow upstream execution semantics are not
Tested: pytest backend/tests/test_character_agent_l4_execution.py backend/tests/test_character_agent_execution_channels.py -v
Not-tested: visual richness in Godot"
```

### Task 2: Preserve fresh smoke proof for the shared actor ingress path

**Files:**
- Modify: `scripts/verification/verify_character_agent_execution.py`
- Modify: `scripts/verification/verify_phase0.py`
- Modify: `.harness/rules/` manifests only if required by changed evidence semantics
- Test: `scripts/verification/tests/test_character_agent_execution_verify.py`

- [ ] **Step 1: Write the failing verification test**

```python
from pathlib import Path


def test_character_agent_execution_verifier_requires_shared_actor_ingress_evidence() -> None:
    report = Path(".harness/verification/character-agent-execution-report.md")
    if report.exists():
        text = report.read_text(encoding="utf-8")
        assert "character_agent_execution_contract" in text
        assert "character_agent_execution_consumer" in text
```

- [ ] **Step 2: Run the focused test to verify failure if runtime evidence no longer matches current code**

Run: `pytest scripts/verification/tests/test_character_agent_execution_verify.py -v`
Expected: `FAIL` if the verifier still expects old signal shapes.

- [ ] **Step 3: Update the runtime verifier to match the preserved shared-ingress contract**

```python
required_signals = [
    "character_agent_execution_contract=proved",
    "character_agent_execution_consumer=proved",
]
```

If probe expectations changed, update the verifier to read the current execution payload and current shared actor-consumer evidence instead of older legacy command logs.

- [ ] **Step 4: Run the verification suites**

Run: `pytest scripts/verification/tests/test_character_agent_execution_verify.py -v`
Expected: `PASS`

Run: `python scripts/verification/verify_character_agent_execution.py`
Expected: `overall_character_agent_execution_passed=True`

- [ ] **Step 5: Commit**

```bash
git add scripts/verification/verify_character_agent_execution.py scripts/verification/verify_phase0.py scripts/verification/tests/test_character_agent_execution_verify.py .harness/rules
git commit -m "Preserve smoke-proof execution ingress while mind core evolves

Constraint: Complete mind-core work must keep a minimal fresh shared-actor execution proof alive
Rejected: Let smoke verifiers drift behind runtime changes and trust old report artifacts | weakens acceptance evidence
Confidence: medium
Scope-risk: moderate
Directive: Verification scripts must track current runtime truth and may not rely on stale artifacts as proof
Tested: pytest scripts/verification/tests/test_character_agent_execution_verify.py -v; python scripts/verification/verify_character_agent_execution.py
Not-tested: full all-profile harness"
```
