# Embodied Interaction Product Foundation Master Design

Status: `partially-implemented; coverage-expansion-planned`

Date: `2026-07-29`

Revision: `2026-08-01` (implementation status reconciliation)

## Purpose

Define the formal product foundation that closes the gap between a character
agent's semantic action and a verified embodied result. The result is not an
unbounded motion-generation system. It is a reusable, authority-governed path
for known scene entities and later bounded unknown-entity advisory input.

The first executable reference is: an agent selects `kick(chair_01)`; the
character reaches a registered stance, locally observes a real contact or a
typed failure, backend authority settles exactly once, and Godot/Observatory
show replayable evidence of the same causation chain.

## Source And Status Audit

### Completed and verified existing foundations

| Existing capability | Evidence boundary | What it proves | What it does not prove |
| --- | --- | --- | --- |
| Structured interaction routing | `InteractionOrchestrationService` and `interaction-orchestration-service` profile | semantic, physical, mixed, denied, and degraded policy shapes merge structured results | a local character executed an action against a scene object |
| ESM physical-channel seam | `PhysicalInteractionChannel`, `PhysicalInteractionProbe`, and `esm-physical-channel-world-actuation` profile | physical result families carry body/object/environment refs and constraint gating | real RigidBody3D contact, impulse, or final pose determined the result |
| Local semantic realization ingress | `character_agent_execution` -> `CharacterReplica` and `character-agent-execution` proof | agent execution semantics reach a local actor host | a generic action state machine, navigation, IK, or recovery loop exists |
| Embodied/skeletal sampling | `EmbodiedSkeletalStateProvider` and `embodied-skeletal-debug-replay` profile | high/mid-level embodied data enters perception; full bones are debug-only artifacts | the sample drives an interaction controller |
| Authority event, debug, and Observatory surfaces | `AuthorityEventBus`, frontend projection, Observatory models/UI, and mainline proof | existing world outcomes and actor/Siming traces can be observed and replay-oriented | one interaction session can be reconstructed end-to-end |
| Advisory VLA slow path | `vla_*` runtime modules and `vla-provider-backend` profile | scoped VLA advisory results reach percept bundles without authority/motion writes | live VLA is a required or validated action-control capability |

These statements are evidence-bound to the named current profiles and source
contracts. A future implementation must run fresh evidence before restating
them as a new milestone.

### Implemented And Verified Foundations

- `SceneAffordanceRegistry` has reviewed stable IDs, scene-instance binding
  scope, anchors/colliders, revision pinning, occupancy freshness, and a real
  `chair_01` binding. `embodied-affordance-registry` proves its backend and
  Godot runtime boundary.
- `EmbodiedActionController` implements the bounded local lifecycle:
  acquire target, reserve stance, navigation, alignment, prepare, contact
  observation, recovery, cancellation, and typed terminal outcomes.
  `embodied-action-controller` proves its Godot runtime paths.
- Controller attestation, one selected realization route, observed-outcome
  validation, authority settlement, and replay ledger are implemented for the
  narrow object-interaction path. The corresponding bridge, settlement, and
  replay profiles prove that local observations do not write world truth.
- `InteractionSession`, narrow handoff, and grab-carry-place are implemented
  over the Gameplay atomic event spine. Their profiles prove session lifecycle,
  privacy filtering, idempotency, authority-only Godot presentation, and the
  relevant bounded success/failure cases.

### Implemented But Limited Slices

- `kick-chair`, the default-main-scene `obj_letter` and `obj_plaque`
  `inspect/read` fixtures, and the `obj_lamp_switch` semantic `press` fixture
  and `obj_archive_door` semantic `open_close` fixture, plus the
  `obj_worktable` semantic `use` / `finish_use` fixture, are verified object
  references. The switch proves an ESM-owned `switch: idle -> activated`
  result, the door proves `door: closed -> open -> closed`, and the worktable
  proves `work_surface: ready -> engaged -> ready`. `obj_observation_bench`
  proves authority-scoped `available -> occupied -> available`, owner-only
  release, and posture body results. None proves controller-owned action
  outcomes, seated animation, shared occupancy allocation, or table animation.
  This is not a claim that all default-main-scene objects have reviewed
  bindings or interaction assets.
- Carry/place and handoff prove constrained authority slices, not the complete
  inventory, ownership, economy, or equipment runtime.
- The controller currently proves its bounded state machine, observations, and
  descriptor-driven phase-to-atom bindings. Broad atomic-action coverage and
  the full local IK/motion-warp integration remain follow-on work.
- VLA is available only as an advisory input. Candidate-to-registry binding is
  still disabled; VLA neither controls motion nor activates an affordance.
