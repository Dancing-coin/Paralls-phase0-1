# System L1 Remaining Raw Emitter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the remaining `System L1` raw emitter classes that are still missing from the current repo: tactile, thermal, olfactory, physiology-state, and role-state emitters.

**Architecture:** Reuse the established shared raw-fact contract and emitter pattern. Do not introduce five unrelated send surfaces; implement each emitter as a narrow family-specific producer on top of the existing `FactEnvelopeBuilder` and `RawFactEmitter`.

**Tech Stack:** Godot 4.x GDScript, Python 3.13, FastAPI backend, pytest.

---

## Status Snapshot

- Date: `2026-06-09`
- Plan status: executed
- Current code truth:
  - `TactileFactEmitter.gd`
  - `ThermalFactEmitter.gd`
  - `OlfactoryFactEmitter.gd`
  - `PhysiologyStateFactEmitter.gd`
  - `RoleStateFactEmitter.gd`
  all exist and expose minimal emission methods
- Follow-on note:
  - this plan only covered shell creation
  - runtime truth for these families is tracked by the separate `runtime-wired-remaining-emitters` plan

### Task 1: Add The Five Missing Emitter Shells

**Files:**
- Create: `scripts/l1/facts/emitters/TactileFactEmitter.gd`
- Create: `scripts/l1/facts/emitters/ThermalFactEmitter.gd`
- Create: `scripts/l1/facts/emitters/OlfactoryFactEmitter.gd`
- Create: `scripts/l1/facts/emitters/PhysiologyStateFactEmitter.gd`
- Create: `scripts/l1/facts/emitters/RoleStateFactEmitter.gd`
- Modify: `backend/tests/test_verification_audit.py`

- [ ] **Step 1: Add failing verification tests for file existence and one method per emitter**

Add static tests asserting each file exists and exposes at least one emission method.

- [ ] **Step 2: Run verification tests to confirm failure**

Run:

```bash
python -m pytest -v tests/test_verification_audit.py
```

- [ ] **Step 3: Create minimal emitter shells**

Each should:

- extend `Node`
- reference the shared raw-fact path
- emit one minimal structured fact type

- [ ] **Step 4: Re-run verification tests**

Run:

```bash
python -m pytest -v tests/test_verification_audit.py
```

- [ ] **Step 5: Commit**

```bash
git add scripts/l1/facts/emitters/*.gd backend/tests/test_verification_audit.py
git commit -m "feat: add remaining system-l1 raw emitter shells"
```
