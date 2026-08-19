# SGC-5 Performance And Replay Evidence Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task after one complete SGC-1..4 vertical exists.

**Goal:** Establish reproducible performance and load-shedding evidence without making unsupported scale claims.

**Spec:** `docs/superpowers/specs/world-character-siming-authority-mainline/siming-group-world-formalization/05-sgc-5-performance-replay-evidence-contract.md`

**Prerequisite:** One complete vertical with focused replay/privacy evidence.

### Task 0: Benchmark admission gate

**Files:** completed SGC focused/Harness report, synthetic dataset manifest, `.harness/verification/`

- [ ] Select the completed vertical and record its source/revision/privacy/replay evidence digest.
- [ ] If the vertical is incomplete, stop with `unimplemented`; do not create a capacity claim or benchmark baseline.
- [ ] Freeze synthetic data version, environment label and measurement schema before collecting timings.

### Task 1: Define deterministic profile inputs

**Files:** `backend/tests/test_sgc_performance_profiles.py`, `docs/harness.md`

- [ ] Write RED tests rejecting missing environment, dataset, seed, revision, budget, repeat or selector metadata.
- [ ] Fix synthetic dataset version/size, warm-up/repeat counts and measured fields for all four profiles.
- [ ] Record local environment labels without reading private character memory.

### Task 2: Add profile selectors

**Files:** `scripts/verification/harness.py`, `scripts/verification/registry.py`, `.harness/profiles/sgc-5-performance-replay.json`, `.harness/rules/sgc-5-performance-replay.json`, `backend/tests/test_sgc_performance_profiles.py`

- [ ] Register the selector named `sgc-5-performance-replay` through the existing profile/rule manifests; its four subprofiles are data cases, not new runtimes.
- [ ] Record plan size, append count, projection latency, activation count, replay time, median and high percentile.
- [ ] Assert repeated fixed inputs produce the same input/result digests.

### Task 3: Enforce degradation evidence

**Files:** `backend/tests/test_sgc_performance_profiles.py`, `docs/harness.md`

- [ ] Write tests that reject silent receipt loss, privacy weakening, audit omission and fabricated settlement on threshold breach.
- [ ] Define each selector's threshold and allowed no-op/requeue/LOD disposition.
- [ ] Run the four subprofiles, record environment limits under `.harness/verification/sgc-5/`, and update completion audit only with measured evidence.
