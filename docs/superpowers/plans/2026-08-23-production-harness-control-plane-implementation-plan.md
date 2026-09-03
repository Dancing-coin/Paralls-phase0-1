# Production Harness Control Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the production-oriented Harness control plane around existing domain authorities and pass fresh full Harness verification.

**Architecture:** Replace the process-only task ledger with a SQLite-backed control-plane store, then adapt existing domain results into the shared failure and evidence contracts. Keep authority writes in ESM, GameplayEventStore, embodied services, and transport publishers; the Harness owns execution metadata only.

**Tech Stack:** Python 3.11+, Pydantic v2, stdlib `sqlite3`, existing Gameplay/EventStore/outbox/Godot probes, pytest.

**Spec:** `docs/superpowers/specs/2026-08-23-production-harness-control-plane-design.md`

## Global Constraints

- No new third-party dependencies.
- No new domain truth owner.
- Every mutation is scoped by task identity and expected task revision.
- Every trace payload is redacted before persistence.
- Existing domain idempotency and replay contracts remain authoritative.
- Siming and CharacterAgent business behavior remain unchanged.

### Task 1: Durable control-plane store

**Files:**
- Create: `backend/app/services/harness_task_ledger.py`
- Modify: `backend/app/models/harness_execution.py`
- Test: `backend/tests/test_harness_task_ledger.py`

**Interfaces:**
- `HarnessTaskLedger.create(envelope) -> ExecutionEnvelope`
- `HarnessTaskLedger.transition(task_id, expected_revision, phase, ...) -> ExecutionEnvelope`
- `HarnessTaskLedger.append_trace(task_id, expected_revision, record) -> TaskTraceRecord`
- `HarnessTaskLedger.read(task_id) -> ExecutionEnvelope`
- `HarnessTaskLedger.list_trace(task_id) -> list[TaskTraceRecord]`
- `HarnessTaskLedger.recover(task_id) -> ExecutionEnvelope`

- [ ] Write RED tests for SQLite restart recovery, task revision CAS rejection, idempotent create, and terminal re-execution rejection.
- [ ] Run the focused tests and observe the missing ledger failure.
- [ ] Implement SQLite schema, WAL mode, atomic mutations, and migration version check using stdlib `sqlite3`.
- [ ] Run the focused ledger tests and existing execution-contract tests.

### Task 2: Durable capability gate and metadata policy

**Files:**
- Create: `backend/app/services/harness_capability_store.py`
- Modify: `backend/app/services/harness_execution_trace.py`
- Test: `backend/tests/test_harness_capability_store.py`

**Interfaces:**
- `issue(principal_ref, task_id, phase, policy_revision, expires_at, nonce) -> CapabilityGrant`
- `consume(grant_id, task_id, phase, correlation_id, now) -> CapabilityGrant`
- `redact_metadata(value) -> dict[str, object]`

- [ ] Write RED tests for scoped grants, expiry, nonce replay, one-time consumption, and forbidden metadata.
- [ ] Run the tests to verify they fail before implementation.
- [ ] Implement persistent grant state with compare-and-set updates and reuse the trace redaction policy.
- [ ] Run capability, execution, and embodied task tests.

### Task 3: Failure adapters and task integration

**Files:**
- Create: `backend/app/services/harness_failure_adapters.py`
- Modify: `backend/app/services/embodied_harness_task.py`
- Modify: `backend/app/services/interaction_orchestration_service.py`
- Modify: `backend/app/services/embodied_execution_ingress.py`
- Modify: `backend/app/services/esm_service.py`
- Modify: `backend/app/gameplay/event_store.py`
- Test: `backend/tests/test_harness_failure_adapters.py`
- Test: `backend/tests/test_harness_task_integrations.py`

- [ ] Write RED tests mapping representative native errors from ESM, Gameplay, embodied ingress, and transport to common `FailureKind` values while preserving native codes.
- [ ] Run the tests and verify the adapters are absent.
- [ ] Implement explicit adapter tables and emit task trace records at the existing integration seams.
- [ ] Ensure domain owners still perform all canonical writes.
- [ ] Run the existing ESM, Gameplay, embodied, and transport suites.

### Task 4: Evidence join and transport/Godot receipt

**Files:**
- Modify: `backend/app/services/embodied_harness_task.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/gameplay_mirror_connection_registry.py`
- Modify: `scripts/verification/verify_harness_embodied_task.py`
- Test: `backend/tests/test_harness_evidence_join.py`

- [ ] Write RED tests for authority receipt, EventStore sequence, outbox delivery, Godot receipt, replay hash, and verifier run ID joining.
- [ ] Run the tests and observe missing terminal evidence.
- [ ] Implement bounded evidence references and delivery callbacks; reject raw payloads.
- [ ] Run embodied interaction, Godot mirror, replay, and Harness task profiles.

### Task 5: Full-all gate repair

**Files:**
- Modify: `scripts/verification/SimingHeavenlyRuntimeProbe.gd` or its verifier only where the current marker contract is stale.
- Modify: `scripts/verification/verify_siming_heavenly_runtime.py`
- Test: existing Siming heavenly runtime verifier tests.

- [ ] Reproduce the current `godot_restart_marker_missing` or `godot_complete_marker_missing` with a fresh isolated runtime path.
- [ ] Trace the marker lifecycle and identify whether the failure is probe, backend reconnect, or verifier timeout.
- [ ] Write a failing regression test for the exact marker contract.
- [ ] Apply the smallest runtime-verification repair without adding Siming business behavior.
- [ ] Run the explicit heavenly runtime profile three times and then run `--profile all`.

### Task 6: Completion verification

- [ ] Run `python -m pytest -q`.
- [ ] Run `python scripts/verification/harness.py --profile harness-embodied-task --godot-exe ...`.
- [ ] Run the ESM, Gameplay, transport, embodied, and mainline profiles.
- [ ] Run `python scripts/verification/harness.py --profile all --godot-exe ...` with an isolated runtime path.
- [ ] Read the final report and confirm no required profile is missing or merely artifact-backed after a failed run.
