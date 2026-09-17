# Unified Character Action Foundation and INF Tag Contract Design

Date: `2026-09-14`

Status: `final design target v2; runtime migration incomplete`

## Purpose

This document consolidates the repository's shared character-body target with
the external-asset action foundation and the INF/CharacterAgent metadata
boundary. It supersedes fragmented interpretations of `TagContainer`,
`ActionData`, parallel state machines, and local damage resolution.

The first implementation milestone is deliberately asset-driven: external
rigged models and animations are imported, qualified, retargeted, and played
through one shared actor runtime. No project-authored animation content is
required by this design.

The first milestone also includes a bounded weapon slice. It must prove the
equipment/action/claims/authority seams with one qualified held-item binding,
one standard melee action, and a semantic hitscan request/authority-validation
fixture.
This does not make Phase 1 a complete weapon game: ammunition, magazines,
chambers, ballistic projectiles, dual wielding, parry/clash, and arbitrary
prop weaponization remain deferred.

This is the final cross-domain design target for the current migration. It
does not claim that the repository already implements the target. Physics,
ESM/Gameplay settlement, and connected runtime rules are split into child
specifications so their ownership and acceptance evidence cannot drift from
this document:

- `2026-09-14-character-physics-motion-and-contact-subspec.md`
- `2026-09-14-character-esm-action-attempt-settlement-subspec.md`
- `2026-09-14-character-connected-action-and-physical-replication-subspec.md`
- `2026-09-14-character-animation-asset-qualification-and-concurrent-realization-subspec.md`

The implementation plan is an execution order only. If a child specification
and an older historical document disagree, this final design and its child
specifications win; the historical document is not an alternative runtime
contract.

## Source-Of-Truth Matrix

| Surface | Sole responsibility | Must not redefine |
| --- | --- | --- |
| This main spec | actor model, multi-action semantics, Agent/INF boundary, global ownership | physical formulas, settlement schema, transport fields |
| Physics child spec | motion composition, Motor execution, collision evidence, physical claims | ESM consequences or network owner |
| ESM child spec | ActionAttempt, route, revision, idempotency, atomic settlement, recovery | local pose or Motor movement |
| Connected child spec | lease/control transport, Gameplay mirror relation, future body stream, prediction/reconnect | domain settlement rules or raw bone replication |
| `character-action-asset-interface.md` | asset-facing index and authoring handoff | a competing runtime contract |
| implementation plan | ordered implementation tasks and evidence | architecture decisions |
| current-state/drift audit | repository facts, gaps, and migration status | future behavior claims |

## Non-Negotiable Ownership

```text
Human / CharacterAgent / Program
-> source adapter
-> IntentProposal
 -> ActorActionArbiter
-> CharacterIntentFrame
-> CharacterMotor / ActionExecutor
-> CharacterPresentationInput
-> imported RoleSkin / AnimationTree
```

- Godot owns local embodiment, input capture, collision execution, and visible/audio presentation.
- `CharacterMotor` is the only owner of velocity, gravity, collision, facing, world displacement, and `move_and_slide()`.
- `CharacterAgent` and INF may produce semantic intent, constraints, evidence, catalysts, and metadata; they may consume committed authority projections, but they never produce settlement results or write Godot transforms or animation state directly.
- Phase 1 consequence ownership is explicit: ESM, Gameplay, or a registered Composite coordinator owns world facts such as hit, damage, death, inventory, equipment, and resource settlement. INF may participate only through an owner-bound, registered contract; `inf` is not a generic settlement route.
- Animation and root motion are presentation inputs. Root-motion deltas may affect movement only after Motor validation.

## Unified Tag Ontology

Tags are namespaced semantic values, not an untyped global bag.

