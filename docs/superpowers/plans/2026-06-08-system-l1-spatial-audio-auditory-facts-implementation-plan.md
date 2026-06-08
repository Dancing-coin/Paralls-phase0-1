# System L1 Spatial Audio And Auditory Facts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first formal auditory raw-fact path to `System L1` so the repo no longer treats visual and spatial-access facts as the only real perception-adjacent sources.

**Architecture:** Keep Godot-side high-frequency execution local, but emit structured auditory raw facts into the same shared `raw_fact_event` contract. Start with a narrow but explicit auditory fact set: source actor, loudness band, speech mode, and coarse auditory reachability.

**Tech Stack:** Godot 4.x GDScript, Python 3.13, FastAPI backend, Pydantic models, pytest, existing raw fact contract and verification harnesses.

---

## Status Snapshot

- Date: `2026-06-09`
- Plan status: mostly executed
- Current code truth:
  - auditory raw-fact contract exists
  - `AuditoryFactEmitter.gd` exists and is scene-wired
  - backend routes auditory facts through the authority path
  - verification proves the first auditory fact path
- Remaining gap:
  - this plan's first formal auditory path is effectively landed
  - deeper auditory-domain completion moved into the dedicated auditory completion plan

### Task 1: Add The Auditory Raw Fact Contract

**Files:**
- Modify: `backend/app/models/raw_fact.py`
- Modify: `backend/tests/test_raw_fact_router.py`

- [ ] **Step 1: Add failing tests for auditory raw facts**

Add a test asserting that `RawFactEvent` accepts an auditory fact family or auditory-like fact type under the shared contract.

- [ ] **Step 2: Run and verify failure if the current contract is too narrow**

Run:

```bash
python -m pytest -v tests/test_raw_fact_router.py
```

- [ ] **Step 3: Extend the contract only as needed**

Preserve shared raw-fact structure. Do not fork a second path.

- [ ] **Step 4: Re-run focused tests**

Run:

```bash
python -m pytest -v tests/test_raw_fact_router.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/raw_fact.py backend/tests/test_raw_fact_router.py
git commit -m "feat: extend raw fact contract for auditory facts"
```

### Task 2: Add A Godot Auditory Emitter

**Files:**
- Create: `scripts/l1/facts/emitters/AuditoryFactEmitter.gd`
- Modify: `scenes/phase0/MainDemo.tscn`
- Modify: `backend/tests/test_verification_audit.py`

- [ ] **Step 1: Add failing verification test**

Add a static verification test checking that `AuditoryFactEmitter.gd` exists and exposes at least one speech/auditory emission method.

- [ ] **Step 2: Run the verification test to verify failure**

Run:

```bash
python -m pytest -v tests/test_verification_audit.py
```

- [ ] **Step 3: Create the minimal emitter**

The first version should emit facts like:

- `speaker_active`
- `speech_mode_changed`

using the existing shared raw-fact builder/emitter path.

- [ ] **Step 4: Wire the emitter into `MainDemo.tscn`**

Add it under the same `VisualFactEmitter`/L1 fact area or a sibling `FactEmitterRoot`, following the existing project pattern.

- [ ] **Step 5: Re-run static verification**

Run:

```bash
python -m pytest -v tests/test_verification_audit.py
```

- [ ] **Step 6: Commit**

```bash
git add scripts/l1/facts/emitters/AuditoryFactEmitter.gd scenes/phase0/MainDemo.tscn backend/tests/test_verification_audit.py
git commit -m "feat: add auditory raw fact emitter"
```

### Task 3: Add Backend Routing For Auditory Facts

**Files:**
- Modify: `backend/app/services/fact_router.py`
- Optional Create: `backend/app/services/fact_handlers/auditory_fact_handler.py`
- Modify: `backend/tests/test_raw_fact_router.py`

- [ ] **Step 1: Add failing route tests**

Add tests asserting that auditory raw facts are accepted and routed without breaking visual/spatial support.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest -v tests/test_raw_fact_router.py
```

- [ ] **Step 3: Add the minimal route behavior**

Keep router thin.
If a separate handler is useful, create it; if not, keep the first route minimal and explicit.

- [ ] **Step 4: Re-run route tests**

Run:

```bash
python -m pytest -v tests/test_raw_fact_router.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/fact_router.py backend/app/services/fact_handlers/auditory_fact_handler.py backend/tests/test_raw_fact_router.py
git commit -m "feat: route auditory raw facts through authority path"
```

### Task 4: Run End-To-End Regression

- [ ] **Step 1: Run full backend and runtime verification**

Run:

```bash
python -m pytest -v
python scripts/verification/verify_phase1_slice.py
python scripts/verification/verify_phase0.py
python scripts/verification/verify_l1_runtime_edges.py
```

Expected:

- PASS
