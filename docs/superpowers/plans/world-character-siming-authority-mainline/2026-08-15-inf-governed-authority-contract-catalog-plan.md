# INF Governed Authority Contract Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish one immutable contract catalog shared by the existing INF
authorities without creating a writer or widening any authority.

**Architecture:** `governed_contract_catalog.py` is a pure typed reader with a
fixed tuple of existing authority contracts. Participating authorities invoke
the reader as a pre-append admission assertion; domain validation and all
append/outbox/replay behavior remain local.

**Tech Stack:** Python, Pydantic models, existing `GameplayEventStore`, pytest,
repository Harness.

---

### Task 1: Define catalog and RED contract-shape tests

**Files:**
- Create: `backend/app/gameplay/governed_contract_catalog.py`
- Create: `backend/tests/test_infra_governed_authority_contract_catalog.py`

- [x] Write tests that assert the approved contract references,
  exact owner/stream/privacy/receipt/replay metadata, and unknown/kind-mismatch
  zero-write admission rejection.
- [x] Run `python -m pytest -q backend/tests/test_infra_governed_authority_contract_catalog.py` and confirm RED.
- [x] Add a frozen `GovernedAuthorityContract` and `GovernedAuthorityContractCatalog.require()` with no mutation method.
- [x] Rerun the focused test and confirm PASS.

### Task 2: Consume the catalog in existing owners

**Files:**
- Modify: `backend/app/gameplay/organization_government_runtime.py`
- Modify: `backend/app/gameplay/debt_runtime.py`

- [x] Add failing focused tests that monkeypatch the catalog's fixed row to a
  mismatched owner/stream and assert each affected owner rejects before a store
  write.
- [x] Make Government policy registration, Debt issue/repayment, the fixed
  weather-front Organization edge, and Organization supply promotion require
  their own catalog entry before constructing their existing formal plans.
- [x] Rerun the focused owner tests and confirm their existing success,
  duplicate, stale-revision, privacy and replay assertions still pass.

### Task 3: Independent evidence and documentation sync

**Files:**
- Create: `scripts/verification/verify_infra_governed_authority_contract_catalog.py`
- Create: `.harness/profiles/infra-governed-authority-contract-catalog.json`
- Modify: `docs/harness.md`
- Modify: `docs/8月分析/世界基础设施增量指导/README.md`

- [x] Add one Harness selector per catalog contract plus independent unknown
  contract and owner-enforcement selectors.
- [x] Run the focused profile, docs profile, checkpoint-tail-focused tests,
  `git diff --check`, then `python -m pytest -q`.
- [x] Update the completion audit: the catalog is a governed extension
  substrate, not completion of arbitrary settlement or group simulation.

### Follow-up: INF-2R payroll contract rows

- [x] Add discrete Organization operating-window and Economy wage-payment
  contract rows with exact owner, stream, event, scope, receipt and replay
  metadata.
- [x] Add distinct pre-append zero-write tests for the Organization and
  Economy rows, plus individual Harness selectors for metadata, receipt/privacy,
  duplicate/revision conflict and checkpoint-tail replay.
- [x] Keep the catalog immutable and source-controlled; no caller registration
  or coordinator append path is added.
