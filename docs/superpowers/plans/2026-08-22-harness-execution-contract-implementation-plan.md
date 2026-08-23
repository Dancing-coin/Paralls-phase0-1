# Harness Execution Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a domain-neutral Harness execution envelope, failure disposition policy, and task-level trace service.

**Architecture:** Keep the contract in `backend/app/models` and a small in-memory service in `backend/app/services`. The service validates lifecycle transitions and appends trace records but delegates all domain execution and authority writes to existing owners.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, existing Harness registry and report helpers.

**Spec:** `docs/superpowers/specs/2026-08-22-harness-execution-contract-design.md`

## Global Constraints

- No new third-party dependencies.
- No Siming or CharacterAgent behavior changes.
- No new authority owner, event store, transport, or persistence layer.
- Terminal execution phases are immutable.
- Generated evidence remains under `.harness/verification/`.

### Task 1: Add the typed execution contract

**Files:**
- Create: `backend/app/models/harness_execution.py`
- Test: `backend/tests/test_harness_execution_contract.py`

**Interfaces:**
- Produces `ExecutionEnvelope`, `FailureDisposition`, `TaskTraceRecord`, `classify_failure`, and the `ExecutionPhase`/`FailureKind` literals.

- [ ] **Step 1: Write failing model and policy tests**

```python
def test_failure_policy_is_deterministic() -> None:
    assert classify_failure("stale_revision").recovery_action == "refresh_revision"
    assert classify_failure("transient").retryable is True
    assert classify_failure("permission_denied").retryable is False

def test_execution_envelope_rejects_empty_identity() -> None:
    with pytest.raises(ValidationError):
        ExecutionEnvelope(task_id="", run_id="run:1", correlation_id="corr:1")
```

- [ ] **Step 2: Run the focused tests and verify the expected missing-module failure**

Run: `python -m pytest -q backend/tests/test_harness_execution_contract.py`

Expected: collection fails because `app.models.harness_execution` does not exist.

- [ ] **Step 3: Implement the minimal Pydantic models and closed failure mapping**

Use strict non-empty identity fields, bounded non-negative `attempt`/`max_attempts`, and the phase/failure literals from the spec. `classify_failure` must return a fresh `FailureDisposition` for each call.

- [ ] **Step 4: Run the focused tests**

Run: `python -m pytest -q backend/tests/test_harness_execution_contract.py`

Expected: PASS.

### Task 2: Add the in-memory lifecycle and trace service

**Files:**
- Create: `backend/app/services/harness_execution_trace.py`
- Modify: `backend/tests/test_harness_execution_contract.py`

**Interfaces:**
- Consumes the models from Task 1.
- Produces `HarnessExecutionTraceService.start(...)`, `.transition(...)`, `.record(...)`, `.get_envelope(...)`, and `.get_trace(...)`.

- [ ] **Step 1: Add failing lifecycle and trace tests**

```python
def test_service_rejects_terminal_transition_and_preserves_trace() -> None:
    service = HarnessExecutionTraceService()
    service.start(task_id="task:1", run_id="run:1", correlation_id="corr:1")
    service.transition("task:1", "running", producer_ts=1)
    service.transition("task:1", "committed", producer_ts=2)
    with pytest.raises(ValueError):
        service.transition("task:1", "running", producer_ts=3)
    assert [row.sequence for row in service.get_trace("task:1")] == [1, 2]

def test_failure_transition_records_disposition() -> None:
    service = HarnessExecutionTraceService()
    service.start(task_id="task:2", run_id="run:2", correlation_id="corr:2")
    envelope = service.transition("task:2", "failed", producer_ts=4, failure_kind="stale_revision")
    assert envelope.failure.recovery_action == "refresh_revision"
```

- [ ] **Step 2: Run the tests and verify the new service failure**

Run: `python -m pytest -q backend/tests/test_harness_execution_contract.py`

Expected: the new service tests fail because `HarnessExecutionTraceService` is absent.

- [ ] **Step 3: Implement the minimal service**

Store one envelope and one list of trace records per task. Validate transition membership, reject unknown task IDs and terminal writes, increment sequence monotonically, and copy metadata dictionaries so callers cannot mutate stored trace rows.

- [ ] **Step 4: Run focused tests and the existing backend contract suite**

Run: `python -m pytest -q backend/tests/test_harness_execution_contract.py backend/tests/test_backend_contract.py`

Expected: PASS.

### Task 3: Add the focused Harness profile and documentation

**Files:**
- Create: `scripts/verification/verify_harness_execution_contract.py`
- Create: `.harness/profiles/harness-execution-contract.json`
- Create: `.harness/rules/harness-execution-contract-rules.json`
- Modify: `docs/harness.md`
- Modify: `docs/INDEX.md`
- Test: `scripts/verification/tests/test_harness_execution_contract_verify.py`

- [ ] **Step 1: Write the failing verifier test**

Assert the verifier reports `overall_harness_execution_contract_passed=True` and includes lifecycle, failure-policy, terminal-guard, and trace-correlation results.

- [ ] **Step 2: Run the verifier test and verify it fails**

Run: `python -m pytest -q scripts/verification/tests/test_harness_execution_contract_verify.py`

Expected: import or profile lookup failure.

- [ ] **Step 3: Implement verifier/profile/rules/docs**

The verifier must run the focused pytest file, execute one committed path and one stale-revision failure path, write JSON/Markdown reports, and return non-zero on any missing result. Register the profile before `character-behavior-evaluation` and document its scope and command.

- [ ] **Step 4: Run focused Harness checks**

Run:

```powershell
python scripts/verification/harness.py --profile harness-execution-contract
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile harness-lifecycle
```

Expected: all three profiles pass.

### Task 4: Complete verification

- [ ] **Step 1: Run the focused backend suite**

Run: `python -m pytest -q backend/tests/test_harness_execution_contract.py`

- [ ] **Step 2: Run workflow and boundary profiles**

Run: `python scripts/verification/harness.py --profile change-lifecycle` and `python scripts/verification/harness.py --profile boundaries`.

- [ ] **Step 3: Run the full harness**

Run: `python scripts/verification/harness.py --profile all`.

Report any pre-existing unrelated failures separately; do not broaden this slice to repair them.
