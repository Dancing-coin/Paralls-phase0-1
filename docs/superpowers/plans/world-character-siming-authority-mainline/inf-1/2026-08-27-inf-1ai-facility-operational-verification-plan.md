# INF-1AI Facility Operational Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans (recommended) to implement this plan task-by-task.

**Goal:** Record one replayable Construction-owned operational verification after a committed completed production run.

**Architecture:** Construction rereads exact run-start/run-finished evidence and the current facility projection, derives all target coordinates and pins, then appends one fixed project event. The existing Construction projector adds a dedicated verification map; Production, Inventory and Economy facts remain separate.

**Tech Stack:** Python, Pydantic, GameplayCommandEnvelope, SettlementPlan, GameplayEventStore, pytest, Harness.

---

### Task 1: RED tests

**Files:**
- Create: `backend/tests/test_inf1ai_facility_operational_verification.py`

- [x] Write success, full/tail replay, receipt, duplicate and changed-duplicate tests.
- [x] Write zero-write tests for missing/private/stale/wrong source, missing provenance, decommissioned facility, existing verification, catalog mismatch, and caller-selected coordinates.
- [x] Run the RED command and observe the expected missing intent/method/projector/catalog failure.

### Task 2: Existing Construction owner implementation

**Files:**
- Modify: `backend/app/gameplay/construction_production_runtime.py`

- [x] Add strict `FacilityOperationalVerificationIntentV1` and `FacilityOperationalVerification` projection record.
- [x] Add the event family to the existing projector and validate exact source/run/facility/project/revision pins.
- [x] Add `verify_facility_operationally()` that builds one envelope/plan/append batch and returns append-derived receipt data.

### Task 3: Immutable admission metadata

**Files:**
- Modify: `backend/app/gameplay/governed_contract_catalog.py`
- Test: `backend/tests/test_infra_governed_authority_contract_catalog.py`

- [x] Add only the exact lifecycle catalog row and descriptor with the fixed predicate/effect family.
- [x] Extend catalog exactness assertions; add no mutable registration or generic resolver.

### Task 4: Independent Harness and documentation

**Files:**
- Create: `.harness/profiles/infra-construction-facility-operational-verification.json`
- Create: `scripts/verification/verify_infra_construction_facility_operational_verification.py`
- Modify: INF-1 contract/plan README, completion audit, remaining-scope, matrix, blocker taxonomy and continuation checkpoint.

- [x] Run focused tests, catalog regression, INF-1AI Harness, continuation gate, docs Harness and `git diff --check`.
- [x] Run the complete INF-focused test corpus.
- [x] Mark only INF-1AI `implemented narrow vertical`; keep August INF A-D `not complete` and all generic prohibitions.
