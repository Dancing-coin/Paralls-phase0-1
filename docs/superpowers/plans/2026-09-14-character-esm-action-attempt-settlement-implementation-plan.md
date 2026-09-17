# Character ESM Action Attempt Settlement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect locally admitted actions and physical evidence to ESM/Gameplay authority settlement without confusing animation markers or local collision with world truth.

**Architecture:** The actor runtime emits an `ActionAttempt` at a qualified timing marker. The backend validates identity, revisions, idempotency, route, physical evidence, and domain preconditions before committing an atomic event batch or returning a typed rejection. Results flow back as projections only.

**Tech Stack:** Python backend models/services, existing ESM and Gameplay authority stores, Godot GDScript interaction controller, pytest, and Harness integration profiles.

**Spec:** `docs/superpowers/specs/2026-09-14-character-esm-action-attempt-settlement-subspec.md`

**Execution status:** Task-level reference for Task 10 of
`docs/superpowers/plans/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-implementation-plan.md`.
The unified plan is the only implementation order; this file does not define
an alternate runtime path or release gate.

## Global Constraints

- ESM owns environment affordance, access, occupancy, reservation, and object state.
- Gameplay owns actor resources, statuses, capabilities, equipment, and actor projections.
- CharacterAgent, INF, Siming, animation markers, and colliders only propose or evidence actions.
- Phase 1 `authority_route_ref` is limited to `esm`, `gameplay`, or
  `composite`; INF may contribute only through a server-registered
  `owner_contract_ref` and is never a generic settlement writer.
- Duplicate retries return the original result; same-key different-payload is rejected.
- Unknown commit status is queried with the original idempotency key.
- No partial writes occur on validation or concurrency failure.
- Phase 1 proves one melee settlement end to end and a hitscan semantic
  request/route fixture; it does not implement ammo, projectile, or client
  damage truth.

### Task 1: Define ActionAttempt and AuthorityResult models

**Files:**
- Modify: `backend/app/models/embodied_interaction.py`
- Create: `backend/app/models/action_attempt.py`
- Create: `backend/app/models/authority_result.py`
- Test: `backend/tests/test_character_action_attempt_models.py`

**Interfaces:**
- `ActionAttempt.from_payload(dict) -> ActionAttempt`
- `ActionAttempt.canonical_payload() -> dict`
- `AuthorityResult.to_payload() -> dict`

- [ ] Add the canonical actor/action identity, contact marker plus optional
  marker time, bounded `target_refs[]`, physics tick, bounded
  `physics_evidence_refs[]`, evidence digest, expected revisions, idempotency,
  command version, causation, correlation, route, optional server-issued
  `owner_contract_ref`, source, privacy, and `submitted_at` fields.
- [ ] Add optional `action_family` (`melee` or `hitscan`) and `weapon_ref`;
  reject client-provided damage, hit confirmation, ammo mutation, and ballistic
  result fields.
- [ ] Validate stable action instance IDs and typed target references.
- [ ] Define `canonical_payload()` to exclude `submitted_at`; identical stable
  business fields with a new submission time return the original result, while
  any other same-key change returns `payload_mismatch`.
- [ ] Enforce `ActionAttempt <= 32 KiB`, `target_refs <= 8`,
  `physics_evidence_refs <= 8`, and evidence array/record bounds from the ESM
  child spec; reject overages with `payload_limit_exceeded`.
- [ ] Encode outcomes `committed`, `rejected`, and `unknown` plus recovery metadata.
- [ ] Run model tests and verify malformed payloads fail closed.

### Task 2: Implement ingress validation and idempotency

**Files:**
- Modify: `backend/app/services/embodied_execution_ingress.py`
- Create: `backend/app/services/action_attempt_idempotency.py`
- Test: `backend/tests/test_character_action_attempt_ingress.py`

**Interfaces:**
- `EmbodiedExecutionIngress.accept_attempt(ActionAttempt) -> AuthorityResult`
- `ActionAttemptIdempotency.lookup_or_reject(ActionAttempt) -> AuthorityResult | None`

- [ ] Authenticate actor/session identity and authority route.
- [ ] Check duplicate identity before loading mutable aggregates.
- [ ] Reject same idempotency key with changed canonical payload.
- [ ] Pin expected actor/world revisions and return typed stale/precondition errors.
- [ ] Run focused ingress tests including duplicate, stale, unauthorized, and unknown outcomes.

