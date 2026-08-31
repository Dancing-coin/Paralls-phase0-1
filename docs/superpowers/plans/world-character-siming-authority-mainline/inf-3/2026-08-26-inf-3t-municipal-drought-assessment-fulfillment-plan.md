# INF-3T Municipal Drought Assessment Fulfillment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the one Contract-owned municipal assessment completion step without creating a generic contract completion authority.

**Architecture:** A row-specific Contract intent rereads the INF-3S-created active service record and its pinned advisory origin, derives the fixed completion evidence and idempotency key, then appends the only permitted two-event Contract batch. Existing Contract, Economy, Ownership, EventStore, and replay boundaries remain separate.

**Tech Stack:** Python, Pydantic, GameplayCommandEnvelope, SettlementPlan, GameplayEventStore, pytest, repository Harness.

---

### Task 1: Lock the row contract with RED tests

**Files:**
- Create: `backend/tests/test_inf3t_municipal_drought_assessment_fulfillment.py`
- Modify: `backend/app/gameplay/contract_runtime.py`

- [x] **Step 1: Write failing success/replay tests**

Create an INF-3S-created active municipal Contract, invoke the new fixed intent,
and assert exactly `service_completion_recorded`, then `record_fulfilled`, both
authority-only; assert derived evidence/idempotency; assert one append receipt
and full/checkpoint-tail `ContractProjector` equivalence.

- [x] **Step 2: Run the focused test to verify RED**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest backend/tests/test_inf3t_municipal_drought_assessment_fulfillment.py -q`

Expected: FAIL because the row-specific intent/method/catalog identity is absent.

- [x] **Step 3: Add failure tests**

Cover wrong/missing source creation event, wrong terms/evidence/party/advisory
origin, inactive or already fulfilled record, stale advisory/Contract pin,
policy missing, catalog mismatch, changed duplicate, and forged caller evidence
or authority fields. Each asserts the pre-append snapshot is identical.

### Task 2: Admit only the immutable exact descriptor/catalog row

**Files:**
- Modify: `backend/app/gameplay/governed_contract_catalog.py`
- Test: `backend/tests/test_infra_governed_authority_contract_catalog.py`

- [x] **Step 1: Write failing catalog/descriptor assertions**

Assert that the catalog exposes only
`inf:municipal-drought-assessment-contract-fulfillment@1`, owner
`actor_gameplay.contract_domain`, stream `gameplay:contracts`, the exact two
Contract event types, authority-only projection, EventStore receipt, and
ContractProjector replay. Assert the descriptor fixes its one capability,
outcome, predicate, and effect type.

- [x] **Step 2: Install static immutable metadata**

Add the exact catalog row and descriptor to the existing frozen-return tuples.
Add no registration API, lookup router, or mutable catalog behavior.

- [x] **Step 3: Run catalog tests**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest backend/tests/test_infra_governed_authority_contract_catalog.py backend/tests/test_inf3t_municipal_drought_assessment_fulfillment.py -q`

Expected: PASS.

### Task 3: Implement the fixed Contract vertical

**Files:**
- Modify: `backend/app/gameplay/contract_runtime.py`
- Test: `backend/tests/test_inf3t_municipal_drought_assessment_fulfillment.py`

- [x] **Step 1: Add the strict intent and source verifier**

Accept only source creation event id, exact advisory/Contract revision pins,
command metadata, and an exact authority-derived idempotency key. Derive the
contract id, fixed authority, policy, completion evidence kind/ref, stream,
visibility, event vector, and receipt coordinates internally.

- [x] **Step 2: Build the two-event canonical append batch**

Use `GameplayCommandEnvelope` with `event_specs`, pass it through
`SettlementPlan.from_command_envelope(...).to_atomic_event_batch()`, then call
the existing `GameplayEventStore.append_batch()` exactly once. Require the
immutable catalog row before batch construction.

- [x] **Step 3: Run the focused suite**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest backend/tests/test_inf3t_municipal_drought_assessment_fulfillment.py backend/tests/test_inf3s_government_drought_assessment_contract.py backend/tests/test_inf2ad_municipal_drought_assessment_exchange.py backend/tests/test_inf4u_municipal_drought_assessment_certificate.py -q`

Expected: PASS with the original rows retaining separate source/receipt
boundaries.

### Task 4: Add independent evidence and synchronize documents

**Files:**
- Create: `.harness/profiles/inf3t-municipal-drought-assessment-fulfillment.json`
- Create: `scripts/verification/verify_inf3t_municipal_drought_assessment_fulfillment.py`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/2026-08-15-inf-mainline-completion-audit.md`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/2026-08-17-inf-mainline-continuation-checkpoint.md`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/2026-08-26-owner-operation-conflict-matrix-baseline.md`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/inf-3/README.md`

- [x] **Step 1: Write the independent Harness**

The verifier must run the focused test file and assert the generated trace
proves the two-event order, one receipt, all required zero-write cases,
authority-only privacy, source/current revision pins, duplicate behavior, and
full/checkpoint-tail replay equality.

- [x] **Step 2: Run all named evidence**

Run the INF-3T profile, its focused suite, `infra-continuation-gate`, docs
profile, and `git diff --check`.

- [x] **Step 3: Record the final row partition**

Change the contract, plan, matrix, audit, README, and checkpoint to
`implemented narrow vertical` only after every named command passes. State
explicitly that INF-2AD payment and INF-4U certificate require a separate
command after the Contract completion receipt and that August INF A-D remains
`not complete`.