| Namespace | Owner | Meaning | Can directly mutate body? |
| --- | --- | --- | --- |
| `goal:*` | CharacterAgent/INF input | Long-horizon role objective | No |
| `intent:*` | Adapter/Agent | Proposed immediate purpose | No |
| `evidence:*` | INF/CharacterAgent context | Evidence supporting an interpretation or proposal | No |
| `capability:*` | Gameplay/INF projection | Available ability/equipment proof | No |
| `affordance:*` | ESM/Gameplay projection | Legal world interaction opportunity | No |
| `constraint:*` | Authority/Agent context | Restrictions and policy gates | No |
| `state:*` | Actor runtime projection | Current locomotion/action state | Only through coordinator |
| `status:*` | Gameplay authority projection | Injury, stun, exhaustion, death, etc. | Only through authority result |
| `action:*` | Action asset/runtime | Requested or active action identity | No |
| `phase:*` | Action runtime | Windup/contact/recovery phase | No |
| `occupy:*` | Layer coordinator | Resource ownership token | No |
| `event:*` | Runtime/authority event | Contact/request/result event | No |
| `authority:*` | committed ESM/Gameplay/Composite result projection | Accepted/rejected/settled result | Updates projection only |
| `presentation:*` | Presentation adapter | Locomotion/pose/expression cue | No |
| `expression:*` | Presentation/character L4 | Facial or micro-expression cue | No |

INF metadata such as confidence, evidence, provenance, causation,
correlation, revision, privacy scope, authority scope, and `reason_codes`
travels alongside these tags. It is not itself a local body state. A proposal
may include `authority_scope` as context, but only the committed result
projection may emit `authority:*` tags.

## Runtime Contracts

## Canonical Resource And Physics Claims

The first milestone freezes one resource vocabulary for all action packages:

```text
full_body_pose
├─ pelvis
├─ upper_body
│  ├─ left_arm
│  │  └─ left_hand
│  └─ right_arm
│     └─ right_hand
├─ left_leg
└─ right_leg

head
root_translation
facing
world_motion
weapon_slot:<id>
voice_channel
physics_body
support_contact
interaction_reach
weapon_hit_volume:<id>
target_occupancy:<id>
ragdoll_body
```

### Phase 1 Weapon Slice

Weapons are an equipment and capability projection plus ordinary action
profiles; they are not a second body state machine. The minimum contract is:

```text
EquipmentBinding {
  slot_id
  anchor_ref
  item_ref
  attachment_mode       # visual_kinematic | reviewed_physics_interaction
}

WeaponActionProfile {
  semantic_action_id
  action_family          # melee | hitscan
  weapon_ref
  required_slots[]
  resource_claims[]
  physics_claims[]
  timing_markers[]
  cancel_windows[]
  authority_route_ref      # esm | gameplay | composite (Phase 1)
}
```

Phase 1 uses `weapon_slot:<id>` and `weapon_hit_volume:<id>` as canonical
claims. A melee marker may create an `ActionAttempt`; a hitscan request may
carry a weapon reference and aiming evidence. Neither local collision, marker,
ray query, recoil effect, nor client-provided damage is a world consequence.
Both action families enter the same Arbiter lifecycle, and ESM/Gameplay still
returns the typed authority result.

Visual bone resources and physical resources are intentionally separate. Two
actions may use different arms but still conflict on a shared
`weapon_hit_volume`, `interaction_reach`, `target_occupancy`, or
`physics_body`. Conversely, an upper-body action may coexist with
`world_motion` when its root/pelvis/support claims and physical profile permit
that combination. A logical animation claim never proves a physical contact.

### IntentProposal

Source-specific proposal containing:

- `source_id` and `control_mode`
- `intent_tags`
- local movement and desired facing
- optional `action_tag`, target reference, and context tags
- priority hint and causation/correlation metadata

### LayerControlProposal

Internal output of Locomotion, Combat, Interaction, or Status. It contains:

- proposed movement/facing/action
- tags to add or remove from the local projection
- resource occupancy (`world_motion`, `facing`, `action`, `interaction`)
- cancellability and interruption reason
- optional root-motion policy

### CharacterIntentFrame

The sole merged actor ingress consumed by runtime execution. It contains the
resolved continuous-control set, zero or more admitted/queued/rejected action
updates, active action-instance references, authority context, motion
contributions, and the winning occupancy set for one physics tick. Downstream
components cannot replace it with a second frame in the same tick.

### CharacterRuntimeState

Read-only snapshot plus controlled transition API for:

- grounded/velocity/motion state
- active layer states and occupancy
- active action instances and phases
- control leases and canonical physical/visual occupancy
- pending authority requests
- effective capability/status projection
- latest authority result and presentation cues

### CharacterActionAssetDescriptor

