# System L1 ESM Full-Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the current strengthened `ESM` slice into a repository-local full-domain `System L1` subdomain with an explicit settlement matrix, clearer state templates, and stronger field / propagation semantics.

**Architecture:** Keep `ESM` inside `System L1`. Extend depth, not scope: more explicit settlement classes, more explicit state template boundaries, and clearer field semantics. Do not turn `ESM` into cognition, narrative meaning, or higher-layer orchestration.

**Tech Stack:** Python 3.13, FastAPI backend, Pydantic, pytest, current `world_result` and verification surfaces.

---

## Status Snapshot

- Date: `2026-06-10`
- Plan status: repo-local target completed and verified
- Current execution rule: continue using TDD and run the three verification scripts serially only
- Current code truth:
  - repository-local settlement matrix is explicit and verified
  - follow-on success results now preserve the originating `ActionRequest` lineage through shared `request_ref` / `causation_id` / `correlation_id`
  - repo-local capability boundaries are now explicit in code, including unsupported environment-request rejection behavior
  - environment machine templates are now explicit for the runtime-used `light_source` / `heat_source` / `smoke_source` / `noise_source` ids
  - a minimal repo-local workbench snapshot surface now exists in code, including a bounded recent-history window
  - variant-family support policy is now explicit in code for environment requests
  - latest backend full suite and runtime verification triad are green on this worktree
- Remaining gap:
  - this child plan is complete for the repo's current repository-local `ESM` full-domain target
  - it is not the same thing as a full production `ESM` workbench or a broader main-project settlement matrix, so the parent `system-l1-full-phase1` plan still needed separate close-out verification
- Verification evidence:
  - `backend/tests/test_esm_service.py::test_esm_service_exposes_repo_local_capability_manifest`
  - `backend/tests/test_esm_service.py::test_esm_service_exposes_repo_local_workbench_snapshot`
  - `backend/tests/test_esm_service.py::test_esm_service_workbench_snapshot_keeps_latest_request_and_resolution_even_when_last_request_is_rejected`
  - `backend/tests/test_esm_service.py::test_esm_service_workbench_snapshot_exposes_recent_history_window`
  - `backend/tests/test_ws_protocol.py::test_websocket_environment_request_accepts_light_level_restore_variant`
  - `backend/tests/test_ws_protocol.py::test_websocket_environment_request_accepts_thermal_level_rise_variant`
  - `backend/tests/test_ws_protocol.py::test_websocket_environment_request_accepts_smoke_density_rise_variant`
  - `backend/tests/test_ws_protocol.py::test_websocket_environment_request_accepts_noise_level_rise_variant`
  - `backend/tests/test_ws_protocol.py::test_websocket_environment_request_rejects_unsupported_change_type_with_constraint_result`
  - `backend/tests/test_verification_audit.py::test_phase0_audit_requires_explicit_esm_request_lineage_and_thermal_field_evidence`

## Task Status Register

### Task 1: Freeze The Settlement Matrix

- Status: 已做（大部分/已验证，含一条已验证未提交的 request-linkage 收口 slice）
- Landed:
  - explicit interaction success
  - explicit interaction rejection
  - explicit environment-state shift
  - explicit `ActionRequest` runtime message
  - explicit `StateMachineTransitionEvent` runtime message
  - success-path `ObjectStateResult` / `BodyStateResult` / `EnvironmentStateResult` now share the originating interaction request lineage instead of emitting isolated request refs
  - unsupported `environment_request` change types now reject explicitly as `ConstraintStateResult` instead of being silently accepted
  - `get_repo_local_capabilities()` now exposes the current supported / unsupported repo-local ESM boundary in code
  - repo-local supported environment-request variants now include `light_level_drop`、`light_level_restore`、`thermal_level_rise`、`smoke_density_rise`、`noise_level_rise`
  - runtime-used environment machine ids now have explicit templates instead of existing only as emitted strings

### Task 2: Deepen Environment Field Semantics

