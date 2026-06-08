# System L1 Auditory Domain Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current first auditory route into a true auditory `System L1` subdomain with an explicit fact taxonomy, a stable candidate-compiler policy, and verification proof that matches the chosen boundary.

**Architecture:** Keep the shared `raw_fact_event` spine. Do not add a second transport path. Extend auditory facts along three dimensions: fact taxonomy, propagation semantics, and explicit `L1-only` vs `candidate-compilable` policy.

**Tech Stack:** Godot 4.x GDScript, Python 3.13, pytest, current raw fact contract, verification triad.

---

## Status Snapshot

- Date: `2026-06-09`
- Plan status: partially executed
- Current code truth:
  - `speaker_active` path is real and verified
  - `speech_mode_changed` is represented in the current auditory payload
- Remaining gap:
  - `auditory_reachability_changed` is not yet promoted to an explicit fact type
  - `ambient_noise_changed` is not yet promoted to an explicit fact type
  - auditory candidate-compilation policy is not yet frozen in code
  - verification does not yet prove the full auditory-domain boundary this plan targets

### Task 1: Expand The Auditory Fact Taxonomy

**Files:**
- Modify: `scripts/l1/facts/emitters/AuditoryFactEmitter.gd`
- Modify: `scripts/audio/SpatialVoiceController.gd`
- Modify: `backend/tests/test_raw_fact_router.py`
- Modify: `backend/tests/test_verification_audit.py`

- [ ] **Step 1: Write the failing tests**

Require explicit support for at least:
- `speaker_active`
- `speech_mode_changed`
- `auditory_reachability_changed`
- `ambient_noise_changed`

- [ ] **Step 2: Run the failing tests**

```bash
python -m pytest -v tests/test_raw_fact_router.py tests/test_verification_audit.py
```

- [ ] **Step 3: Implement the minimal taxonomy**

Keep `AuditoryFactEmitter.gd` focused and structured.
Do not branch into role-private hearing outcomes.

- [ ] **Step 4: Re-run tests**

```bash
python -m pytest -v tests/test_raw_fact_router.py tests/test_verification_audit.py
```

- [ ] **Step 5: Commit**

```bash
git add scripts/l1/facts/emitters/AuditoryFactEmitter.gd scripts/audio/SpatialVoiceController.gd backend/tests/test_raw_fact_router.py backend/tests/test_verification_audit.py
git commit -m "feat: expand auditory L1 fact taxonomy"
```

### Task 2: Freeze Candidate-Compiler Policy For Auditory Facts

**Files:**
- Modify: `backend/app/services/candidate_percept_service.py`
- Modify: `backend/tests/test_candidate_percept_service.py`
- Modify: `backend/tests/test_visual_fact_pipeline.py`

- [ ] **Step 1: Write the failing tests**

Add tests for the chosen policy:
- one auditory fact type that remains `L1-only`
- one auditory fact type that becomes candidate-compilable, if that is the chosen policy

- [ ] **Step 2: Run the failing tests**

```bash
python -m pytest -v tests/test_candidate_percept_service.py tests/test_visual_fact_pipeline.py
```

- [ ] **Step 3: Implement the minimal policy**

Recommended:
- keep `ambient_noise_changed` at `L1-only`
- optionally compile `speaker_active` and/or `auditory_reachability_changed`

If no auditory fact is promoted yet, make that explicit and test for empty compilation.

- [ ] **Step 4: Re-run tests**

```bash
python -m pytest -v tests/test_candidate_percept_service.py tests/test_visual_fact_pipeline.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/candidate_percept_service.py backend/tests/test_candidate_percept_service.py backend/tests/test_visual_fact_pipeline.py
git commit -m "feat: freeze auditory L1-to-L2 candidate policy"
```

### Task 3: Strengthen Auditory Verification Proof

**Files:**
- Modify: `backend/app/verification_audit.py`
- Modify: `scripts/verification/verify_phase1_slice.py`
- Modify: `scripts/verification/verify_phase0.py`
- Modify: `backend/tests/test_verification_audit.py`

- [ ] **Step 1: Add failing verification checks**

Require the auditory domain to prove:
- raw auditory emission
- the chosen candidate policy behavior, if any
- no accidental role-private conclusion in `L1`

- [ ] **Step 2: Run failing tests**

```bash
python -m pytest -v tests/test_verification_audit.py
```

- [ ] **Step 3: Extend audits minimally**

Keep the proofs explicit and domain-specific.

- [ ] **Step 4: Re-run tests**

```bash
python -m pytest -v tests/test_verification_audit.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/verification_audit.py scripts/verification/verify_phase1_slice.py scripts/verification/verify_phase0.py backend/tests/test_verification_audit.py
git commit -m "test: prove the auditory L1 domain explicitly"
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