```text
CharacterActionAssetDescriptor {
  semantic_action_id
  source_clip_ref
  realization_profiles
  canonical_skeleton_mapping_ref
  canonical_bone_mask_ref?
  atomic_sequence              # Phase 1 must be empty; semantic atom IDs only
  resource_claims
  physics_claims
  physics_profile_ref
  authority_route_ref      # esm | gameplay | composite (Phase 1)
  required_clips
  optional_clips
  required_slots
  locomotion_compatibility
  cancel_windows
  timing_markers
  root_motion_profile?
  root_motion_policy          # hold | bounded_continue | reversible_continue
  root_motion_required
  fallback_policy
  qualification_report_ref
  presentation_tags
  allowed_control_modes?
}
```

The descriptor never contains authoritative damage or world mutation.
`atomic_sequence` is a reserved semantic decomposition field, not a list of
animation clip names. In the first milestone it must be `[]`; an empty value
is valid and is the expected form for all imported assets. A future non-empty
sequence will resolve names through the versioned atomic-action registry and
expand into ordinary `ActionInstance` requests before resource arbitration.
The expansion therefore cannot bypass canonical resource claims, bone-mask
qualification, cancellation, timing markers, or authority attempts. Sequence
ordering is declarative until a future atom schema supplies explicit timing or
parallel-group metadata; the field alone must never be interpreted as
permission to run conflicting atoms concurrently.

## Actor Action Arbitration

`ActorActionArbiter` is the single owner of admission, canonical resource
claims, preemption, cancellation, queueing, and recovery. Locomotion,
interaction, combat, and status are proposal sources or state projections;
they do not independently write the body and are not four competing body FSMs.
Status produces constraints and severity; the arbiter applies them alongside
ordinary action claims. A policy may retain the compatibility priority
`Status > Interaction > Combat > Locomotion`, but priority never overrides a
physical-resource conflict or permits two final writers for one channel.

`EmbodiedActionController` remains the interaction/action phase executor. It
does not become a second global action FSM; the arbiter owns arbitration while
the controller owns phase playback and authority-request timing.

## External Asset Pipeline

Runtime package paths are canonicalized to `assets/active/<package_id>/` (for
example, `assets/active/crusader_knight/`). `assets/characters/...` may hold
authoring guidance, manifests, reports, or provenance only; it is not an
alternate runtime package root.

Each external asset package contains:

1. model and skeleton
2. animation clips
3. canonical-skeleton mapping profile
4. action/locomotion tag manifest
5. optional root-motion profiles

Import qualification rejects missing Skeleton3D, invalid rest pose, missing
required clips, missing required root bone, incompatible slots, and unmapped
action tags. Optional root motion may fall back to Motor-driven displacement;
required root motion rejects the action package.

External animation content remains authored outside the project. The asset
qualification pipeline may map package bone names, analyze actual animation
track impact, extract root motion, and produce a mechanically filtered
presentation variant. It must never infer at runtime that an arbitrary
full-body clip is safe to use as an upper-body concurrent action.

The qualification result is represented by one or more realization profiles:

```text
native_upper_body
derived_upper_body
full_body_exclusive
drive_locomotion
additive
```

The profile records its canonical mask, locomotion relation, root-motion
policy, source/derived clip provenance, fallback policy, and qualification
report. A semantic action may expose several qualified profiles; the Arbiter
selects one using current locomotion, canonical claims, and physics profile.
If no concurrent profile passes qualification, the action must remain
exclusive, queued, rejected, or presentation-only according to its declared
fallback. The complete import, track-analysis, derivation, and report contract
is defined by the animation asset qualification child specification.
Its `Normative Phase 1 Asset Delivery Rules` section is the single external
handoff checklist; this parent specification does not define a second asset
acceptance matrix.

## INF and Agent Integration

The legal direction is:

```text
INF facts / metadata / catalyst
-> CharacterAgent interpretation and planning
-> IntentProposal / context / evidence / constraint
-> local state/action arbitration
-> contact/request event
-> ESM, Gameplay, or registered Composite authority
-> committed authority result + metadata
-> CharacterRuntimeState projection
```