- Status: 已做（大部分/已验证）
- Landed:
  - `light_level`
  - `noise_level`
  - `thermal_level`
  - `smoke_density`
  - `visibility_level`
  - `field_id`
  - `updated_at`
  - `EnvironmentStateResult.field_id`
  - `EnvironmentStateResult.source_environment_id`
  - `EnvironmentStateResult.updated_at`
  - coarse thermal propagation to adjacent zones
  - adjacent-zone propagation

### Task 3: Strengthen Replay / Debug Proof For ESM

- Status: 已做（大部分/已验证，最新收口 slice 已在当前工作树验证）
- Landed:
  - audit proof for success / failure / environment-state paths
  - replay-friendly stable ids across result objects
  - stable `machine_id` on replay-critical state-result families
  - stable `entity_id` on replay-critical result families
  - websocket protocol tests covering the full emitted chain
  - websocket success-chain assertions now prove follow-on state results keep the originating interaction request lineage
  - phase0 verification now explicitly proves follow-on result request lineage
  - phase0 verification now explicitly proves the coarse thermal-field contract on environment-state evidence

### Task 4: Run Full Regression

- Status: 已按当前对齐 slice 重跑并通过
- Latest verified discipline:
  - `python -m pytest -v`
  - `python scripts/verification/verify_phase1_slice.py`
  - `python scripts/verification/verify_phase0.py`
  - `python scripts/verification/verify_l1_runtime_edges.py`
- Latest verified outputs:
  - `overall_phase1_slice_passed=True`
  - `overall_strict_phase0_passed=True`
  - `overall_l1_runtime_edges_passed=True`

### Task 1: Freeze The Settlement Matrix

**Files:**
- Modify: `backend/app/models/world_result.py`
- Modify: `backend/app/services/esm_service.py`
- Modify: `backend/tests/test_esm_service.py`
- Modify: `backend/tests/test_ws_protocol.py`

- [x] **Step 1: Write the failing tests**

Require explicit repository support for:
- interaction success
- interaction rejection
- environment-state shift
- one additional explicit settlement class or explicit negative policy

- [x] **Step 2: Run the failing tests**

```bash
python -m pytest -v tests/test_esm_service.py tests/test_ws_protocol.py
```

- [x] **Step 3: Implement the minimal matrix**

Do not overbuild. Either:
- add one additional settlement class
- or make the supported matrix explicit through tests and model shape

- [x] **Step 4: Re-run tests**

```bash
python -m pytest -v tests/test_esm_service.py tests/test_ws_protocol.py
```

- Deferred: no repository commit was requested in this session; verified worktree + synced docs are the closure record for this slice.

```bash
git add backend/app/models/world_result.py backend/app/services/esm_service.py backend/tests/test_esm_service.py backend/tests/test_ws_protocol.py
git commit -m "feat: freeze the repository-local ESM settlement matrix"
```

### Task 2: Deepen Environment Field Semantics

**Files:**
- Modify: `backend/app/models/environment_field.py`
- Modify: `backend/app/services/esm_service.py`
- Modify: `backend/tests/test_esm_service.py`

- [x] **Step 1: Write the failing tests**

Add tests for:
- current `light`
- current `noise`
- one more explicit field dimension such as `thermal` or `visibility_state`

- [x] **Step 2: Run the failing tests**

```bash
python -m pytest -v tests/test_esm_service.py
```

- [x] **Step 3: Implement the minimal field extension**

Keep the field system coarse and explicit.
Do not invent a full solver.

- [x] **Step 4: Re-run tests**

```bash
python -m pytest -v tests/test_esm_service.py
```

- Deferred: no repository commit was requested in this session; verified worktree + synced docs are the closure record for this slice.

```bash
git add backend/app/models/environment_field.py backend/app/services/esm_service.py backend/tests/test_esm_service.py
git commit -m "feat: deepen repository-local ESM field semantics"
```

### Task 3: Strengthen Replay / Debug Proof For ESM