### Task 3: Route ESM, Gameplay, and composite settlement

**Files:**
- Modify: `backend/app/gameplay/action_window_runtime.py`
- Modify: `backend/app/services/embodied_authority_settlement_service.py`
- Create: `backend/app/services/action_attempt_route_resolver.py`
- Test: `backend/tests/test_character_action_attempt_route_resolution.py`

**Interfaces:**
- `ActionAttemptRouteResolver.resolve(ActionAttempt) -> str`
- `EmbodiedAuthoritySettlementService.settle(ActionAttempt) -> AuthorityResult`

- [ ] Route environment effects to ESM and actor effects to Gameplay.
- [ ] Route the standard melee fixture through the normal composite/Gameplay
  validation path and resolve a hitscan fixture by semantic weapon reference
  plus revalidated aim evidence.
- [ ] Use one atomic event batch for composite actions when the existing store supports both streams.
- [ ] Otherwise require an explicit reservation/compensation lifecycle and label the result non-atomic.
- [ ] Validate affordance, spatial range, occupancy, capability, status, resource, and equipment preconditions before append.
- [ ] Run route tests with zero-write failure assertions.

### Task 4: Revalidate physical evidence and commit projections

**Files:**
- Modify: `backend/app/services/embodied_authority_settlement_service.py`
- Create: `backend/app/services/physics_evidence_revalidator.py`
- Create: `backend/app/services/character_authority_projection_service.py`
- Test: `backend/tests/test_character_action_attempt_settlement_static.py`

**Interfaces:**
- `PhysicsEvidenceRevalidator.validate(ActionAttempt) -> dict`
- `CharacterAuthorityProjectionService.project_authority_result(AuthorityResult) -> dict`

- [ ] Revalidate evidence digest, tick, actor location envelope, target revision, and support/contact requirements.
- [ ] Ensure markers and collider flags never settle damage, pickup, occupancy, or status by themselves.
- [ ] Project only committed results into CharacterRuntimeState and the existing Gameplay mirror.
- [ ] Ensure rejected or unknown results release claims and freeze unsafe root motion through the actor adapter.
- [ ] Run success, rejection, stale, and late-result tests.

### Task 5: Integrate Godot marker emission and recovery

**Files:**
- Modify: `scripts/interaction/EmbodiedActionController.gd`
- Create: `scripts/character/ActionAttemptEmitter.gd`
- Modify: `scripts/character/CharacterRuntimeState.gd`
- Test: `backend/tests/test_character_action_attempt_godot_boundary_static.py`

**Interfaces:**
- `ActionAttemptEmitter.emit_marker_attempt(Dictionary) -> Dictionary`
- `CharacterRuntimeState.apply_authority_result(Dictionary) -> void`

- [ ] Record marker observations first, let Motor emit same-tick
  `PhysicsContactEvidence`, then emit one attempt at the tick settlement
  boundary with stable attempt/idempotency identity. Actions without a
  physical-evidence requirement may emit immediately after marker observation.
- [ ] Carry evidence references rather than local outcome claims.
- [ ] Handle committed, rejected, unknown, timeout, cancellation, and target-invalid recovery deterministically.
- [ ] Prevent late results from resurrecting cancelled or expired action instances.
- [ ] Run the focused boundary test and existing embodied-action tests.

### Task 6: Authority integration verification

**Files:**
- Create: `scripts/verification/verify_character_esm_action_settlement.py`
- Test: `backend/tests/test_character_esm_action_settlement_profile.py`

- [ ] Start the real backend and send one ESM interaction, one Gameplay resource rejection, and one composite action.
- [ ] Verify duplicate retry returns the original transaction identity.
- [ ] Verify concurrent same-revision attempts produce at most one commit.
- [ ] Verify local contact without a settlement produces no world change.
- [ ] Verify melee evidence can commit only after authority validation and a
  hitscan request cannot commit from a client-supplied hit or damage field.
- [ ] Run `python -m pytest backend/tests/test_character_esm_action_settlement_profile.py -v` and the relevant Harness profile.

## Completion Criteria

- [ ] ActionAttempt and AuthorityResult are stable, typed, idempotent, and revision-pinned.
- [ ] ESM/Gameplay ownership is enforced with zero-write rejection behavior.
- [ ] Local markers and physical evidence never become world truth without authority settlement.
- [ ] Committed results return through existing projection paths and drive explicit actor recovery.