Siming remains catalyst-level. It can add `goal:*`, `constraint:*`,
`evidence:*`, or presentation hints plus `reason_codes` metadata, but it cannot
select a raw pose, move the body, emit an authority result, or confirm a world
consequence. INF/CharacterAgent may consume committed authority projections,
but cannot convert a proposal into a settlement by changing its metadata.

## Tick Ordering

The actor simulation runs on a fixed physics tick. Rendering frames may sample
the latest immutable snapshot, but they never become an alternate simulation
clock.

1. Collect source proposals and active control-lease renewals for physics tick
   `T`.
2. Evaluate all state layers against the previous runtime snapshot.
3. Resolve priority and occupancy into one `CharacterIntentFrame` for `T`.
4. Advance action executors and record marker observations with the same tick
   and action-instance identity; a presentation marker alone is not a contact.
5. Convert admitted movement, root-motion, impulse, and `runtime_correction`
   contributions into a collision-aware `PhysicsMotionCommand`.
6. Consume that command in `CharacterMotor`; only Motor may set velocity,
   perform collision motion, apply gravity, and call `move_and_slide()`.
7. Publish collision/grounded results as `PhysicsContactEvidence(T)`. At the
   same tick settlement boundary, combine marker observations with evidence
   into `ActionAttempt(T)` when physical evidence is required; actions that do
   not require it may emit after marker observation. Then emit
   `CharacterPresentationInput` to imported RoleSkin/AnimationTree.
8. Apply already-received authority results to runtime projections. Results
   received after `T` never retroactively re-run the completed tick.

## Physics And Authority Boundary

The action foundation does not treat animation root motion as physics truth. It
defines three distinct values:

```text
MotionContribution       # candidate from control/action/presentation
PhysicsMotionCommand     # deterministic, clamped Motor input for tick T
PhysicsEvidence          # observed collision/ground/contact result from Motor
```

`MotionContributionComposer` produces one deterministic command with separate
channels for desired velocity, root delta, impulse, `runtime_correction`,
facing, and constraints. It applies fixed limits for speed, acceleration,
impulse magnitude, vertical launch, and correction distance. Multiple impulses
are combined in stable action-instance order and then clamped by the actor's
current physical profile. A root delta is never applied with
`global_position +=`; it is converted to a velocity or swept-motion candidate
and passed through Motor collision handling.

Each action descriptor carries a non-authoritative `physics_profile_ref` whose
registered profile defines grounded/airborne requirements, root-motion
envelopes, speed and impulse limits, collision response, locomotion
coexistence, and required contact/support evidence. The profile constrains
local feasibility; it never grants a hit, damage, object mutation, or other
world consequence.

Phase 1 treats Godot physics as the local embodiment/collision executor and
evidence producer, while ESM/Gameplay or a registered Composite coordinator
remains semantic/world authority.
Registered static geometry, affordance anchors, occupancy, and object state are
settled by ESM. Dynamic world changes require an authority result and
corresponding world projection; a local rigid-body reaction is not sufficient
evidence. The local Motor may reject an impossible motion immediately, but it
cannot grant a world consequence.

The first milestone uses a kinematic `CharacterBody3D` path for actor motion.
It does not claim deterministic or authoritative simulation of arbitrary
`RigidBody3D` scenes. Any future dynamic physics feature must choose an
explicit `PhysicalAuthority` owner and define its tick, snapshot, correction,
and replay contract; ESM is not silently promoted into a rigid-body solver.

Physical contact is represented in two stages:

```text
Motor / sensor -> PhysicsContactEvidence (local, provisional)
                 -> ActionAttempt (marker + evidence digest)
ESM/Gameplay    -> range/affordance/status/revision validation
                 -> committed consequence or typed rejection
```

For connected play, client-supplied contact evidence is advisory telemetry.
The authority route must revalidate the target, action window, actor revision,
and permitted spatial envelope before settlement. A client cannot manufacture
an ESM hit, pickup, occupancy change, knockback, or damage result by sending a
positive collider flag.

## ESM/Gameplay ActionAttempt Contract

`ActionAttempt` is the bridge between a locally admitted action and an
authority-owned consequence. It must include:

