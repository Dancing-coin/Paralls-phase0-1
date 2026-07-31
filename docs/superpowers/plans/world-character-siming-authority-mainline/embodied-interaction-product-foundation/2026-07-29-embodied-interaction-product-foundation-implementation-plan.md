# Embodied Interaction Product Foundation Implementation Plan

Status: `drafted-for-spec-review`

Date: `2026-07-29`

Revision: `2026-07-31` (review remediation)

## Goal

Implement a reusable, backend-authoritative embodied interaction foundation,
starting with a verifiable `kick-chair` closure and then extending the same
contracts to object transfer and multi-actor sessions. This plan does not
authorize implementation until the matching spec tree is approved.

## Preconditions

- Approved spec tree: `docs/superpowers/specs/world-character-siming-authority-mainline/embodied-interaction-product-foundation/`.
- Preserve current `character_agent_execution`, ESM orchestration, physical
  channel, VLA advisory, skeletal replay, and Phase 0 proof behavior.
- Do not add dependencies unless explicitly approved.
- Before code edits, add failing focused tests for each behavior and maintain a
  Goal for the multi-phase execution.

## Dependency Graph

```text
0 contract inventory, authenticated bridge, writer selection, and harness skeleton
  -> 1 registry
  -> 2 embodied transport, grants, and legacy-route gate
  -> 3 controller + local observation
  -> 4 authority observation settlement
  -> 5 kick-chair vertical slice + evidence ledger
  -> 6 gameplay event-batch prerequisite, InteractionSession + handshake
  -> 7 grab/carry/handoff and optional advisory binding
  -> 8 aggregate regression and runbook
```

Phases 1-5 are the first product closure. Phases 6-7 are planned follow-on
closures and must not be presented as complete merely because their contracts
were created.

## Phase 0: Freeze Contracts And Test Fixtures

**Primary files:** add focused Pydantic/GDScript contracts under
`backend/app/` and `scripts/interaction/`; tests under `backend/tests/` and
`scripts/verification/tests/`; add planned verifier entrypoints under
`scripts/verification/` and profile manifests under `.harness/profiles/`.

1. Define request, registry record, controller binding/grant, ordered phase,
   local outcome, settlement writer, session, projection, and evidence-ledger
   schemas with IDs, revisions, causation, correlation, epochs, nonce,
   sequence, and field visibility.
2. Make the `esm_compatibility_adapter` the sole first-closure writer and add
   an explicit capability check that rejects session/cross-domain settlement
   until the gameplay atomic event-batch writer exists. Do not dual-write.
3. Add negative contract tests for raw input, bone/rigid-body control fields,
   unauthenticated controller binding, spoofed attempt ID, stale epoch, nonce
   reuse, sequence gaps, revoked grants, unknown fields, cross-scene binding,
   duplicate attempt IDs, and per-field projection leakage.
4. Add empty planned profile skeletons only once their verifier scripts have a
   meaningful failure mode; document them in `docs/harness.md`.

**Exit criteria:** schemas reject forbidden ownership/control fields; an
embodied request has one selected writer and realization route; every later
phase can refer to one canonical attempt/outcome model; existing interaction
profile remains green.

## Phase 1: Implement `SceneAffordanceRegistry`

**Primary files:** add registry backend service/model ownership under
`backend/app/services/` or `backend/app/world_runtime/` after locating the
closest identity owner; add Godot registry/binding scripts under
`scripts/interaction/`; add a dedicated probe scene under `scenes/phase0/` or
its successor test-scene directory.

1. Implement reviewed record loading as an adapter over the existing
   `SceneSpaceModelExtractor`, `RuntimeOccupancySampler`, and PQF grounding
   catalog. Retain their entity/collider/anchor IDs exactly; do not create a
   parallel identity map or use VLA output as a record source.
2. Add scene-instance scoping, binding health, revision pinning,
   affordance/anchor query, occupancy freshness, and filtered
   public/controller views.
3. Create a real `chair_01` fixture with collider, stance/contact anchors,
   physical profile, upright/tipped observation rule, and fixed-chair variant.
4. Prove unload/reload, node/collider loss, binding revision mismatch, stale
   occupancy, unknown affordance, catalog identity mismatch, and VLA advisory
   conflict behavior.

**Exit criteria:** a controller request resolves the same runtime node/collider
that backend preflight pinned; stale/unknown bindings do not start realization.

## Phase 2: Implement Embodied Transport, Attestation, And Route Gate

