# System L1 ESM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the current repo’s minimal environment/action settlement helper into a Phase 1-shaped `ESM` slice with clearer contracts, environment-field state, and debug/replay-friendly outputs.

**Architecture:** Keep `ESM` inside `System L1`, preserve deterministic settlement, and extend it along three axes: action/constraint contracts, environment state-machine structure, and regional environment-field data that can influence later perception and execution rules.

**Tech Stack:** Python 3.13, FastAPI backend, Pydantic models, pytest, existing `ESMService`, current `world_result` path.

---

## Status Snapshot

- Date: `2026-06-10`
- Plan status: superseded
- Superseded by:
  - `docs/superpowers/plans/2026-06-08-system-l1-esm-full-domain-implementation-plan.md`
- Reason:
  - this earlier plan defined the first Phase-1-shaped `ESM` slice
  - the repository later expanded that scope into the explicit repo-local full-domain closure plan
  - current status, evidence, and verification truth are maintained only in the newer full-domain plan

### Task 1: Formalize Action/Constraint Contracts

**Files:**
- Modify: `backend/app/services/esm_service.py`
- Modify: `backend/tests/test_esm_service.py`
- Optional Modify: `backend/app/models/world_result.py`

- [ ] **Step 1: Add failing tests for explicit action settlement contracts**

Add tests to `backend/tests/test_esm_service.py` asserting that:

- successful interaction returns a deterministic success result with stable causation fields
- failed interaction returns a deterministic constraint result with stable constraint fields
- the environment-state result path is still explicit and replayable

- [ ] **Step 2: Run the ESM tests to verify failure if new fields/contract shape are missing**

Run:

```bash
python -m pytest -v tests/test_esm_service.py
```

- [ ] **Step 3: Extend `ESMService` and models minimally**

Add or stabilize:

- explicit action settlement result shape
- explicit constraint shape
- deterministic environment-state result shape

Do not add narrative meaning.

- [ ] **Step 4: Re-run ESM tests**

Run:

```bash
python -m pytest -v tests/test_esm_service.py
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/esm_service.py backend/tests/test_esm_service.py backend/app/models/world_result.py
git commit -m "feat: formalize phase1-shaped esm settlement contracts"
```

### Task 2: Add A Minimal Regional Environment Field

**Files:**
- Modify: `backend/app/services/esm_service.py`
- Optional Create: `backend/app/models/environment_field.py`
- Modify: `backend/tests/test_esm_service.py`

- [ ] **Step 1: Add failing tests for coarse environment field state**

Add a test asserting that the repo can represent at least one coarse environment field value, such as light or noise, and that an environment-state transition can update it deterministically.

- [ ] **Step 2: Run to verify failure**

Run:

```bash
python -m pytest -v tests/test_esm_service.py
```

- [ ] **Step 3: Implement the minimal field structure**

The first version can be extremely small:

- `light_level`
- `noise_level`

Keep it deterministic and local to `ESM`.

- [ ] **Step 4: Re-run tests**

Run:

```bash
python -m pytest -v tests/test_esm_service.py
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/esm_service.py backend/tests/test_esm_service.py backend/app/models/environment_field.py
git commit -m "feat: add minimal regional environment field to esm"
```

### Task 3: Preserve Runtime Verification

**Files:**
- Modify only if needed: `scripts/verification/verify_phase0.py`
- Modify only if needed: `backend/tests/test_visual_fact_pipeline.py`

- [ ] **Step 1: Run full verification**

Run:

```bash
python -m pytest -v
python scripts/verification/verify_phase1_slice.py
python scripts/verification/verify_phase0.py
python scripts/verification/verify_l1_runtime_edges.py
```

Expected:

- PASS

- [ ] **Step 2: Commit only if verification harnesses changed**

```bash
git add scripts/verification/verify_phase0.py backend/tests/test_visual_fact_pipeline.py
git commit -m "test: preserve runtime verification under esm expansion"
```
