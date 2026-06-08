# System L1 To System L2 Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen the `System L1 -> System L2` interface so raw facts, candidate percepts, and character-perceived events are not only distinct types, but are also explicitly observable, debuggable, and safely routable as separate seams.

**Architecture:** Build on the current Stage A and Stage B slices. Keep `RawFactEvent`, `CandidatePerceptEvent`, and `CharacterPerceivedEvent` distinct, and improve the interface seam by making the transitions explicit in runtime/debug output and by preserving the authority path without re-collapsing layers.

**Tech Stack:** Python 3.13, FastAPI backend, Pydantic models, pytest.

---

## Status Snapshot

- Date: `2026-06-09`
- Plan status: executed and verified for the repository-local target
- Current code truth:
  - `RawFactEvent`, `CandidatePerceptEvent`, and `CharacterPerceivedEvent` are distinct types
  - `BodyStateResult -> SelfBodyPerceivedEvent` self-body handoff now exists as a separate direct path
  - debug narration and runtime messages explicitly expose the L1 -> L2 -> per-character chain
  - guardrail tests already cover core authority/layer separation behavior

## Completion Register

- Task 1 candidate/perceived debug summaries: completed and verified
- Task 2 boundary guardrail tests: completed and verified

### Task 1: Make Candidate And Perceived Transitions Explicit In Debug Output

**Files:**
- Modify: `backend/app/debug_narration.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_debug_narration.py`

- [ ] **Step 1: Add failing tests for candidate/perceived debug summaries**

Add tests that require readable debug summaries for:

- candidate percept creation
- character-perceived event application

- [ ] **Step 2: Run the tests to verify failure**

Run:

```bash
python -m pytest -v tests/test_debug_narration.py
```

- [ ] **Step 3: Add the minimal debug wording**

Keep summaries short and layer-aware.

- [ ] **Step 4: Re-run tests**

Run:

```bash
python -m pytest -v tests/test_debug_narration.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/debug_narration.py backend/app/main.py backend/tests/test_debug_narration.py
git commit -m "feat: expose l1-to-l2 transitions in debug output"
```

### Task 2: Guard The Layer Boundaries With Tests

**Files:**
- Modify: `backend/tests/test_visual_fact_pipeline.py`
- Modify: `backend/tests/test_raw_fact_router.py`

- [ ] **Step 1: Add guardrail tests**

Add tests proving:

- `RawFactEvent` still routes to authority handlers
- candidate compilation happens behind that path
- character-perceived application happens without replacing authority output

- [ ] **Step 2: Run focused tests**

Run:

```bash
python -m pytest -v tests/test_raw_fact_router.py tests/test_visual_fact_pipeline.py
```

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_raw_fact_router.py backend/tests/test_visual_fact_pipeline.py
git commit -m "test: guard system-l1 to system-l2 interface seams"
```
