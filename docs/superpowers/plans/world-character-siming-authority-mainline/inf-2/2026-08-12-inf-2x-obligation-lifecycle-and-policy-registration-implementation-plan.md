# INF-2X Obligation Lifecycle And Policy Registration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the sole registered construction production obligation transition event-derived without creating a scheduler or domain owner.

**Architecture:** Preserve `SimulationClock` due selection and have each named authority emit its fragment/lifecycle correlation through the existing coordinator and `GameplayEventStore`.

**Tech Stack:** Python, existing `world_runtime` models/coordinator, gameplay authorities, pytest, Harness.

---

### Task 1: Define registration and legal transitions

**Files:** Modify `backend/app/world_runtime/obligations.py`; create `backend/tests/test_infra_obligation_lifecycle.py`.

- [x] Write focused failing tests for unregistered policy, registration owner/stream mismatch, missing correlation, illegal cancellation, revision conflict and unsupported retry/compensation; each retains event count.
- [x] Add immutable construction policy registration naming the owner, stream, settled/cancelled event family, project scope and policy revision.
- [x] Register only construction production v1; keep survival, economy and ecology lifecycle rows unavailable until their exact owner events are independently admitted.

### Task 2: Commit lifecycle through owner events

**Files:** Modify `backend/app/world_runtime/simulation_clock.py`, `obligations.py`, and the applicable existing authority modules; modify focused test.

- [x] Keep due ordering/catch-up caller-driven and append only the registered construction `settled` and `cancelled` correlation events through owner fragments.
- [x] Reject a missing owner fragment/correlation or stale expected stream revision without writes; pending/defer/release needs a separately admitted owner event.
- [x] Keep receipts process-local read projections of committed append results; do not introduce a receipt store.

### Task 3: Add retry, cancellation and permitted compensation

**Files:** Modify the same modules and focused test.

- [x] Keep retry and compensation rejected because no registered owner failure or compensation event exists.
- [x] Implement authorized future cancellation solely through the existing construction owner event and reject terminal or stale revisions before append.
- [x] Test duplicate receipts, revision conflict, cancellation terminal state, privacy filtering and no background settlement.
- [x] Rebuild the registered construction settlement batch before duplicate replay
  and reject a changed payload under the same idempotency key without append.

### Task 4: Replay and independent evidence

**Files:** Modify existing replay readers as needed; create `.harness/profiles/infra-obligation-lifecycle.json`; create verifier/report.

- [x] Prove full/checkpoint-tail replay equality over the committed construction lifecycle events; no new schema requires an upcaster.
- [x] Add `infra-obligation-lifecycle` with distinct assertions for every admitted capability and rejection.
- [x] Run focused tests, the profile, full pytest, and `git diff --check`; synchronize August analysis, spec, plan and report per enabled owner policy. Reverification on 2026-08-13 added committed source obligation identity zero-write evidence.