```text
attempt_id
actor_ref
action_instance_id
semantic_action_id
target_refs[]
contact_marker_id
contact_marker_time_seconds?
action_family?             # melee | hitscan | interaction | other
weapon_ref?
physics_tick
physics_evidence_refs[]
physics_evidence_digest?
authority_route_ref      # esm | gameplay | composite (Phase 1)
owner_contract_ref?
expected_revision_vector
idempotency_key
command_version
causation_id
correlation_id
source_ref
privacy_scope
submitted_at             # transport audit metadata only
```

`submitted_at` is transport/audit metadata and is deliberately excluded from
`canonical_payload()`. A retry with the same stable business fields but a new
submission time is the same idempotent attempt; any other canonical field
change returns `payload_mismatch`. `owner_contract_ref` is accepted only when
issued by a server-side descriptor/catalog and must resolve to an ESM,
Gameplay, or Composite owner. It cannot be `inf`.

The Phase 1 envelope is bounded: serialized `ActionAttempt` is at most
`32 KiB`, `target_refs` and `physics_evidence_refs` are each limited to `8`,
and all evidence references must resolve to server-known, bounded records.
`control_intents` are limited to `8`, `action_request_ids` to `16`,
`collider_refs` to `32`, `hit_sensor_refs` to `16`, and `contact_points` to
`32`. A serialized `PhysicsContactEvidence` is at most `16 KiB`. Every
violation returns `payload_limit_exceeded`; truncation is forbidden. Evidence
remains advisory/provisional and never becomes client-supplied world truth.

The route is explicit:

- `esm`: environment affordance, spatial access, occupancy, and registered
  world-object state;
- `gameplay`: actor resources, status, capability, equipment, and ability
  settlement;
- `composite`: one authority coordinator validates both domains and appends
  one atomic multi-stream batch when the action changes both actor and world.

INF/Siming may supply context, constraints, evidence references, or a catalyst
for an attempt, but neither is an authority route. The coordinator maps
`ActionAttempt` to the existing `EmbodiedActionRequest`, `ActionWindowIntent`,
and Gameplay settlement commands rather than introducing a second protocol.

Independent same-tick attempts may settle independently. Attempts touching the
same aggregate or explicitly declared atomic group share expected revisions
and resolve as one conflict domain: at most one compatible revision can commit,
duplicate delivery returns the original result, and stale attempts return a
typed revision/precondition failure.

Authority results must carry `attempt_id`, `action_instance_id`,
`transaction_id` when committed, resulting revision vectors, failure stage, and
recovery action. They are projected into `CharacterRuntimeState` and the Godot
gameplay mirror only after the backend event/settlement boundary.

When an attempt changes both actor gameplay state and a world object, the
authority coordinator must settle the required actor/resource/body streams and
ESM/world-object streams in one atomic batch where the existing domain contract
requires atomicity. If the domains cannot share one transaction store, the
action must be declared non-atomic and expose an explicit reservation,
compensation, and failure policy; two independent acknowledgements must not be
described as one atomic result.

## Connected Runtime And Prediction Contract

The existing mirror protocol is sufficient for state projection but does not
by itself transport actor control. The action foundation therefore reserves
two structured directions over the existing session transport:

```text
Godot -> backend: control-lease renewals, ActionRequest, ActionAttempt
backend -> Godot: admission, authority result, `runtime_correction`,
                  gameplay snapshot/delta, resync
```

Every control or action message carries `session_id`, `actor_ref`,
`connection_epoch`, `client_sequence`, `physics_tick`, the relevant lease or
action revision, and causation/correlation data. Authority-bound requests also
carry a stable `idempotency_key` and expected revision vector. Backend delivery
uses the existing `delivery_sequence`, snapshot/delta base checks,
`facade_revision`, and prediction-resolution rules.

The first connected milestone has these limits:

- local Motor prediction may continue for movement and presentation, but it is
  never gameplay/world-truth confirmation;
- action visuals may start locally after admission, while contact-dependent
  root motion follows `hold`, `bounded_continue`, or `reversible_continue`;
- a backend `runtime_correction` is applied as a typed correction
  contribution on a later physics tick, then collision-validated by Motor;
- control leases expire when renewals stop, and new authority attempts are
  blocked while the session is stale or disconnected;
- duplicate, late, out-of-order, or old-epoch messages are ignored or routed
  to deterministic resync; a late result cannot resurrect an action instance;
- reconnect creates a new connection epoch and requires a fresh actor/runtime
  snapshot before new predictions or authority attempts resume.

