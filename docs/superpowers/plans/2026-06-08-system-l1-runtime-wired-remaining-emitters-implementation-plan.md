# System L1 Runtime-Wired Remaining Emitters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the remaining five `System L1` fact families beyond shell-only presence, with `role-state` and `physiology-state` becoming runtime-wired and the other three gaining bounded but real runtime/authority proof.

**Architecture:** Reuse the shared `raw_fact_event` contract and existing emitter pattern. Do not invent new transport paths. Drive `role-state` and `physiology-state` from already-running local runtime state, and give `tactile` / `thermal` / `olfactory` at least one real repository-local trigger plus verification proof.

**Tech Stack:** Godot 4.x GDScript, Python 3.13, pytest, current Phase 0 runtime harnesses, existing `FactEnvelopeBuilder.gd` / `RawFactEmitter.gd`.

---

## Status Snapshot

- Date: `2026-06-09`
- Plan status: executed and verified for the repository-local target
- Current code truth:
  - `RoleStateFactEmitter` is runtime-wired from `CharacterReplica`
  - `PhysiologyStateFactEmitter` is runtime-wired from jump / grounded runtime state
  - `TactileFactEmitter` is triggered from successful object interaction results
  - `ThermalFactEmitter` is triggered from `env_lamp -> alerted`
  - `OlfactoryFactEmitter` is triggered from the same bounded environment-state proxy
  - `phase1_slice`, `phase0`, and `l1_runtime_edges` verification passed after integration

## Completion Register

- Task 1 `RoleStateFactEmitter`: completed and verified
- Task 2 `PhysiologyStateFactEmitter`: completed and verified
- Task 3 `Tactile / Thermal / Olfactory` bounded runtime triggers: completed and verified
- Task 4 full regression: completed and verified

### Task 1: Runtime-Wire `RoleStateFactEmitter`

**Files:**
- Modify: `scripts/l1/facts/emitters/RoleStateFactEmitter.gd`
- Modify: `scripts/character/CharacterReplica.gd`
- Modify: `scenes/phase0/CharacterReplica.tscn`
- Modify: `backend/tests/test_verification_audit.py`

- [ ] **Step 1: Write the failing static/runtime-proof tests**

Add tests that require:
- `RoleStateFactEmitter.gd` to expose at least `emit_role_state_transition(...)`
- `CharacterReplica.gd` to call that emitter from real runtime state changes
- a verification token such as `phase0_role_state_fact_emitter:role_state_transition`

- [ ] **Step 2: Run the failing tests**

Run:

```bash
python -m pytest -v tests/test_verification_audit.py
```

Expected:
- FAIL because the emitter exists only as a shell and is not runtime-wired.

- [ ] **Step 3: Add the minimal runtime wiring**

Implement:
- one node path from `CharacterReplica` to `RoleStateFactEmitter`
- one low-level emission point when stance/gait/runtime execution mode changes
- one stable debug token

Prefer runtime changes already emitted via:
- locomotion state updates
- player shell active/inactive transitions
- action override state transitions

- [ ] **Step 4: Re-run tests**

Run:

```bash
python -m pytest -v tests/test_verification_audit.py
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/l1/facts/emitters/RoleStateFactEmitter.gd scripts/character/CharacterReplica.gd scenes/phase0/CharacterReplica.tscn backend/tests/test_verification_audit.py
git commit -m "feat: runtime-wire role-state L1 facts"
```

### Task 2: Runtime-Wire `PhysiologyStateFactEmitter`

**Files:**
- Modify: `scripts/l1/facts/emitters/PhysiologyStateFactEmitter.gd`
- Modify: `scripts/character/CharacterReplica.gd`
- Modify: `scenes/phase0/CharacterReplica.tscn`
- Modify: `backend/tests/test_verification_audit.py`

- [ ] **Step 1: Write the failing tests**

Require:
- `emit_breathing_strain_fact(...)` still exists
- `CharacterReplica.gd` emits physiology facts from a real body/runtime condition
- a stable verification token such as `phase0_physiology_fact_emitter:breathing_strain_changed`

- [ ] **Step 2: Run the failing tests**

Run:

```bash
python -m pytest -v tests/test_verification_audit.py
```

Expected:
- FAIL

- [ ] **Step 3: Add the minimal runtime source**

Bind physiology output to one already-running low-level condition, for example:
- sustained locomotion probe state
- forced movement / jump strain
- non-grounded or unstable movement band

Do not interpret psychology. Keep the fact low-level.

- [ ] **Step 4: Re-run tests**

Run:

```bash
python -m pytest -v tests/test_verification_audit.py
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/l1/facts/emitters/PhysiologyStateFactEmitter.gd scripts/character/CharacterReplica.gd scenes/phase0/CharacterReplica.tscn backend/tests/test_verification_audit.py
git commit -m "feat: runtime-wire physiology-state L1 facts"
```

### Task 3: Give `Tactile`, `Thermal`, And `Olfactory` One Real Repository Trigger Each

**Files:**
- Modify: `scripts/l1/facts/emitters/TactileFactEmitter.gd`
- Modify: `scripts/l1/facts/emitters/ThermalFactEmitter.gd`
- Modify: `scripts/l1/facts/emitters/OlfactoryFactEmitter.gd`
- Modify: `scripts/phase0/MainDemoController.gd`
- Modify: `backend/tests/test_verification_audit.py`

- [ ] **Step 1: Add failing tests**

Require one bounded runtime path each:
- tactile: interaction or close contact proxy
- thermal: environment field / alerted-lamp heat proxy
- olfactory: environment odor-state proxy

- [ ] **Step 2: Run the failing tests**

Run:

```bash
python -m pytest -v tests/test_verification_audit.py
```

Expected:
- FAIL

- [ ] **Step 3: Add bounded runtime triggers**

Keep them narrow and honest:
- tactile may fire on successful close interaction
- thermal may fire when `env_lamp` enters `alerted`
- olfactory may fire from the same environment state if explicitly documented as a bounded proxy

Do not invent full simulators.

- [ ] **Step 4: Re-run tests**

Run:

```bash
python -m pytest -v tests/test_verification_audit.py
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/l1/facts/emitters/TactileFactEmitter.gd scripts/l1/facts/emitters/ThermalFactEmitter.gd scripts/l1/facts/emitters/OlfactoryFactEmitter.gd scripts/phase0/MainDemoController.gd backend/tests/test_verification_audit.py
git commit -m "feat: add bounded runtime triggers for remaining sensory emitters"
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

- [ ] **Step 3: Commit verification-only updates if needed**

```bash
git add backend/tests/test_verification_audit.py scripts/verification/*.py backend/app/verification_audit.py
git commit -m "test: prove runtime-wired remaining L1 emitters"
```