- Godot mirror and Observatory outputs are evidence/presentation for the
  implemented slices, not a comprehensive scene-wide interaction UI.

### Still Not Started

- Comprehensive default-main-scene coverage by object family. The Wave 1
  route for pickup props, seated animation, shared seat/table occupancy, and door occlusion is planned in
  `2026-08-01-atomic-action-library-and-default-scene-coverage-design.md`.
- A broad, reviewed atomic-action library wired into controller phases for all
  semantic actions, equipment variants, and expressive overlays.
- General unknown-object interaction or automatic affordance activation from
  VLA output.
- High-precision synchronized social clips beyond the implemented session and
  bounded handoff slices.

### Analysis treated as historical or advisory

- `docs/kimi分析/2026-07-23-具身角色交互与VLA闭环差距分析.md` remains useful for
  problem framing and its first-chair reference, but explicitly says it is not
  the active plan and must not replace runtime proof.
- `docs/kimi分析/2026-07-23-智能体具身交互全景评估与实施路线.md` remains a route
  reference. Its LLM-readiness conclusion is explicitly marked partially
  outdated; its productization route is not implementation truth.
- Neither analysis upgrades or replaces the current code and harness evidence;
  the implemented status above is grounded only in the named profiles.

## Architecture

```text
Character mind / L3-L4 semantic plan
  -> structured EmbodiedActionRequest (intent only)
  -> backend preflight: authority, policy, pinned revisions, target ref
  -> SceneAffordanceRegistry query and realization contract
  -> controller-scoped execution grant over the typed Godot bridge
  -> Godot EmbodiedActionController
       navigate -> align -> prepare -> contact window -> observe -> recover
  -> LocalPhysicalObservation / LocalExecutionOutcome
  -> backend authority settlement using the observation as evidence
  -> AuthorityEvent / world result / private perception and memory writeback
  -> Godot mirror + Observatory + replay ledger
```

The local controller never decides a semantic world result. The backend never
pretends a contact occurred merely because an animation request was sent.

## Core Contracts

### `EmbodiedActionRequest`

This is a structured, backend-authorized realization request, not raw input or
motion data:

```text
request_id, interaction_attempt_id, session_id?
actor_id, target_ref, action_semantic, affordance_id
authority_preflight_ref, policy_revision, scene_revision
required_anchor_roles, execution_profile_ref, expiration_tick
causation_id, correlation_id
```

It may contain bounded desired stance/anchor IDs and approved force/effect
limits. It must not contain bone transforms, continuous velocities, arbitrary
node paths, free-form GDScript, or a final world-state claim.

### `LocalExecutionOutcome`

Godot returns a single terminal, structured observation:

```text
interaction_attempt_id, phase, terminal_status
observed_at, actor_pose_ref, target_binding_ref
contact_observation?, object_observation?, body_observation?, environment_observation?
failure_code?, trace_refs[], causation_id, correlation_id
controller_grant_id, connection_epoch, terminal_sequence, outcome_nonce, payload_digest
```

Terminal status is one of `contact_observed`, `completed_without_contact`,
`aborted`, `interrupted`, `failed_precondition`, `failed_navigation`,
`failed_alignment`, `missed_contact`, or `observation_invalid`. Local success
means only that an observation was produced; settlement remains pending.

`controller_grant_id`, `connection_epoch`, `terminal_sequence`, and the
one-time `outcome_nonce` are mandatory attestation inputs, not application
decorations. The backend validates them through the transport contract in this
tree before it reads the physical observation. A plain attempt ID is never a
credential and `character_actor_status` is never an outcome channel.

### `EmbodiedSettlementResult`

Backend returns one of `committed`, `rejected`, `not_committed`, or
`observation_rejected`, with the same attempt/session/causation/correlation
identifiers, authority result refs, resulting world-state refs, retry policy,
and safe presentation directive. A committed result is the only source for
authoritative scene mutation and mind/Siming writeback.

## Boundary With Existing Systems

| System | May do | Must not do |
| --- | --- | --- |
| Character mind | select action semantics, evaluate social intent, retry/abort after result | own scene physics, declare contact success, settle world truth |
| ESM/authority | preflight, authorize, validate observed evidence, settle and emit events | run Godot navigation/IK or use animation completion as contact proof |
| Godot | execute local pose/navigation/physics and report bounded observations | mutate backend world truth or authorize itself |
| Siming | consume public settled evidence; emit high-level catalyst | start/steer controller phases or write a session state |
| VLA | suggest identity/affordance candidates and uncertainty in a scoped advisory path | directly bind a local action, control motion, apply force, or settle |
| Godot mirror/Observatory | show filtered state, pending attempt, settlement, and evidence refs | become a replay authority or retain unfiltered private mind state |

