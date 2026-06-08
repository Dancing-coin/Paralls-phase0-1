# System L1 Debug, Replay, And Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the `System L1` verification and debug surface so the larger Phase 1 `System L1` domain remains provable as new emitters and `ESM` capabilities are added.

**Architecture:** Build on the current verification triad (`verify_phase0.py`, `verify_phase1_slice.py`, `verify_l1_runtime_edges.py`) and extend them only where new `System L1` subdomains require real runtime proof.

**Tech Stack:** Python 3.13, Godot 4.x, pytest, current JSON/Markdown verification reports.

---

## Status Snapshot

- Date: `2026-06-09`
- Plan status: partially executed
- Current code truth:
  - `verify_phase0.py`, `verify_phase1_slice.py`, and `verify_l1_runtime_edges.py` are all active and green
  - `verification_audit.py` has been extended repeatedly for new L1/ESM proof surfaces
  - current verification covers object visual facts, auditory facts, role/physiology facts, tactile/thermal/olfactory facts, ESM action/state outputs, and runtime edge recovery
- Remaining gap:
  - verification still lags any future full-domain auditory completion and runtime-wired remaining-emitter work

### Task 1: Inventory Current Coverage And Add Missing L1-Domain Checks

**Files:**
- Modify: `scripts/verification/verify_phase1_slice.py`
- Modify: `scripts/verification/verify_phase0.py`
- Modify: `scripts/verification/verify_l1_runtime_edges.py`
- Modify: `backend/app/verification_audit.py`

- [ ] **Step 1: Add failing checks for newly introduced L1 subdomains as each child plan lands**

Examples:

- auditory facts observed
- object visual facts observed
- spatial-relation visual facts observed
- evidence projection observed

- [ ] **Step 2: Run current verification scripts to identify the first missing proof**

Run:

```bash
python scripts/verification/verify_phase1_slice.py
python scripts/verification/verify_phase0.py
python scripts/verification/verify_l1_runtime_edges.py
```

- [ ] **Step 3: Extend audits minimally**

Keep audits strict but domain-specific. Do not broaden them into vague smoke tests.

- [ ] **Step 4: Re-run the three verification scripts**

Run:

```bash
python scripts/verification/verify_phase1_slice.py
python scripts/verification/verify_phase0.py
python scripts/verification/verify_l1_runtime_edges.py
```

- [ ] **Step 5: Commit**

```bash
git add scripts/verification/*.py backend/app/verification_audit.py
git commit -m "test: extend system-l1 verification coverage"
```
