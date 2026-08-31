# INF-3U Municipal Certificate Government Acknowledgment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let existing GovernmentAuthority acknowledge one exact INF-4U municipal assessment certificate without widening privacy or adding a generic Government lifecycle.

**Architecture:** A strict row-specific intent validates the immutable certificate, Contract completion, original advisory, and current heads. Government appends one authority-only acknowledgment event and exposes a dedicated authority-only replay view. The existing project advisory view and WebSocket presentation remain issuance-only.

**Tech Stack:** Python, Pydantic, GameplayCommandEnvelope, SettlementPlan, GameplayEventStore, pytest, repository Harness.

---

### Task 1: Write RED source and target tests

**Files:**
- Create: `backend/tests/test_inf3u_municipal_certificate_government_acknowledgment.py`
- Modify: `backend/app/gameplay/organization_government_runtime.py`

- [x] **Step 1: Write the failing success/replay test**

Build the exact INF-3R -> INF-3S -> INF-3T -> INF-4U source chain. Request
the Government acknowledgment and assert one authority-only event, append
receipt, dedicated acknowledgment full/checkpoint-tail replay equality, and no
change to the project advisory view.

- [x] **Step 2: Verify RED**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest backend/tests/test_inf3u_municipal_certificate_government_acknowledgment.py -q`

Expected: FAIL because the strict intent/method/catalog/view is absent.

- [x] **Step 3: Add zero-write tests**

Cover missing/forged/stale/private certificate, stale Contract/advisory/Government
heads, changed duplicate, wrong deterministic right/asset/holder, catalog
mismatch, duplicate certificate acknowledgment, and attempted project visibility.

### Task 2: Admit exact immutable metadata

**Files:**
- Modify: `backend/app/gameplay/governed_contract_catalog.py`
- Test: `backend/tests/test_infra_governed_authority_contract_catalog.py`

- [x] **Step 1: Write failing catalog/descriptor assertions**

Assert one `settlement` catalog row for the fixed Government stream/event,
authority-only receipt/replay, and one descriptor with only the source
certificate predicate/effect pair.

- [x] **Step 2: Extend only static tuples**

Add no registration, router, coordinator, or mutable catalog behavior.

### Task 3: Implement the fixed Government vertical

**Files:**
- Modify: `backend/app/gameplay/organization_government_runtime.py`
- Test: `backend/tests/test_inf3u_municipal_certificate_government_acknowledgment.py`

- [x] **Step 1: Add strict intent and acknowledgment view**

Read exact certificate/advisory/Contract evidence, pin all source and target
heads, and project only fixed acknowledgments under authority scope.

- [x] **Step 2: Append exactly one Government event**

Derive every identifier, policy, event, stream, visibility, and idempotency key
inside GovernmentAuthority; append once through the canonical envelope/plan
spine.

- [x] **Step 3: Run adjacent regression tests**

Run INF-3R/3S/3T, INF-2AD, INF-4U, existing advisory presentation, and new
INF-3U tests. Confirm no project view or WebSocket presentation change.

### Task 4: Add independent evidence and documentation

**Files:**
- Create: `.harness/profiles/inf3u-municipal-certificate-government-acknowledgment.json`
- Create: `scripts/verification/verify_inf3u_municipal_certificate_government_acknowledgment.py`
- Modify: mainline audit, remaining-scope, INF-3 README/plan README, blocker taxonomy, matrix, and checkpoint

- [x] **Step 1: Add independent Harness**

Run success/replay, source/privacy/revision/idempotency zero-write, catalog
exactness, and project-presentation non-widening selectors.

- [x] **Step 2: Run final evidence**

Run the INF-3U profile, municipal closed-loop profile, continuation gate, docs
profile, `git diff --check`, and the complete INF-focused pytest corpus.

- [x] **Step 3: Mark only this row implemented**

Record `implemented narrow vertical` only after every command passes. Preserve
August INF A-D as `not complete` and all remaining formal blockers.
