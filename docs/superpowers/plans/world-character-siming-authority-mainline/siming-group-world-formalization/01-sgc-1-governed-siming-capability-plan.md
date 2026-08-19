# SGC-1 Governed Siming Capability Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task after the contract is approved.

**Goal:** Bind one Siming typed intent to one existing catalog capability without a new writer or router.

**Spec:** `docs/superpowers/specs/world-character-siming-authority-mainline/siming-group-world-formalization/01-sgc-1-governed-siming-capability-contract.md`

**Prerequisite:** The owner-contract matrix identifies one complete existing owner row. Otherwise execute Task 1 only and record `owner-contract blocked`.

### Task 0: Admission gate

**Files:** `docs/superpowers/specs/world-character-siming-authority-mainline/siming-group-world-formalization/01-sgc-1-governed-siming-capability-contract.md`, applicable INF owner matrix, `.harness/verification/`

- [ ] Confirm the selected row has owner, event family, stream, source, revision, privacy, idempotency, receipt, replay and compensation evidence.
- [ ] If any field is missing, write the blocker evidence and stop with `owner-contract blocked`; do not create a catalog entry, test-green claim or runtime adapter.
- [ ] Record the selected row and current catalog revision in the package checkpoint before implementation.

### Task 1: Freeze the row and RED contract

**Files:** `docs/superpowers/specs/world-character-siming-authority-mainline/siming-group-world-formalization/01-sgc-1-governed-siming-capability-contract.md`, `docs/superpowers/plans/world-character-siming-authority-mainline/siming-group-world-formalization/01-sgc-1-governed-siming-capability-plan.md`, `backend/tests/test_siming_governed_capability_contract.py`

- [ ] Record capability ref/version, fixed owner, stream/event family, source vector, scope, revision, idempotency, receipt and compensation.
- [ ] Add RED tests for unknown/version/schema/scope/source/target/duplicate rejection and assert no `append_batch()` call.
- [ ] Run `pytest backend/tests/test_siming_governed_capability_contract.py -q` and preserve the expected RED evidence.

### Task 2: Implement only the admitted guard

**Files:** `backend/app/gameplay/governed_contract_catalog.py`, `backend/app/services/siming_intervention_guardrails.py`, `backend/app/services/siming_audit_writer.py`

- [ ] Add the immutable source-controlled entry through the existing catalog data surface.
- [ ] Resolve the owner operation before `SettlementPlan`; reject caller-selected operation fields.
- [ ] Add no registration method, generic adapter, or second append surface.
- [ ] Re-run the focused tests until the approved success path is green and all rejection paths remain zero-write.

### Task 3: Harness and audit closure

**Files:** `scripts/verification/harness.py`, `scripts/verification/registry.py`, `.harness/profiles/sgc-1-governed-siming-capability.json`, `.harness/rules/sgc-1-governed-siming-capability.json`, `docs/harness.md`, applicable INF audit/plan/checkpoint

- [ ] Register the selector through the existing profile/rule manifests; do not add a runtime registry or direct profile dispatch branch.
- [ ] Add one selector named `sgc-1-governed-siming-capability` covering success, privacy, revision, exact/changed duplicate, receipt, full replay and checkpoint-tail replay.
- [ ] Run focused pytest, the selector, and `git diff --check`.
- [ ] Save the focused output and Harness report under `.harness/verification/sgc-1/` with environment, catalog revision and source digest.
- [ ] Mark only `implemented narrow vertical` after evidence; otherwise retain `owner-contract blocked`.
