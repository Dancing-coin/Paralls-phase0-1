# System L1 ESM Full-Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the current strengthened `ESM` slice into a repository-local full-domain `System L1` subdomain with an explicit settlement matrix, clearer state templates, and stronger field / propagation semantics.

**Architecture:** Keep `ESM` inside `System L1`. Extend depth, not scope: more explicit settlement classes, more explicit state template boundaries, and clearer field semantics. Do not turn `ESM` into cognition, narrative meaning, or higher-layer orchestration.

**Tech Stack:** Python 3.13, FastAPI backend, Pydantic, pytest, current `world_result` and verification surfaces.

---

### Task 1: Freeze The Settlement Matrix

**Files:**
- Modify: `backend/app/models/world_result.py`
- Modify: `backend/app/services/esm_service.py`
- Modify: `backend/tests/test_esm_service.py`
- Modify: `backend/tests/test_ws_protocol.py`

- [ ] **Step 1: Write the failing tests**

Require explicit repository support for:
- interaction success
- interaction rejection
- environment-state shift
- one additional explicit settlement class or explicit negative policy

- [ ] **Step 2: Run the failing tests**

```bash
python -m pytest -v tests/test_esm_service.py tests/test_ws_protocol.py
```

- [ ] **Step 3: Implement the minimal matrix**

Do not overbuild. Either:
- add one additional settlement class
- or make the supported matrix explicit through tests and model shape

- [ ] **Step 4: Re-run tests**

```bash
python -m pytest -v tests/test_esm_service.py tests/test_ws_protocol.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/world_result.py backend/app/services/esm_service.py backend/tests/test_esm_service.py backend/tests/test_ws_protocol.py
git commit -m "feat: freeze the repository-local ESM settlement matrix"
```

### Task 2: Deepen Environment Field Semantics

**Files:**
- Modify: `backend/app/models/environment_field.py`
- Modify: `backend/app/services/esm_service.py`
- Modify: `backend/tests/test_esm_service.py`

- [ ] **Step 1: Write the failing tests**

Add tests for:
- current `light`
- current `noise`
- one more explicit field dimension such as `thermal` or `visibility_state`

- [ ] **Step 2: Run the failing tests**

```bash
python -m pytest -v tests/test_esm_service.py
```

- [ ] **Step 3: Implement the minimal field extension**

Keep the field system coarse and explicit.
Do not invent a full solver.

- [ ] **Step 4: Re-run tests**

```bash
python -m pytest -v tests/test_esm_service.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/environment_field.py backend/app/services/esm_service.py backend/tests/test_esm_service.py
git commit -m "feat: deepen repository-local ESM field semantics"
```

### Task 3: Strengthen Replay / Debug Proof For ESM

**Files:**
- Modify: `backend/app/verification_audit.py`
- Modify: `scripts/verification/verify_phase0.py`
- Modify: `backend/tests/test_verification_audit.py`

- [ ] **Step 1: Write failing proof tests**

Require phase verification to explicitly prove:
- stable ESM settlement identity
- explicit field/result evidence
- environment-state proof that goes beyond a single implicit log token

- [ ] **Step 2: Run the failing tests**

```bash
python -m pytest -v tests/test_verification_audit.py
```

- [ ] **Step 3: Implement the minimal audit extension**

Keep the proof strict, not broad smoke.

- [ ] **Step 4: Re-run tests**

```bash
python -m pytest -v tests/test_verification_audit.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/verification_audit.py scripts/verification/verify_phase0.py backend/tests/test_verification_audit.py
git commit -m "test: strengthen repository-local ESM proof surface"
```

### Task 4: Run Full Regression

- [ ] **Step 1: Run backend tests**

```bash
python -m pytest -v
```

- [ ] **Step 2: Run runtime verification triad serially**

```bash
python scripts/verification/verify_phase1_slice.py
python scripts/verification/verify_phase0.py
python scripts/verification/verify_l1_runtime_edges.py
```