This is connected authoritative action/mirror support, not full multiplayer
rollback. `netfox`, raw remote-pose driving, and server-authoritative rigid-body
simulation remain deferred. A future authoritative PvP physics mode must add
a clearly owned fixed-tick physics authority and reconciliation protocol.

Terminology is intentionally strict: Phase 1 `runtime_correction` is a
Gameplay/runtime projection contribution that still passes through the local
Motor and collision checks; it is not network physical authority. Future Mode C
uses `body_correction`, accompanied by `authority_epoch`, `body_revision`, and
`physics_tick`, on a separate body stream owned by `PhysicalAuthority`.

## Networked Physical Authority Reservation

The repository already has a Gameplay mirror transport with
`connection_epoch`, `delivery_sequence`, snapshot/delta base checks,
`facade_revision`, prediction IDs, and resync. Those fields govern gameplay
projections; they are not a physical replication protocol. The action
foundation reserves a separate typed body stream for a future connected
physical authority:

```text
Godot -> physical authority:
  actor_control_intent { actor_ref, physics_tick, client_sequence,
                         lease_revision, control_intent, action_ids }

physical authority -> Godot:
  actor_body_snapshot/delta { actor_ref, physics_tick, authority_epoch,
                              body_revision, position, velocity, facing,
                              grounded, active_action_ids, body_correction }
```

This stream must not carry raw bone poses or allow a remote client to write a
local Transform. A client may predict its own reversible Motor motion, but the
physical authority's body snapshot is the source used to correct divergence.
Remote actors consume snapshots/interpolation; they do not run an independent
world-truth simulation. `ActionAttempt` settlement and Gameplay mirror
messages retain their own transaction/revision identities and are correlated
to the body tick, but a body snapshot is not itself a gameplay event.

Before enabling this mode, the project must decide and document one owner for
the physical authority (dedicated backend physics worker, Godot authoritative
host, or another explicitly governed server). Until that decision and its
fixed-tick implementation exist, the honest scope is connected semantic
authority plus local embodiment, not multiplayer physics.

## Replay And Determinism Boundary

The deterministic guarantee is tiered:

- arbitration, resource claims, action admission, attempt ordering, idempotency,
  and authority settlement must be logically deterministic and replayable;
- Motor inputs use fixed physics delta, a pinned actor/physics profile,
  quantized network commands where applicable, and recorded correction/evidence
  references;
- exact bitwise replay of arbitrary Godot dynamic-body simulation is not
  promised. Replays compare normalized intent, command, collision evidence,
  authority result, and final accepted projection, with configured tolerances
  for local floating-point motion;
- a future physical authority may strengthen this to authoritative snapshot
  replay, but it must publish the engine/version/profile identity and body
  revision in its trace.

## First-Milestone Acceptance

For at least two qualified external characters:

- Idle/Walk/Run/Jump/Turn play through the shared presentation contract.
- Player and NPC use the same CharacterBody3D/Motor path.
- One external attack or interaction action supports phase markers, cancellation,
  optional root motion, and authority-request/recovery flow.
- At least one qualified package exposes an equipment slot/hand anchor and a
  standard melee action whose marker-to-`ActionAttempt` path reaches ESM/
  Gameplay and returns recovery.
- The connected semantic contract contains a hitscan action family and passes
  request/authority validation fixtures without implementing client-side
  ballistics, ammo, or damage truth.
- A real CharacterAgent/INF boundary message produces an Intent and a visible
  result in Godot.
- No non-Motor path writes `global_position`, `velocity`, or world truth.

Additional physics/authority/network acceptance:

- root motion against a wall, slope, and step is collision-resolved by Motor;
- simultaneous movement/root/impulse contributions produce the same clamped
  result under repeated replay;
- local contact evidence without a matching ESM/Gameplay settlement never
  changes world state;
- two independent same-tick attempts can settle separately, while attempts
  racing for one aggregate resolve by revision/idempotency rules;
- duplicate, gap, late, disconnect, reconnect, and old-epoch deliveries have
  deterministic handling;
- a rejected or timed-out attempt releases claims and resumes/recovers the
  control lease without a second transform writer; and
- the connected path proves intent/attempt transport and authority projection,
  while explicitly not claiming multiplayer rollback or remote raw-pose
  authority.

