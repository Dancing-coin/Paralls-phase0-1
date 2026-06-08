# System L1 Verification Truth Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep implementation truth, verification truth, and repository-local summary truth synchronized for `System L1`.

**Architecture:** Build on the current verification triad and repository-local checklist. Tighten the maintenance rules so new L1 subdomains cannot land in code without corresponding verification and status-surface updates.

**Tech Stack:** Python 3.13, pytest, current verification scripts, repo-local markdown status/checklist docs.

---

### Task 1: Make The Repository Checklist Match Current L1 Truth

**Files:**
- Modify: `docs/phase1-l1-full-scope-checklist.md`
- Modify: `backend/tests/test_verification_audit.py`

- [ ] **Step 1: Write failing truth-sync tests**

Add tests that prove the checklist no longer claims completed L1 subdomains are still missing.

- [ ] **Step 2: Run the failing tests**

```bash
python -m pytest -v tests/test_verification_audit.py
```

- [ ] **Step 3: Update the checklist**

Bring the checklist in line with current truth for:
- visual fact completion
- auditory route presence
- remaining emitter shell presence
- client interaction normalization
- current ESM depth

- [ ] **Step 4: Re-run tests**

```bash
python -m pytest -v tests/test_verification_audit.py
```

- [ ] **Step 5: Commit**

```bash
git add docs/phase1-l1-full-scope-checklist.md backend/tests/test_verification_audit.py
git commit -m "docs: sync the repository-local L1 checklist with current truth"
```

### Task 2: Freeze Positive / Negative Verification Fixture Discipline

**Files:**
- Modify: `backend/tests/test_verification_audit.py`

- [ ] **Step 1: Add failing tests or assertions for fixture symmetry**

Make explicit that when a new proof surface is added:
- positive fixtures include it
- negative fixtures omit it

- [ ] **Step 2: Run failing tests**

```bash
python -m pytest -v tests/test_verification_audit.py
```

- [ ] **Step 3: Normalize fixtures**

Update the fixture set so this rule is consistently enforced across:
- visual proof
- auditory proof
- authority-route proof

- [ ] **Step 4: Re-run tests**

```bash
python -m pytest -v tests/test_verification_audit.py
```

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_verification_audit.py
git commit -m "test: enforce verification fixture symmetry for L1 proof surfaces"
```

### Task 3: Verify The Verification Surface

**Files:**
- Modify only if needed: `scripts/verification/verify_phase1_slice.py`
- Modify only if needed: `scripts/verification/verify_phase0.py`
- Modify only if needed: `scripts/verification/verify_l1_runtime_edges.py`
- Modify only if needed: `backend/app/verification_audit.py`

- [ ] **Step 1: Run full backend tests**

```bash
python -m pytest -v
```

- [ ] **Step 2: Run runtime verification triad serially**

```bash
python scripts/verification/verify_phase1_slice.py
python scripts/verification/verify_phase0.py
python scripts/verification/verify_l1_runtime_edges.py
```

- [ ] **Step 3: Commit only if verification scripts changed**

```bash
git add scripts/verification/*.py backend/app/verification_audit.py
git commit -m "test: keep the System L1 verification truth surface aligned"
```

