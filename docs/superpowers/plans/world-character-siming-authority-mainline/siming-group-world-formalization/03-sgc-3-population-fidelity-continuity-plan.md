# SGC-3 Population Fidelity Continuity Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task after the cadence and owner contracts are approved.

**Goal:** Preserve one CharacterRecord while moving between deterministic far, mid and near fidelity.

**Spec:** `docs/superpowers/specs/world-character-siming-authority-mainline/siming-group-world-formalization/03-sgc-3-population-fidelity-continuity-contract.md`

**Prerequisite:** Existing committed cadence projection and one admitted owner-bound consumer.

### Task 0: Cadence and consumer gate

**Files:** `backend/app/population_continuity/models.py`, `backend/app/population_continuity/source_inputs.py`, `backend/app/population_continuity/world.py`, applicable owner contract, `.harness/verification/`

- [ ] Select the existing `WorldModeProfile`/source projection and record its mode revision, cadence class, source vector and privacy scope.
- [ ] Select one fixed owner-bound consumer; if either source or consumer contract is incomplete, record `owner-contract blocked` and stop.
- [ ] Confirm the package will extend `WorldModeProfile`, `PopulationBatchPlan` and `PopulationWorldPlan` rather than create a second planner or clock.

### Task 1: Pin batch inputs

**Files:** `backend/app/population_continuity/models.py`, `backend/app/population_continuity/batch.py`, `backend/tests/test_sgc_population_fidelity_handoff.py`

- [ ] Write RED tests for missing/private/revoked/stale cadence and nondeterministic ordering.
- [ ] Add world-mode/cadence refs and revisions, selector revision, seed and budget to the existing batch input model while preserving the current source-input validation and digest ordering.
- [ ] Return audited no-op/requeue for invalid cadence; never consult wall-clock or create a scheduler.

### Task 2: Enforce fidelity transitions

**Files:** `backend/app/population_continuity/activation.py`, `backend/app/population_continuity/batch.py`

- [ ] Reuse the existing activation lock for `active` and reject conflicting locks.
- [ ] Keep prewarm free of private memory and duplicate identity state.
- [ ] Requeue stale `pending_merge` candidates and preserve their source/revision audit.
- [ ] Keep presentation-only output out of append and map owner-bound output to one fixed catalog capability.

### Task 3: Validate fairness and replay

**Files:** `backend/tests/test_sgc_population_fidelity_handoff.py`, `scripts/verification/harness.py`, `scripts/verification/registry.py`, `.harness/profiles/sgc-3-population-fidelity-continuity.json`, `.harness/rules/sgc-3-population-fidelity-continuity.json`, `docs/harness.md`

- [ ] Test starvation credit, deterministic cohort ordering, privacy, idempotency, receipt and owner rejection.
- [ ] Register and run the selector named `sgc-3-population-fidelity-continuity` with full/tail replay evidence.
- [ ] Save cohort ordering, lock, privacy, requeue and receipt evidence under `.harness/verification/sgc-3/`.
- [ ] Update P3/INF-4 status and retain blocked rows for any missing owner contract.