## Engineering Support Surfaces

The following support surfaces are part of the action-foundation delivery.
They observe or exercise the same runtime contracts; none may become another
body controller, state authority, action scheduler, or world-truth writer.

### Runtime Debug Overlay

`CharacterRuntimeDebugOverlay` is a read-only view over one selected actor's
post-arbitration snapshot. It presents:

- every `ContinuousControlLease`, its source, revision, expiry, and effective
  state;
- every `ActionInstance`, lifecycle phase, admission decision, resource claim,
  locomotion relation, marker, and pending `attempt_id`;
- the resolved `CharacterIntentFrame`, including admitted/queued/rejected
  requests and deterministic ordering key;
- the `ResourceClaimScheduler` result, canonical-resource occupancy, claim
  conflicts, preemption, and cancellation reason;
- `MotionContributionComposer` inputs and final desired velocity, root delta,
  impulse, correction, and facing values; and
- `CharacterMotor` grounded state, current velocity, requested velocity,
  collision count, facing, and timing.

The overlay receives immutable debug snapshots after arbitration and after the
Motor tick. It does not inspect mutable internals by reference and has no API
that changes actor state.

### Test Control Panel

`CharacterRuntimeTestPanel` is enabled only for editor, test, or explicit
development builds. It can select an actor, spawn a registered test actor,
adjust approved runtime tuning values, submit a named fixture
`ControlIntent`/`ActionRequest`, and request a test-only authority fixture.

"Force state" is deliberately not a direct mutation. It is represented as a
traceable, expiring debug control lease, action request, or simulated
authority result passing through the normal Arbiter and authority projection.
The panel labels all injected data with `source=debug_fixture`, correlation
data, and a test scope. Production builds omit the panel and reject that
source.

### Animation Debugger

`CharacterAnimationDebugger` is a presentation-only tool. It shows active
clips, canonical bone masks, blend weights, root-motion extraction, markers,
and current animation time. Preview play, pause, seek, and frame stepping run
in an isolated animation-preview mode: they never call the Motor, emit an
`ActionAttempt`, or commit world state. A full simulation single-step remains
a separate operation that advances the ordinary physics tick and is visibly
labelled as such.

### Performance Monitor

`CharacterPerformanceMonitor` exposes rolling and capture-window measurements
for FPS, frame time, physics time, ActorActionArbiter time,
ResourceClaimScheduler time, MotionContributionComposer time, CharacterMotor
time, presentation/animation time, and active action/claim counts. It uses
sampled telemetry and bounded history rather than per-tick unbounded logs.
Performance instrumentation is observational; gameplay and arbitration must
not branch on its measurements.

## External-Asset Authoring Contract

The canonical skeleton mapping is the semantic contract. The following
conventions make third-party assets qualification-ready without requiring the
project to author animation content.

### Naming and Directory Layout

Use lower-case snake case:

```text
<category>_<action>_<variant>

locomotion_walk_forward
locomotion_run_strafe_left
combat_sword_light_01
interaction_pickup_kneel
reaction_hit_upper_body
```

`category` is one of `locomotion`, `combat`, `interaction`, `reaction`,
`utility`, or `expression`. `variant` is required; use `default` where a
semantic action has one variant. Clip names describe the asset only; semantic
action IDs remain the manifest's typed runtime identifiers.

Use this package layout:

```text
assets/characters/<character_id>/
  model/
  materials/
  textures/
  animations/
    locomotion/
    combat/
    interaction/
    reaction/
    utility/
    expression/
  manifests/
  docs/
```

For example, player locomotion clips live below
`assets/characters/player/animations/locomotion/`. Shared animations may be
referenced by a package manifest but must still be qualified against that
package's canonical-skeleton mapping.

### Import Requirements

- Deliver preferred runtime-ready assets as glTF 2.0 binary (`.glb`); retain
  source DCC files outside the runtime package. FBX is an accepted intake
  format only when it is converted and qualification-tested for the target
  Godot version.
- Use metres: one authored unit equals one Godot world metre. Apply object
  transforms, uniform scale, and rotation before export; do not rely on
  runtime scene scaling to correct an asset.