**Primary files:** extend `backend/app/ws_protocol.py`, `backend/app/main.py`,
add `backend/app/services/embodied_controller_auth_service.py` and
`backend/app/services/embodied_execution_ingress.py`, extend
`scripts/autoload/BackendBridge.gd`, add a local trusted-launch run helper, and
add focused backend/Godot bridge tests. The current generic socket has no
controller authentication, so do not describe or enable this phase as an
extension of an existing authenticated bridge. Do not overload
`character_actor_status`.

1. Implement `EmbodiedControllerAuthService` as the sole owner of principal,
   credential, controller binding, epoch, and revocation state. For the first
   closure, implement only the loopback-only, one-time `trusted_local_launch`
   credential injected by the local launcher. The production
   `authenticated_session` verifier is a required configured-adapter gate, not
   an assumed existing service; its absence keeps the production feature gate
   off.
2. Bind the derived principal to a controller instance and issue a monotonically
   increasing connection epoch. Require a server-stored,
   controller-scoped execution grant with expiry, request digest, revision
   pins, nonce, and revocation state.
3. Implement `EmbodiedExecutionIngress` and typed request, phase, outcome,
   settlement, cancellation, and resync
   messages with explicit backend handler and Godot dispatch ownership. Reject
   unknown types/fields/version before execution.
4. Implement source sequence/digest idempotency, reconnect revocation, and
   authority-driven resync. A reconnect must never resume local motion without
   a new authority grant.
5. Add the backend-selected `legacy_character_replica` / `embodied_controller_v1`
   feature gate. Prove a single attempt cannot start both paths and that a gate
   rollback drains active embodied attempts through cancellation/recovery.

**Exit criteria:** a focused bridge probe proves a known attempt ID cannot be
spoofed, old-epoch/delayed messages cannot settle, and every permitted message
has one handler; a non-loopback or production profile cannot enable the local
credential; legacy behavior remains unchanged when the gate is off.

## Phase 3: Implement `EmbodiedActionController` And Local Observation

**Primary files:** add `scripts/interaction/EmbodiedActionController.gd`,
local observation emitter/adapter scripts, action assets/configuration, and
Godot probe scenes; integrate through the route gate with `CharacterReplica.gd`
and `CharacterMotor.gd` without moving semantic intent ownership there.

1. Implement state transitions, timeout/cancellation/recovery, stance
   reservation, path/align checks, and ordered local trace events.
2. Use engine-local navigation and collision APIs; add the generic kick atom
   and only the minimum IK/motion-warp integration needed for a contact window.
3. Emit an attested bounded terminal local observation for hit/miss/no-path/
   fixed target/target move/interruption, retaining full-bone debug evidence
   separately.

**Exit criteria:** a headless/runtime Godot probe proves all first-closure
terminal paths, restores local ownership after failure, contains no raw physics
or bone stream transport, and cannot bypass the selected route or execution
grant.

## Phase 4: Settle Observed Physical Outcomes In Backend Authority

**Primary files:** extend `backend/app/services/interaction_orchestration_service.py`,
`physical_interaction_channel.py`, existing ESM/authority-event adapters, and
their tests. Do not create a parallel world-result protocol.

1. Add preflight, controller-grant validation/atomic consume, observed-outcome
   validation, idempotency, revision/policy checking, and typed settle/abort/
   retry results.
2. Implement `esm_compatibility_adapter` as one atomic authority receipt and
   existing ESM-result/AuthorityEvent operation for the single-object closure;
   record `settlement_writer_kind` and fail closed when a requested effect needs
   the absent gameplay event-batch writer.
3. Replace synthetic "effect applied" assumptions only for the new embodied
   path: existing legacy/probe behavior remains compatible until deliberately
   migrated.
4. Emit correlated authority events/world results and allowlist-filtered
   character/Siming writeback inputs only after commit/reject.

**Exit criteria:** fabricated, stale, duplicate, attestation-invalid, or
mismatched local observations produce zero mutation; a validated chair
observation settles exactly once through its recorded writer.

## Phase 5: Prove `kick-chair` And Evidence Ledger

**Primary files:** add interaction evidence service/projection and verifier;
extend `BackendBridge.gd`, `LocalPresentationBus.gd`, relevant Observatory
state/UI consumers, `scripts/verification/`, `.harness/profiles/`,
`docs/harness.md`, and the runbook.

