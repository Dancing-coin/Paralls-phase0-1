# INF-2AE Facility Commissioning Review Exchange Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Status:** `implemented narrow vertical; verified; August INF A-D remain not complete`

**Goal:** Close one product-significant post-commissioning service exchange using existing Contract and Economy owners.

**Architecture:** Construction's committed INF-1AI verification is read-only source evidence. Contract derives the facility operator party from the committed acquisition plot, creates and fulfills one fixed service contract, and Economy consumes only that fulfilled exact contract through the existing package-declared exchange path. No cross-owner combined batch is introduced.

**Tech Stack:** Python, Pydantic, GameplayPatchManifest v2, GameplayPatchRegistry, Contract/Economy authorities, GameplayEventStore, pytest, Harness.

---

### Task 1: Write RED tests for source admission and Contract lifecycle

**Files:**
- Create: `backend/tests/test_inf2ae_facility_commissioning_review_contract.py`

- [x] Build INF-1AI source evidence and assert exact derived receiver, service terms, project binding and Contract event pair.
- [x] Assert generic create/complete/fulfill/terminate cannot bypass the exact service terms.
- [x] Assert missing/private/stale/multiple source and changed duplicate are zero-write.
- [x] Run the focused file as RED before implementation, then record the green result after the row-specific intent/method were added.

### Task 2: Implement Contract source admission and fulfillment

**Files:**
- Modify: `backend/app/gameplay/contract_runtime.py`
- Test: `backend/tests/test_inf2ae_facility_commissioning_review_contract.py`

- [x] Add strict source-bound intents and fixed methods deriving party/policy/evidence/idempotency coordinates.
- [x] Append creation and fulfillment through the existing envelope/SettlementPlan/EventStore spine.
- [x] Add exact projector/replay and generic-entry fences.

### Task 3: Freeze the immutable v4 package

**Files:**
- Create: `docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/package-industrial-facilities-v4-commissioning-review.manifest.json`
- Create: package digest/freeze record
- Test: `backend/tests/test_inf2ae_facility_commissioning_review_package.py`

- [x] Validate the schema pair `(2, "1.0")`, fixed service/evidence/price/currency, canonical array order, declaration digest and content digest.
- [x] Install/activate only the immutable v4 candidate in focused tests; do not mutate v1/v2/v3.

### Task 4: Implement Economy settlement and evidence

**Files:**
- Modify: `backend/app/gameplay/economy_runtime.py` only if the existing exact package exchange needs a row fence.
- Create: `backend/tests/test_inf2ae_facility_commissioning_review_exchange.py`
- Create: `.harness/profiles/inf2ae-facility-commissioning-review-exchange.json`
- Create: `scripts/verification/verify_inf2ae_facility_commissioning_review_exchange.py`

- [x] Settle only the exact fulfilled service package row with exact-one accounts and fixed 12-unit policy.
- [x] Verify receipt, authority privacy, source/revision pins, duplicate/changed duplicate, insufficient funds, account ambiguity, and full/tail replay.
- [x] Run INF-2AE, INF-1AI, municipal chain, continuation, docs and complete INF-focused tests.

### Task 5: Synchronize governing records

**Files:**
- Modify: INF-2 README/plan README, owner-operation matrix, completion audit, remaining-scope, blocker taxonomy, continuation checkpoint.

- [x] Mark only INF-2AE's exact Contract and Economy rows implemented after all evidence passes.
- [x] Keep generic payment/transfer and other INF-2 slots blocked; keep August INF A-D not complete.