- Export a stable rest pose, a declared root bone, and animations sampled at
  60 FPS unless a manifest explicitly declares a justified source rate. The
  qualification report records the actual rate; runtime timing is marker/time
  based, never inferred from a clip filename.
- Bake only the skeletal transforms intended for the clip. Root translation
  and rotation must be explicit and match the manifest root-motion policy.
- Preserve the canonical forward/up convention, skeleton names/mapping, and
  equipment attachment bones required by the package manifest.

### Action Timing Sheet

Every semantic action has a timing document in its package `docs/` directory.
It records the clip and variant, duration/source rate, resource claims and
bone mask, locomotion relation, root-motion policy, and these named times in
seconds and source frames:

```text
blend_in
windup_start
contact_marker[n]
active_start / active_end
cancel_open[n] / cancel_close[n]
recovery_start
blend_out
loop_enter / loop_exit       # sustained actions only
```

The sheet identifies which contact marker emits an `ActionAttempt`, whether
the action is `local_only`, and the authority-pending motion policy. This
sheet is the author-facing source for manifest validation; it does not contain
damage, hit, inventory, or other world-truth values.

## Reserved Extension Points

The first milestone deliberately reserves, but does not implement, these
extensions:

- additional input/behavior sources through the existing control-lease and
  action-request adapters;
- advanced equipment (two-handed tools, mounts), tails, wings, and other future
  anatomy through versioned asset manifests and an explicitly reviewed future
  resource-graph revision, never per-package conflict rules;
- navigation/RVO suggestions as `ControlIntent` candidates, with Motor still
  deciding physical motion;
- visual modifiers such as foot IK, look-at, recoil, motion matching, facial
  animation, audio, and VFX behind `RolePresentationAdapter`;
- compound actions as explicitly declared atomic attempt groups, distinct from
  ordinary independent same-tick attempts;
- replay capture, multiplayer prediction, and network transport around the
  existing ordered attempt and authority-result trace; and
- new status/capability/affordance IDs through typed registries plus a schema
  version, not a universal free-form tag bag.

These are not permission to add a second `CharacterBody3D` controller, a
plugin-owned action authority, a parallel locomotion owner, or a new direct
Transform-writing path.

## Atomic Action Library Reservation

The asset contract reserves the following field for a future semantic atom
library:

```gdscript
@export var atomic_sequence: Array[StringName] = []
```

Phase 1 keeps this field empty for every qualified action asset. No atomic
action authoring, lookup, expansion, or runtime sequencing is required for
the first milestone. A future asset may contain entries such as:

```gdscript
atomic_sequence = [&"StepForward", &"SwingRightArm", &"LeanForward"]
```

These are typed semantic atom IDs, never animation clip names. A versioned
atomic-action registry will eventually resolve them and expand the sequence
into ordinary `ActionInstance` requests before the existing resource scheduler
and motion composer run. Each atom will therefore inherit canonical resource
claims, bone-mask qualification, cancellation/recovery rules, contact-marker
and authority semantics. The sequence field alone does not authorize
conflicting atoms to run concurrently; future timing or parallel-group
metadata must make that choice explicit and deterministic.

## Explicit Deferrals

- No authored animation production.
- No complete combo, hit-reaction, death, or survival animation library.
- No runtime module hot-unplug.
- No netfox rollback integration.
- No plugin-owned CharacterBody3D controller.
- No local damage truth in action assets.
- No complete weapon runtime: ammunition, magazines, chambers, ballistic
  projectiles, dual wielding, parry/clash, or arbitrary prop weaponization.

## Related Repository Truth

- `docs/character/character-actor-final-convergence-target.md`
- `docs/character/character-actor-architecture.md`
- `docs/character/character-action-asset-interface.md`
- `docs/character/character-agent-runtime-architecture.md`
- `docs/character/character-action-foundation-current-state.md`
- `docs/superpowers/specs/2026-09-14-character-physics-motion-and-contact-subspec.md`
- `docs/superpowers/specs/2026-09-14-character-esm-action-attempt-settlement-subspec.md`
- `docs/superpowers/specs/2026-09-14-character-connected-action-and-physical-replication-subspec.md`
- `docs/superpowers/specs/2026-09-14-character-animation-asset-qualification-and-concurrent-realization-subspec.md`
- `docs/superpowers/plans/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-implementation-plan.md`