1. Build an attempt ledger from request through final presentation with
   server-assigned ledger sequence, emitter epoch/source sequence, typed
   late-message audit records, per-field filtered Observatory rows, and
   debug-only skeletal references.
2. Add success and failure Godot probes producing screenshot/log/JSON artifacts.
3. Add `embodied-affordance-registry`, `embodied-bridge-attestation`,
   `embodied-action-controller`,
   `embodied-authority-settlement`, and `embodied-interaction-replay` profiles,
   then compose `embodied-interaction-foundation-all`.

**Exit criteria:** success and failure artifacts prove a real scene-visible
result, one authority settlement, and a replay-valid causal chain. Existing
`phase0`, `interaction-orchestration-service`, `esm-physical-channel-world-actuation`,
`embodied-skeletal-debug-replay`, and `mainline-unified-runtime` still pass.

## Phase 6: Implement `InteractionSession` Before Synchronized Social Clips

**Primary files:** add authority-owned session service/models, session
projection, local slot consumer, and focused backend/Godot probes.

1. Before code edits, complete and verify the gameplay-foundation event-store
   and atomic-event-batch prerequisite. This phase is blocked rather than
   emulated through `esm_compatibility_adapter`.
2. Implement proposed/accept/reject/authorized/realizing/cancelled/interrupted/
   committed lifecycle with participant/slot/reservation ownership.
3. Prove handshake acceptance, refusal, target departure, third-party
   interruption, and privacy filtering.
4. Integrate session terminal observations with the same settlement/evidence
   ledger, not a separate social trace.

**Exit criteria:** two characters never complete a shared action without one
authoritative session and both valid terminal participation observations.

## Phase 7: Expand Carefully To Objects And Advisory VLA

1. Implement `grab-carry-place` and handoff using attachment, occupancy, drop,
   and authority possession boundaries; coordinate with the gameplay-foundation
   inventory/ownership plan rather than duplicating it.
2. Add reviewed VLA candidate-to-registry binding only after known-registry
   paths remain fully functional with VLA disabled, stale, or conflicting.
3. Defer hugs and other high-precision synchronized clips until handshake
   session evidence and action assets exist.

**Exit criteria:** attachment/local presentation cannot establish ownership;
handoff settles through authority and VLA never directly starts motion.

## Phase 8: Aggregate Evidence And Documentation Closure

1. Add each new profile to registry/order, `docs/harness.md`, `docs/INDEX.md`,
   runtime module docs, and the appropriate runbook.
2. Run focused tests and profiles after each phase; run the new aggregate and
   `python scripts/verification/harness.py --profile all` only after all
   predecessor profiles pass.
3. Archive fresh reports/screenshots/traces under `.harness/verification/` and
   update the source/verification status matrix without promoting planned work
   to verified status.

## Verification Commands

During implementation, add and run the planned focused profiles in dependency
order. The existing regression floor is:

```powershell
python scripts/verification/harness.py --profile interaction-orchestration-service
python scripts/verification/harness.py --profile esm-physical-channel-world-actuation
python scripts/verification/harness.py --profile embodied-skeletal-debug-replay
python scripts/verification/harness.py --profile vla-provider-backend
python scripts/verification/harness.py --profile mainline-unified-runtime
python scripts/verification/harness.py --profile all
```

Documentation-only changes to this plan/spec tree must at least run:

```powershell
python scripts/verification/harness.py --profile docs
```

## Risks And Controls

| Risk | Control |
| --- | --- |
| Godot and backend diverge | pin scene/policy revisions; settle only observed evidence; resync/replay on mismatch |
| Local animation appears successful without contact | require registered contact and final-state observation rules |
| Controller becomes a second cognition layer | accept only authorized semantics; expose retry as outcome input to mind |
| VLA/LLM bypasses safety | schema rejects controls/world-write fields; retain advisory-only bridge tests |
| Social clips outrun session semantics | implement/verify session before handshake and high-value synchronized clips |
| Scope leaks into dialogue/TTS | no TTS/streaming files or acceptance criteria in this plan |

## Staffing Guidance After Approval

- One `executor` owns shared contracts and backend settlement integration.
- One `executor` owns Godot registry/controller/probe assets after contracts
  freeze; it must not edit backend settlement models independently.
- One `test-engineer` owns harness profile/verifier design and evidence review.
- One `verifier` performs final cross-boundary replay/runtime validation.

Run contract/architecture work sequentially before parallelizing isolated
backend and Godot implementation lanes; the leader owns integration and the
final aggregate evidence decision.