## First Closure And Deferred Scope

### First closure: `kick-chair`

- one scene-local `chair_01` registration with a kick anchor, stance anchor,
  collider binding, physical-state observation rule, and authority policy;
- one agent actor, one `kick` realization profile, approach/alignment/contact/
  verify/recover lifecycle, and safe abort path;
- real contact/miss/no-path/fixed-chair observations;
- one authority settlement per attempt, idempotency/revision protection, and
  structured world result only after observed evidence is validated;
- Godot visible change, authority trace, filtered Observatory timeline, and a
  replay artifact proving the same IDs end to end.

### Subsequent closures

1. `grab-carry-place`: hand anchor, attachment, dropped/occupied targets, and
   carrying constraints.
2. `handoff`: two actors plus object ownership/possession settlement.
3. `handshake`: first social `InteractionSession` acceptance/refusal/cancel
   path before high-value synchronized clips.
4. advisory VLA binding for unknown/unannotated assets, always optional and
   confidence-governed.

### Explicitly excluded

- TTS, voice streaming, visemes, general facial animation, and dialogue UX.
- Full-body remote control, raw physics streaming, or LLM/VLA motion tokens.
- A general interaction content library, arbitrary scene import, or all
  multi-actor social content.
- Replacing existing gameplay-event architecture or making Godot an event store.

## Dependencies

- Existing: mainline execution semantics, ESM interaction orchestration, L1
  perception, AuthorityEvent routing, VLA advisory, and Godot bridge.
- Contract alignment: character-gameplay-foundation event settlement and Godot
  mirror designs. `kick-chair` uses the explicitly temporary ESM compatibility
  settlement adapter defined in the session spec. Social, relationship, body,
  inventory, and cross-domain actions are gated on the gameplay atomic-event
  batch writer; the embodied path must not fork a second authority model.
- Runtime assets: a self-contained test scene with NavigationRegion3D, a
  character binding, a collider-enabled chair, and bounded action assets.

## Acceptance Criteria

1. A known scene object can be queried by stable ID and returns its registered
   affordances, anchors, binding revision, and authority policy ref; stale or
   unknown bindings fail without controller start.
2. A locally authorized `kick` attempt reaches a registered stance and emits
   a terminal `contact_observed`, `missed_contact`, or typed pre-contact
   failure. No terminal path silently hangs.
3. A chair result is committed only after backend validates the matching local
   observation, pinned policy/scene revisions, actor/target binding, and
   idempotency key. A repeated submission returns the original settlement.
4. No-path, target moved, blocked stance, fixed chair, missed contact,
   cancellation, stale scene binding, and duplicate outcome each produce a
   typed result with zero incorrect world mutation.
5. Godot-visible state changes only from committed authority output. Rejected
   or observation-invalid attempts leave the authoritative object state intact.
6. Mind and Siming consume filtered post-settlement evidence only; neither can
   control local phases or see another actor's private session/memory data.
7. VLA advisory can be absent, stale, uncertain, or conflicting without
   preventing known-registry action execution or overriding registry truth.
8. The replay ledger joins request, local phases, terminal observation,
   settlement, authority event, and final presentation by common IDs and
   server-assigned ordering keys; replay detects missing, late, duplicate, and
   contradictory records.
9. A controller outcome is accepted only once when its authenticated bridge
   principal, grant, nonce, connection epoch, sequence, request fingerprint,
   and revocation state all match. Reconnect, cancellation, and expiry revoke
   the old grant and cannot turn delayed traffic into a settlement.
10. Focused backend tests, Godot runtime probe, registered focused profile, predecessor
   profiles, and repository documentation profile pass with fresh evidence.

## Harness Mapping

| Registered profile | Required proof |
| --- | --- |
| `embodied-affordance-registry` | registry schema, binding lifecycle, query isolation, and stale-binding failures |
| `embodied-action-controller` | Godot controller phases, navigation/alignment/contact/abort/recovery runtime proof |
| `embodied-authority-settlement` | evidence validation, idempotency, revision conflicts, commit/reject behavior |
| `embodied-interaction-session` | participant consent, reservation, cancellation, synchronization, and privacy boundaries |
| `embodied-interaction-replay` | complete correlated ledger, deterministic replay validation, Observatory filtering |
| `embodied-interaction-foundation-all` | dependency-ordered aggregate for this tree |

These profiles are registered and have evidence for the bounded slices described
above. They remain acceptance contracts for any expanded object/action coverage;
a green existing report must not be used to infer that the still-not-started
scope is complete.