**Files:**
- Modify: `backend/app/verification_audit.py`
- Modify: `scripts/verification/verify_phase0.py`
- Modify: `backend/tests/test_verification_audit.py`

- [x] **Step 1: Write failing proof tests**

Require phase verification to explicitly prove:
- stable ESM settlement identity
- explicit field/result evidence
- environment-state proof that goes beyond a single implicit log token

- [x] **Step 2: Run the failing tests**

```bash
python -m pytest -v tests/test_verification_audit.py
```

- [x] **Step 3: Implement the minimal audit extension**

Keep the proof strict, not broad smoke.

- [x] **Step 4: Re-run tests**

```bash
python -m pytest -v tests/test_verification_audit.py
```

- Deferred: no repository commit was requested in this session; verified worktree + synced docs are the closure record for this slice.

```bash
git add backend/app/verification_audit.py scripts/verification/verify_phase0.py backend/tests/test_verification_audit.py
git commit -m "test: strengthen repository-local ESM proof surface"
```

### Task 4: Run Full Regression

- [ ] **Step 1: Run backend tests**

```bash
python -m pytest -v
```

- [ ] **Step 2: Run runtime verification triad serially**

```bash
python scripts/verification/verify_phase1_slice.py
python scripts/verification/verify_phase0.py
python scripts/verification/verify_l1_runtime_edges.py
```

## Recently Closed Slices Registered To This Plan

- visibility-state-family alignment:
  - successful object visibility path now uses `partially_visible -> visible`
  - Godot-side environment result consumption is guarded to `environment_state_result`
- replay/workbench identity alignment:
  - `ActionResolutionResult`
  - `ConstraintStateResult`
  - `ObjectStateResult`
  - `EnvironmentStateResult`
  now all expose stable `entity_id` while keeping existing target-specific compatibility fields
- request-lineage alignment across follow-on success results:
  - `ObjectStateResult`
  - `BodyStateResult`
  - `EnvironmentStateResult`
  now preserve the originating interaction `request_ref` plus shared `causation_id` / `correlation_id`
- thermal-field alignment:
  - `EnvironmentFieldState` now carries explicit `thermal_level`
  - `EnvironmentStateResult` now exposes explicit `thermal_level`
  - environment-state field deltas now register `thermal_level`
  - adjacent propagation softens `warm -> mild_warm`
- explicit negative policy for unsupported environment-request variants:
  - repo-local unsupported `requested_change_type` values now reject with `unsupported_environment_request`
  - websocket runtime emits a constraint-style `world_result` instead of a false accepted path
- explicit repo-local capability surface:
  - supported settlement / constraint / field families are queryable from `ESMService`
  - supported and unsupported environment-request change types are declared in one place
  - supported and unsupported environment-request variant families are declared in one place
- explicit environment machine catalog:
  - `light_source`、`heat_source`、`smoke_source`、`noise_source` are now queryable template ids, aligned with emitted runtime machine ids
- minimal repo-local workbench snapshot surface:
  - `ESMService` now exposes a snapshot containing template ids, material ids, environment machine ids, supported/unsupported change types, current environment field state, latest environment request, latest environment resolution, latest environment result, latest state-machine transition, and a bounded recent history window
- fifth supported environment-request variant:
  - `light_level_restore` now resolves to an accepted `EnvironmentStateResult`
  - runtime emits `light_source` machine transitions from `alerted -> stable`
- third supported environment-request variant:
  - `smoke_density_rise` now resolves to an accepted `EnvironmentStateResult`
  - runtime emits `smoke_source` machine transitions and a smoke-rising environment-state path
- fourth supported environment-request variant:
  - `noise_level_rise` now resolves to an accepted `EnvironmentStateResult`
  - runtime emits `noise_source` machine transitions and a noisy environment-state path
- second supported environment-request variant:
  - `thermal_level_rise` now resolves to an accepted `EnvironmentStateResult`
  - runtime emits `heat_source` machine transitions and a heated environment-state path
