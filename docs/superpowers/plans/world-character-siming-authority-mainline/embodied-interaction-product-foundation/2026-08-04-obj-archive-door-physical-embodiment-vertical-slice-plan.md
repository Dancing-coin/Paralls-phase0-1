# obj_archive_door Physical Embodiment Vertical Slice Plan

Status: `implementation-active; all three required failure paths have fresh real-MainDemo evidence, while the applied success case remains blocked fail-closed by the unreachable reviewed contact anchor`

Date: `2026-08-04`

Parent constraint: `2026-08-01-atomic-action-library-and-default-scene-coverage-plan.md`

## Execution Update (2026-08-04)

The candidate probe reliability repairs are complete: asynchronous finish paths
are awaited, controller binding derives from `state == bound`, the host advances
on physics ticks, and the success fixture no longer teleports or directly
rotates `PlayerShell`. Focused authority/Godot/verifier checks pass. A real
localhost backend plus MainDemo run proves one-time controller enrollment and
WebSocket binding, `PlayerShell`-owned movement of approximately `1.67m`,
near-zero facing error, and ordered phases through `execute_contact`; no door
state, leaf, collision, occlusion, settlement, or world result changes before
authority settlement.

The same route also establishes a material geometry blocker. With the reviewed
`binding_revision=2` contact anchor at world approximately
`[0.81, 3.324, -3.958]`, the shipped right-arm chain
`Bip001 R UpperArm -> Bip001 R Forearm -> Bip001 R Hand` reaches only about
`[0.32, 2.67, -3.60]`. Built-in `SkeletonIK3D`, the existing modifier path,
and the narrow local fallback remain about `0.87m` from the anchor, versus
the required `0.08m` tolerance. The rig's effective rest-chain reach is about
`0.52m`. This is not a solver-tuning defect that may be hidden by a local
transform write or a semantic fallback.

Accordingly, the route correctly emits no terminal contact observation,
applied settlement, object result, or presentation, and the door remains
closed. A human-reviewed reachable contact anchor and a new shared binding
revision are now required before the success acceptance row can be implemented
truthfully. Until then, retain the existing failure recovery and no-world-write
behavior; do not infer or silently replace the reviewed anchor.

### 2026-08-04 live evidence update

The wording above describes the positive contact claim only. The route now
does emit a bounded terminal failure when contact alignment is impossible:
`failed_alignment/ik_alignment_tolerance_exceeded`, followed by one rejected
authority settlement and local recovery. Its current success-scenario probe
records `1.669m` real movement, near-zero facing error, measured contact error
of approximately `0.87m`, `commit_count=0`, no object result, and an unchanged
closed door.

The three required failure paths are now independently live-verified:

1. Distance: backend `out_of_range`; no grant, settlement, ledger attempt, or
   mutation; host runs `recovery_without_grant`.
2. Revision: a verifier-owned binding revision increment after authoritative
   preflight yields `binding_revision_mismatch`; local recovery and replay
   validation pass with 11 ordered events and zero mutation.
3. Stance: local `stance_occupied` yields one `not_committed` settlement;
   local recovery and replay validation pass with five ordered events and zero
   mutation.

The verifier also now admits only the typed semantic atom/recovery fields that
the controller emits, enforces a 30-second bounded physical grant and a
45-second scenario watchdog, and uses a monotonic contact-settle timeout. These are reliability
repairs to the existing route; they neither move the reviewed anchor nor allow
Godot to write world truth.

### 2026-08-04 aggregate checkpoint

The full registered harness run `run-20260804-220632-133304` passed every
predecessor profile through `godot-gameplay-mirror` and then stopped at the
door profile. Its canonical report,
`.harness/verification/obj-archive-door-physical-embodiment-report.json`,
proves the focused suite plus `distance_failure`, `revision_failure`, and
`stance_failure`. It deliberately marks only `scenario-success` as missing:
there is no applied settlement, open object result, or open presentation
snapshot while the reviewed anchor remains unreachable. This is the required
fail-closed result, not a basis to weaken contact tolerance, teleport the
player, alter the anchor locally, or report the semantic door route as physical
success.

The next executable input for this slice is therefore external rather than a
new code workaround: review a reachable `ContactAnchor`, issue the matching
new `binding_revision`, synchronize that record across the scene bridge,
policy, fixture, and replay expectations, then rerun the exact verification
order in section 9. Until then the three failure cases remain regression
coverage and the success row remains open.

## 1. Intent And Narrow Boundary

This plan closes exactly one reviewed MainDemo affordance:
`obj_archive_door` with semantic action `open`. It is a physical embodiment
vertical slice, not a generic door framework and not a rewrite of the Atomic
Action Library / Default Scene Coverage parent plan.

The slice is complete only when a real player shell locally approaches and
aligns with the reviewed door stance/contact anchors, locally performs the
registered atoms with measured hand alignment, and changes the visible door
only after the backend has committed and published an applied settlement.

The MainDemo command surface supports only `closed -> open` for this slice.
The existing semantic ESM `close` transition remains an internal compatibility
test surface. MainDemo, the WebSocket player-input route, and the physical
presentation must return `physical_close_not_implemented` for `close` until a
separate physical close slice reuses this same host, authority coordinator,
presentation gate, and evidence contract. It must not restore a direct semantic
mutation path.

### In scope

1. A real `PlayerShell -> CharacterMotor` approach/align path to the reviewed
   archive-door anchors.
2. Existing registered atoms `start_move`, `turn_to_target`, `raise_hand`,
   `tap_contact`, and `recover_balance` bound to the appropriate controller
   phases through the sole `CharacterEmbodimentAssetRegistry`.
3. A measured local right-hand alignment to the reviewed contact anchor using a
   capability-gated IK implementation. Motion warping is not required for this
   stationary contact slice.
4. A single backend-owned preflight and outcome settlement path, including
   connection-bound grant validation, one-time outcome consumption, ESM commit,
   idempotency, and correlated replay evidence.
5. Applied-result-only door leaf, passage collision, and local occlusion
   presentation, plus the four acceptance cases in section 10.
6. A focused harness profile that launches the real `MainDemo` with a live
   backend, not a semantic door probe, chair probe, or synthetic component
   scene.

### Explicit non-goals

- Generic doors, locks/keys, door sounds, imported opening clips, multiplayer
  arbitration, dynamic navigation obstacle injection, or AI replanning.
- Full motion generation, full-body motion warping, raw bone streams, remote
  high-frequency pose driving, or VLA selecting atoms, steering movement, or
  writing world truth.
- A second action asset registry, a second `CharacterBody3D` or
  `move_and_slide()` owner, direct Godot ESM/object/occupancy writes, or a
  client-provided target transform/anchor/bone payload.
- Treating `DefaultSceneLetterAffordanceProbe` or
  `EmbodiedKickChairVerticalSliceProbe` as evidence for this door.

No new dependency is permitted.

### Preconditions and preserved boundaries

- The reviewed `obj_archive_door` scene record, explicit anchor/collider IDs,
  `binding_revision=2`, and the backend `closed -> open` ESM policy are the
  starting contract. A failed static or runtime inspection blocks this slice;
  it does not license an inferred anchor, node-name affordance, or fallback
  semantic success.
- The existing `PlayerShell -> CharacterMotor` ownership chain, the sole
  `CharacterEmbodimentAssetRegistry`, `EmbodiedActionController` route gate,
  loopback controller-binding service, ESM writer, and
  `ArchiveDoorPhysicalPresentation` applied-result gate are reused. This plan
  does not replace any of them or introduce a parallel actor, action registry,
  world-state writer, event store, or WebSocket transport.
- The real verification launch must have a local Godot executable, an
  available loopback backend, and a server-minted one-use controller
  enrollment. Missing rig/solver/anchor capability is a typed fail-closed
  outcome, not an excuse to bypass the physical path.
- Preserve all pre-existing worktree changes. In particular, execution must
  not modify `docs/7月分析/2026-08-03-活跃plan与spec进度分析.md` or
  `scripts/verification/check_godot_project.py`.

## 2. Current Code Facts And Gaps

The table describes the working tree as inspected on 2026-08-04. Candidate
implementation files and focused tests already present in the dirty worktree
are verification inputs, not accepted implementation. A file being present or
a static test passing is not evidence that its behaviour has passed a live
Godot run.

| Current fact | Evidence | Remaining gap / required plan response |
| --- | --- | --- |
| The physical scene and an applied-result presentation component exist. It contains `ApproachStance`, `ContactAnchor`, `ObservationAnchor`, `HingePivot/DoorLeaf`, and `ClosedPassageBlocker`. | `scenes/phase0/ArchiveDoorPhysical.tscn:16-50`; `scripts/object/ArchiveDoorPhysicalPresentation.gd:23-74`; `.harness/verification/obj-archive-door-physical-embodiment-runtime.json` | A real MainDemo run measures the reviewed contact as approximately `0.87m` beyond the shipped hand reach, so the scene remains fail-closed. Collision and occlusion are presentation-only gates, with no dynamic navigation update. |
| The presentation opens only for `object_state_result`, `settlement_status=applied`, `current_state=open`; it rotates the hinge, disables the closed collision shape, records `passage_occlusion_state`, and emits a bounded post-apply receipt. | `ArchiveDoorPhysicalPresentation.gd:33-63,79-117`; fresh failure snapshots under `.harness/verification/obj-archive-door-physical-embodiment-*-failure.png` | All required failure paths now prove unchanged leaf/collision/occlusion snapshots. An applied-presentation receipt remains intentionally unverified because no successful contact can truthfully occur. Dynamic navigation is explicitly absent. |
| `MainDemo` instances the physical door and explicit archive-door bridge; `CharacterBase` already instances `ArchiveDoorEmbodiedActionHost` under the `CharacterBody3D` player shell. The host correlates preflight constraints, settlement rejection/cancellation/resync, and terminal local cleanup. | `scenes/phase0/MainDemo.tscn:142-143,5936-5941`; `scenes/phase0/CharacterBase.tscn:3-8,44-51`; fresh runtime artifacts | Real WebSocket/MainDemo probes now prove rejected-settlement recovery and restored local ownership for stance, revision, and contact-tolerance failure. Applied-result recovery remains blocked on the reviewed anchor. |
| The bridge resolves explicit local NodePaths and pins the shared `binding_revision=2`, affordance, execution profile, observation rule, and policy IDs. | `scripts/interaction/ArchiveDoorEmbodiedAffordanceBridge.gd:8-18,78-113,174-184`; `backend/app/services/default_scene_archive_door_embodied_service.py:42-66` | The canonical strings now agree in source, but the live profile must prove that the reviewed geometry, rule, and revision stay equal across preflight, contact, settlement, and presentation; no semantic fallback is allowed. |
| `EmbodiedActionController` has a non-blocking start/advance/finish API while retaining `run_attempt()`, and the new host consumes it. The host reserves an explicit local stance lease and performs a bounded approach-obstacle check before issuing forced movement. | `scripts/interaction/EmbodiedActionController.gd:109-193`; `scripts/interaction/ArchiveDoorEmbodiedActionHost.gd:52-183`; `scripts/interaction/ArchiveDoorEmbodiedAffordanceBridge.gd:96-145`; `.harness/verification/obj-archive-door-physical-embodiment-runtime.json` | The live success diagnostic records the ordered phases through `execute_contact`; revision and stance diagnostics record terminal local recovery. The bounded contact outcome has no pre-settlement `object_observation`, which preserves the no-local-world-claim boundary. Only the applied contact remains blocked by the reviewed anchor. |
| The only movement owner remains `CharacterMotor.apply_intent_frame()`, called by `PlayerShell`; it now consumes the existing `desired_facing_yaw` field. | `scripts/player/PlayerShell.gd:106-118, 194-236`; `scripts/character/CharacterMotor.gd:8-43`; `.harness/verification/obj-archive-door-physical-embodiment-runtime.json` | A real MainDemo diagnostic proves `motor_owner=PlayerShell`, approximately `1.669m` local displacement, and near-zero facing error without a host transform write or second `move_and_slide()` owner. The applied contact remains blocked by the reviewed anchor. |
| The catalog has exactly the five reviewed atoms needed by this slice and the playback adapter delegates to `CharacterReplica`, which already exposes narrow forwarding to its role skin. | `scripts/character/DefaultSceneActionAtomCatalog.gd:8-62`; `scripts/character/CharacterEmbodimentAssetRegistry.gd:36-153`; `scripts/interaction/EmbodiedActionPlaybackAdapter.gd:11-48`; `scripts/character/CharacterReplica.gd:224-240`; `.harness/verification/obj-archive-door-physical-embodiment-runtime.json` | The live local outcome names `start_move`, `turn_to_target`, `raise_hand`, `tap_contact`, and `recover_balance`; stance and revision rejections prove result correlation and local recovery. No duplicate registry or private scene traversal is permitted. |
| `KnightRoleSkin` exposes the real `Skeleton3D`, caches right arm/forearm/hand bones, plays the reviewed atoms, and contains a capability-gated right-hand reach path: `SkeletonIK3D` first, followed by the existing modifier-chain fallback. | `scripts/character/KnightRoleSkin.gd:243-260,345-370,734-818`; `scripts/character/KnightCombatModifier.gd:1-95`; `.harness/verification/obj-archive-door-physical-embodiment-runtime.json` | A real MainDemo diagnostic discovers the right-arm chain and records the active bounded reach measurement. It proves the required fail-closed tolerance recovery (approximately `0.87m` versus `0.08m`), not a successful IK solution; motion warping remains unimplemented and deferred. |
| A door-specific backend service intercepts `obj_archive_door/open`, requires a same-connection controller binding, issues a grant, commits ESM before creating an object result, caches duplicate outcomes, and records ledger/settlement/presentation correlations. A trusted-local controller launcher and focused backend tests are present. | `backend/app/services/default_scene_archive_door_embodied_service.py:41-527`; `backend/app/services/trusted_local_embodied_controller_launcher.py`; `backend/app/main.py:232-241, 1318-1381, 1862-1890`; `backend/app/services/esm_service.py:1098-1138`; `backend/app/models/world_result.py:54-60`; `backend/tests/test_obj_archive_door_embodied_authority.py`; `.harness/verification/obj-archive-door-physical-embodiment-runtime.json` | A live trusted-local enrollment/bind and rejected settlement/replay correlation are now proved. Positive applied-result correlation and the bounded presentation receipt remain regression-covered but live-unproved until a reviewed reachable anchor permits an authority-applied result; hostile receipt rejection remains a focused backend requirement. |
| Controller grants are connection-bound in auth, and phase ingress validates ordered source sequences. | `backend/app/services/embodied_controller_auth_service.py:43-199`; `backend/app/services/embodied_execution_ingress.py:44-109` | Door settlement must remain the only terminal grant consumer. The generic ingress's `handle_local_outcome()` still consumes grants and emits `attested_pending_authority_settlement` for non-door attempts; the door route must never pass through it first. |
| `EmbodiedEvidenceLedger` provides `server_ledger_sequence` and validates the base request -> binding -> phase -> terminal -> settlement order while rejecting presentation-before-settlement. The dedicated `embodied_presentation_observed` route checks the bound connection and matching settlement before it appends `presentation` evidence. | `backend/app/services/embodied_evidence_ledger.py:24-140`; `backend/app/main.py:1369-1381`; `default_scene_archive_door_embodied_service.py:457-526`; `scripts/object/ArchiveDoorPhysicalPresentation.gd:79-117`; `scripts/autoload/BackendBridge.gd:278-287`; replay design §Evidence Ledger | The focused verifier must prove the route live and reject malformed, wrong-connection, or wrong-settlement receipts without any ledger presentation append or world/presentation mutation. Its artifact must join `attempt_id`, `grant_id`, `settlement_id`, revisions, server sequence, and the Godot evidence filename. |
| Focused backend/static tests and the `obj-archive-door-physical-embodiment` harness profile, MainDemo wrapper probe, verifier, and profile tests are present in the dirty worktree. | `backend/tests/test_obj_archive_door_embodied_authority.py`; `backend/tests/test_obj_archive_door_embodied_godot_static.py`; `backend/tests/test_obj_archive_door_embodied_local_static.py`; `scripts/verification/ObjArchiveDoorPhysicalEmbodimentProbe.gd`; `scripts/verification/verify_obj_archive_door_physical_embodiment.py`; `.harness/profiles/obj-archive-door-physical-embodiment.json` | Fresh diagnostic reports prove physical movement, failure recovery, authority settlement, replay joins, and all three required failure paths. The profile is not green because its required applied-open row is still blocked by the reviewed anchor. |
| The latest focused physical report is red for the right reason: the real `success` scenario reaches `execute_contact`, measures an unreachable contact error, and receives `ik_alignment_tolerance_exceeded` with no commit or presentation. | `.harness/verification/obj-archive-door-physical-embodiment-runtime.json`; `obj-archive-door-physical-embodiment-backend-settlement-trace.json`; `obj-archive-door-success-godot.log` | Do not turn this into a semantic success or silently relocate the anchor. The next admissible change is a human-reviewed anchor plus shared binding revision update. |
| The physical probe starts from the authored launch fixture, sends normal structured move input, and waits for the normal host-owned approach/align route; it does not assign player position or body yaw. | `scripts/verification/ObjArchiveDoorPhysicalEmbodimentProbe.gd:115-126,180-222`; `.harness/verification/obj-archive-door-physical-embodiment-runtime.json` | The MainDemo diagnostics record `PlayerShell` as the motor owner, approximately `1.669m` displacement, and near-zero facing error. A direct transform setup remains inadmissible for success evidence. |

## 3. Locked Ownership Decisions

### 3.1 Real entry point

The entry extends the existing dedicated `ArchiveDoorEmbodiedActionHost` child
of `MainDemo/PlayerCharacter` in `scenes/phase0/CharacterBase.tscn`. It owns
one door attempt's lifecycle: request correlation, controller phase advance,
reviewed-atom playback coordination, local stance lease, bounded contact
measurement, terminal recovery, and evidence collection.

It is neither a `PlayerShell` replacement nor a `CharacterReplica` movement
owner.

- `PlayerShell` stays the physical body and the sole caller of
  `CharacterMotor.apply_intent_frame()`.
- `CharacterMotor` remains the sole `move_and_slide()` and body-yaw writer.
- The host only calls `Phase0PlayerBridge.set_forced_player_motion()` /
  `clear_forced_player_motion()` and the existing forced-facing forwarding
  methods. It may not assign `global_position`, `global_transform`,
  `velocity`, or body rotation.
- `CharacterReplica` is only the visual/playback/IK delegation boundary. It
  gets no locomotion method and performs no authority/range/preflight check.
- `EmbodiedActionController` remains phase/state and local observation owner.
  `run_attempt()` remains a test-probe compatibility wrapper; the host uses its
  non-blocking API.

### 3.2 Canonical IDs and revisions

The narrow physical route has one shared record, used identically by backend
and Godot:

```text
target_object_id:  obj_archive_door
affordance_id:     affordance:obj_archive_door:open
action_semantic:   open
binding_revision:  2
execution profile: execution_profile:obj_archive_door:open:v1
observation rule:  observation_rule:archive_door_contact:v1
policy ref:        authority_policy:esm_open_archive_door:v1
```

The backend may store only stable IDs and revisions. It must never receive a
Godot NodePath, hand/bone transform, raw input, raw camera data, or a client
world-state claim. The bridge resolves the stable records locally through
explicit exported NodePaths.

## 4. End-to-End Sequence

```text
trusted-local door verifier/launcher
  -> server mints one short-lived controller enrollment for {char_c, controller instance}
  -> launcher injects it only into the Godot child environment
  -> bootstrap sends embodied_controller_bind over the loopback WebSocket
  -> backend binds {binding_id, connection_epoch, connection_ref}

player submits structured interact_intent {request_id, char_c, scene scope,
  obj_archive_door, open}; no raw control/pose/anchor/world fields
  -> main.py builds normal ActionRequest
  -> DefaultSceneArchiveDoorEmbodiedService.preflight()
       validates connection binding, reviewed policy/state/revision, server actor range,
       request idempotency, and target attempt occupancy
  -> ConstraintStateResult (no grant) OR one EmbodiedActionRequest + Grant

BackendBridge -> LocalPresentationBus.embodied_action_request_received
  -> ArchiveDoorEmbodiedActionHost resolves the matching explicit bridge
  -> controller reserve_stance -> plan_approach -> navigate -> align
  -> PlayerShell forwards forced intent to CharacterMotor, which is the sole mover
  -> host measures stance and facing success before prepare
  -> prepare / execute_contact play existing atoms and run bounded local IK
  -> host sends ordered embodied_phase_event records and receives their safe acknowledgements
  -> exactly one bounded embodied_local_outcome containing measured contact evidence;
     it contains neither `current_state=open` nor any world-state claim

DefaultSceneArchiveDoorEmbodiedService.handle_local_outcome()
  -> validates source sequence/attestation and consumes the grant once
  -> revalidates pinned versus live binding/policy/state
  -> appends request, binding, legal phase, terminal, and settlement ledger records
  -> ESM commits closed -> open exactly once
  -> server creates settlement_id, receipt, and applied ObjectStateResult
  -> publishes settlement result, then object_state_result

ArchiveDoorPhysicalPresentation
  -> accepts only matching applied ObjectStateResult
  -> sets open leaf transform, releases closed collision, sets local occlusion=open
  -> emits a bounded post-apply presentation observation {attempt_id, settlement_id,
     snapshot_digest}; backend appends the ledger `presentation` event
  -> host releases stance, clears forced ownership/IK, and plays recovery.
```

The trusted-local credential is never written to diagnostics, ledger payloads,
replay records, screenshots, or generated artifacts. Existing gameplay-mirror
enrollment is not interchangeable with the embodied controller enrollment;
reuse only its server-issued, launch-only secret handoff pattern.

Preflight distance is backend truth. The valid runtime fixture begins inside
the existing server policy range but outside the exact reviewed stance, so it
must demonstrate measurable local approach motion without claiming local
movement establishes backend range truth.

Preflight may reject before the host obtains a grant. `MainDemoController`
must register the correlated pending door submission with the host, and the
host must receive its matching constraint result, clear any provisional local
state, invoke `recover_balance`, and record `preflight_rejected`. It must not
send a fabricated local outcome for a grant it never received.

## 5. Local Physical Realization Contract

### 5.1 Approach, align, atoms, and movement ownership

| Controller phase | Required existing atom | Local work | Transition guard |
| --- | --- | --- | --- |
| `plan_approach` / `navigate` | `start_move` | Host calculates a bounded planar direction to `ApproachStance`, requests it through `Phase0PlayerBridge`, and records actual `PlayerShell` position delta. | Actual horizontal stance error must decrease; a phase trace alone is insufficient. |
| `align` | `turn_to_target` | Host sets only the existing forced `desired_facing_yaw`; `CharacterMotor` rotates using its bounded `rotate_toward()` path. | Measured yaw error to `ContactAnchor` is within the explicit tolerance before `prepare`. |
| `prepare` | `raise_hand` | Playback through the registry -> adapter -> `CharacterReplica` -> `KnightRoleSkin`; activate bounded reach alignment. | Valid stance/facing and successful rig capability only. |
| `execute_contact` | `tap_contact` | Contact window plus hand-to-anchor measurement; construct only bounded contact evidence, including the reviewed observation-rule ref and scalar error. | Hand distance <= `0.08m`, reviewed anchor/collider/rule IDs match, and no local failure exists. |
| `recover` | `recover_balance` | Restore playback, modifier state, stance lease, forced motion, and forced yaw. | Runs after success and every failure/cancel path. |

The `DefaultSceneActionAtomCatalog` is registered into one
`CharacterEmbodimentAssetRegistry` for each active host lifecycle. The host
must request precisely the listed atom keys. It cannot introduce a second
dictionary catalog, clip lookup, or action asset contract.

Local prepare playback is allowed before settlement. It is explicitly
presentation-only: it cannot rotate the door, disable collision, change ESM
state, publish a success result, or set `passage_occlusion_state=open`.

### 5.2 IK capability and fallback

The dirty worktree contains candidate right-hand reach wiring in `KnightRoleSkin`
and a pre-existing `SkeletonModifier3D` chain, but no accepted MainDemo runtime
proof that the shipped rig can meet the contact tolerance. There is no accepted
production IK or motion-warping capability. The physical slice therefore uses
this capability-gated, fail-closed implementation order:

1. A real MainDemo capability probe uses `ClassDB.class_exists("SkeletonIK3D")`
   before attempting that built-in solver against the shipped
   `KnightRoleSkin` `Skeleton3D`, the discovered right upper-arm/forearm/hand
   chain, and the reviewed `ContactAnchor`. Record the concrete
   `ik_runtime_kind`, chain IDs, and measured hand error. The plan makes no
   claim that another IK class is installed until this probe proves it.
2. If `SkeletonIK3D` is absent or cannot instantiate, bind, and meet the
   tolerance for the shipped rig, first evaluate the existing
   `KnightCombatModifier` chain as the narrow fallback. Add
   `ArchiveDoorReachModifier extends SkeletonModifier3D` only when a failing
   capability test proves the existing modifier cannot host the reviewed reach.
   Attach any such modifier to that existing chain rather than replacing
   `KnightCombatModifier`. It is active only for the prepare/contact window and
   uses the reviewed right arm chain in rig-local space.
3. The modifier may set only local bone poses and report a scalar/vector
   measurement for the local artifact. It may not change `PlayerShell` world
   transform, consume network bone data, expose bone transforms in the outcome,
   replace animation playback, or become an action registry.
4. Missing skeleton/chain/target, modifier initialization failure, or an error
   above `0.08m` returns `failed_alignment` with respectively
   `ik_chain_unavailable`, `ik_target_unavailable`, or
   `ik_alignment_tolerance_exceeded`; it sends no contact observation and
   executes recovery.

Motion warping is explicitly deferred. Stationary local IK after real motor
approach is the minimal implementation. An animation clip, a manual transform
placement, or an unmeasured arm overlay is not acceptable substitute evidence.

### 5.3 Minimum physical door presentation

Required successful applied presentation:

- `HingePivot/DoorLeaf` moves from its recorded closed transform to its recorded
  open transform.
- `ClosedPassageBlocker/CollisionShape3D` is disabled only after the applied
  result, making the player collision path passable.
- `passage_occlusion_state` changes from `closed` to `open` only after the same
  result and the snapshot records its `applied_settlement_id`.

This slice proves collision and occlusion presentation. It explicitly defers
`NavigationServer3D` dynamic obstacle injection and AI rerouting. It must not
describe that deferred work as navigation proof.

## 6. File-Level, Test-First Execution Plan

Every numbered implementation phase starts by adding and observing its named
failing tests before production changes. Existing dirty working-tree changes
are inputs to reconcile, not authority to skip the red phase.

### Phase 0: Freeze the reviewed contract and repair partial-wire mismatches

**Write failing tests first**

- Extend `backend/tests/test_obj_archive_door_embodied_authority.py` to demand
  the canonical `open` affordance/revision, a server-issued `settlement_id`,
  and commit-before-publication ordering.
- Keep
  `test_archive_door_settlement_is_ledger_correlated_and_receipt_pins_object_result`
  as a green regression floor: `ESMService.emit_object_state_result()` already
  accepts and forwards the server-owned `settlement_id`,
  `interaction_attempt_id`, and `grant_id`. Add a new initially failing
  canonical-ID/profile mismatch test; do not weaken the correlation assertion
  or drop those fields from the object result.
- Add `backend/tests/test_obj_archive_door_embodied_contract.py` for strict
  typed fields, no NodePath/raw-input/bone/world-truth fields, and the
  cross-boundary revision/affordance equality.
- Expand `backend/tests/test_obj_archive_door_embodied_godot_static.py` to
  reject a generic `InteractiveObject` replacement and to require applied-only
  leaf/blocker/occlusion mutation. Static tests remain wiring checks only.
- Extend the legacy semantic-door checks in `backend/tests/test_ws_protocol.py`
  and `verify_embodied_affordance_registry.py` so their isolated
  `open_close` fixture remains a semantic regression floor but cannot be
  reported as, or routed through, this physical `MainDemo` attempt. Do not
  re-enable a direct live `obj_archive_door/open` world mutation to keep an old
  semantic assertion green.

**Modify**

- `scripts/interaction/ArchiveDoorEmbodiedAffordanceBridge.gd`
- `scenes/phase0/ArchiveDoorPhysical.tscn`
- `scripts/object/ArchiveDoorPhysical.gd`
- `scripts/object/ArchiveDoorPhysicalPresentation.gd`
- `backend/app/services/default_scene_archive_door_embodied_service.py`
- `backend/app/services/esm_service.py`
- `backend/app/models/embodied_interaction.py`
- `backend/app/models/world_result.py`

**Work**

- Make the bridge and backend share the canonical IDs in section 3.2.
- Add typed, server-owned `settlement_id`, `attempt_id`, `grant_id`, pinned and
  live revision fields to the appropriate settlement/object-result projection;
  preserve backwards-compatible defaults for unrelated result producers.
- Keep `ArchiveDoorPhysicalPresentation.apply_result()` idempotent on the same
  settlement ID and immutable for all non-applied/rejected payloads.

**Exit**: no backend/Godot identifier translation, and an applied open result
is the only input able to change the presentation snapshot.

### Phase 1: Repair the existing host around the only motor owner

**Write failing tests first**

- Make `backend/tests/test_obj_archive_door_embodied_local_static.py` fail for
  a missing host, direct transform writes, another `move_and_slide()`, missing
  atom registration, and missing terminal cleanup.
- Add `backend/tests/test_obj_archive_door_embodied_host_contract.py` to prove
  that actual measured stance/facing errors gate phase advancement; a sequence
  trace without measured movement must fail.
- Extend `backend/tests/test_embodied_action_controller_static.py` and
  `backend/tests/test_embodied_action_playback_static.py` for the non-blocking
  lifecycle and preservation of `run_attempt()` probe compatibility.

**Modify**

- `scripts/interaction/ArchiveDoorEmbodiedActionHost.gd`
- `scripts/phase0/MainDemoController.gd`
- `scripts/character/CharacterReplica.gd`
- `scripts/verification/ObjArchiveDoorPhysicalEmbodimentProbe.gd`
- `scripts/verification/verify_obj_archive_door_physical_embodiment.py`

**Conditional repair only after a failing focused test identifies it**

- `scenes/phase0/CharacterBase.tscn` for an explicit host NodePath or modifier
  binding that cannot be supplied by the existing host setup.
- `scripts/player/Phase0PlayerBridge.gd`, `scripts/player/PlayerShell.gd`, or
  `scripts/character/CharacterMotor.gd` only for a demonstrated forced-input
  owner conflict. The existing forced move/facing path is the default to reuse.
- `scripts/interaction/EmbodiedActionController.gd` or
  `scripts/interaction/EmbodiedActionPlaybackAdapter.gd` only for a defect in
  the existing non-blocking/recovery contract. Preserve `run_attempt()`.

`DefaultSceneActionAtomCatalog.gd` and
`CharacterEmbodimentAssetRegistry.gd` are explicit non-modification defaults:
all five required atoms already exist, and this slice must not make a second
catalog or registry.

**Work**

- Preserve the existing host under `CharacterBase`; validate its explicit
  NodePaths to the player bridge, replica, door bridge, controller, adapter,
  and presentation snapshot source. Do not move it under the door or add a
  second host.
- Preserve the existing narrow `CharacterReplica` forwarding surface for
  reviewed atom playback/recovery and passive hand measurement. Extend it only
  for a capability-gated reach request/result; do not expose a motor, physics
  body, private role scene, or authority transport API.
- Drive only `set_forced_player_motion`, `set_forced_facing_yaw`, and their
  clears. Maintain an active-attempt guard so mouse/forced yaw cannot have two
  writers. Before every direct single-lane approach step, use the existing
  physics query/body test to reject an obstructed stance line; a
  `NavigationAgent3D` is not introduced until MainDemo actually owns a reviewed
  navigation map. This is the bounded no-obstacle path implementation for this
  one fixture, not a generic navigation system. Assert cleanup in
  `defer`-equivalent terminal paths.
- Let `MainDemoController` correlate a submitted door request with the host
  and route its matching preflight constraint to `recover_without_grant()`.
- Emit ordered phase evidence through `LocalPresentationBus`; the host does
  not manufacture a settlement or write the physical scene. Subscribe to the
  matching settlement/result only to finish correlation, resync on rejection,
  and report the post-apply presentation observation.
- For the physical success scenario, remove direct player position/orientation
  writes after scene readiness. Use an authored or launch-time start marker,
  send normal structured move input to establish the server position, and let
  the host's forced-intent path move and align the real player. Failure fixtures
  may choose deterministic backend state, but they may not turn a direct local
  transform write into approach or collision evidence.

**Exit**: a runtime trace can identify `motor_owner=PlayerShell`, nonzero
approach movement, stance/facing errors, selected atoms, phase order, and
`local_ownership_restored=true` on success/failure.

### Phase 2: Implement measured hand alignment and safe contact

**Write failing tests first**

- Add `backend/tests/test_obj_archive_door_embodied_ik_contract.py` for missing
  right-arm chain, unavailable built-in solver, non-contact target, invalid
  tolerance, PlayerShell transform mutation, and raw bone payload exclusion.
- Add `backend/tests/test_obj_archive_door_embodied_failure_paths.py` cases for
  `ik_chain_unavailable` and `ik_alignment_tolerance_exceeded`: no contact
  observation, recovery atom played, forced controls cleared, and unchanged
  door snapshot.
- Add a runtime probe assertion that the start position differs from the stance,
  that the hand error is measured at contact, and that `raise_hand`/
  `tap_contact` occurred before a terminal observation.

**Conditionally add**

- `scripts/character/ArchiveDoorReachModifier.gd` only after the built-in
  `SkeletonIK3D` capability probe records that the solver is absent or unusable
  for the shipped rig *and* a failing capability test shows the existing
  `KnightCombatModifier` chain cannot host the bounded reach.

**Modify**

- `scripts/character/KnightRoleSkin.gd`
- `scripts/character/CharacterReplica.gd`
- `scripts/interaction/ArchiveDoorEmbodiedActionHost.gd`
- `scripts/interaction/EmbodiedActionPlaybackAdapter.gd`
- `scenes/phase0/CharacterBase.tscn` if an explicit local modifier node is
  necessary.

**Work**

- Probe `SkeletonIK3D` first when the runtime exposes it; select it only after
  the shipped rig passes. Use the narrow modifier only as the documented
  fallback.
- Bind only the bridge's `ContactAnchor`; no node discovery by mesh/name and no
  server-side NodePath.
- Extend the typed `ContactObservation` only with an optional reviewed
  `observation_rule_ref` and bounded non-negative
  `hand_alignment_error_m`; enforce both fields for this door. Build the
  contact outcome with `collider:char_c:hand_r`,
  `collider:obj_archive_door:body`, that canonical observation-rule reference,
  and the scalar hand error. Set `object_observation=null`: the door cannot
  honestly observe `open` before authority commits it. It never includes a
  bone transform or a world-state claim.

**Exit**: a real MainDemo contact measurement is <= `0.08m`, or the attempt
fails closed and recovers. There is no successful unmeasured contact route.

### Phase 3: Complete the authority preflight and one-time settlement route

**Write failing tests first**

- Preserve the existing green ledger/receipt regression in
  `test_obj_archive_door_embodied_authority.py`: it proves that the receipt
  and applied `ObjectStateResult` carry the same server-issued
  `settlement_id` plus the originating `interaction_attempt_id` and `grant_id`.
  New preflight/bootstrap, failure-correlation, and hostile-receipt tests must
  fail before their corresponding behaviour is added; no later work may remove
  or weaken this positive correlation assertion.
- Extend `test_obj_archive_door_embodied_authority.py` with valid
  `bind -> preflight -> phases -> measured contact -> one ESM closed/open commit -> one
  applied object result`, plus commit-before-publish assertions.
- Extend `backend/tests/test_obj_archive_door_embodied_websocket.py` for the
  live route's exact envelope order, wrong connection, old epoch, expired/
  reused credential, missing binding, and no credential leakage.
- Add `backend/tests/test_obj_archive_door_embodied_replay.py` for duplicate
  request and duplicate terminal outcome, different-digest duplicate rejection,
  one grant consume, one settlement, continuous server sequence, and stable IDs.
- Extend `test_archive_door_settlement_is_ledger_correlated_and_receipt_pins_object_result`
  with malformed, wrong-connection, and wrong-settlement
  `embodied_presentation_observed` messages. Each must produce a typed reject,
  append no `presentation` ledger event, and leave both the ESM state and
  applied-result count unchanged.
- Add a phase-route regression that first satisfies ingress source-sequence
  validation but deliberately fails the door ledger append. It must return
  `evidence_ledger_rejected`, issue no terminal settlement, and leave the door
  presentation snapshot unchanged; ingress validation alone is not sufficient
  evidence for a legal local phase.
- Extend `backend/tests/test_embodied_controller_auth_ingress.py` with the
  regression that a door terminal outcome cannot first enter the generic
  `EmbodiedExecutionIngress.handle_local_outcome()` and then be consumed again.
- Add stale binding and stale ESM-state tests that assert a typed rejection,
  `mutation_count=0`, and no applied object result.

**Add**

- `backend/app/services/trusted_local_embodied_controller_launcher.py`
- `scripts/launch_trusted_local_obj_archive_door.py`

**Modify**

- `backend/app/services/default_scene_archive_door_embodied_service.py`
- `backend/app/services/embodied_controller_auth_service.py`
- `backend/app/services/embodied_execution_ingress.py`
- `backend/app/services/embodied_evidence_ledger.py`
- `backend/app/main.py`
- `backend/app/models/embodied_interaction.py`
- `backend/app/models/world_result.py`
- `scripts/autoload/BackendBridge.gd`
- `scripts/autoload/LocalPresentationBus.gd`

**Work**

- Reuse the trusted-local launcher pattern, but define an embodied-controller
  profile/issuer/handoff with only actor ID, controller instance, TTL, and
  loopback constraints. Strip bootstrap secrets from the Godot child
  environment after deriving the one enrollment. The client cannot request or
  choose a credential.
- Construct `EmbodiedEvidenceLedger` before injecting it into the door service
  in `main.reset_runtime_state()`; avoid a late global lookup or a second
  ledger. Make door preflight the sole owner of request replay, policy/range/state
  checks, target attempt occupancy, and issuance of one `EmbodiedActionRequest`
  plus one connection-bound grant.
- Make `DefaultSceneArchiveDoorEmbodiedService.handle_local_outcome()` the
  sole door terminal coordinator. It may reuse a non-consuming sequence/schema
  helper, but `consume_grant_for_outcome()` must run exactly once for a new
  payload. Exact duplicate digest/nonce returns the stored receipt/object
  result; a changed payload fails closed.
- Route a door phase through the existing non-consuming sequence validator,
  then append it to this door attempt's ledger; both steps are required and a
  ledger-order failure returns `evidence_ledger_rejected`. Do not let the
  generic terminal ingress consume a door grant. Keep `main.py`'s dedicated
  `embodied_presentation_observed` envelope route first-class: after a
  presentation applies an object result, it accepts only a bounded
  `{attempt_id, settlement_id, snapshot_digest}` acknowledgement from the
  bound connection, appends ledger event kind `presentation`, and rejects a
  malformed, wrong-connection, or nonmatching-settlement receipt without any
  world mutation or ledger presentation event.
- On a valid contact, recheck the live binding/policy/door state and the
  canonical collider/rule/error fields, append the authoritative settlement
  evidence, commit ESM `closed -> open`, create one
  server-issued `settlement_id`, then emit the receipt and applied object
  result. Do not publish the object result, occupancy projection, or visual
  result before the ESM commit succeeds.
- On every post-grant terminal outcome, mint one `settlement_id` before writing
  its final ledger receipt. An applied settlement carries that ID into the
  object result; a rejected/not-committed settlement exposes it only in the
  safe receipt and never in an applied object result. Map stale binding to
  `binding_revision_mismatch`; map a changed door state to `door_state_stale`.

**Exit**: all route mutations are backend-owned; duplicate traffic cannot
cause a second ESM commit, ledger settlement, or Godot presentation command.

### Phase 4: Make all failure paths recover and remain physically immutable

Each row requires a red unit/integration test, a host/runtime test, and the
same before/after snapshot assertion:

```text
{ esm_state, door_leaf_transform, closed_blocker_enabled,
  passage_occlusion_state, presentation_state, applied_settlement_id }
```

| Required scenario | Authoritative producer and structured result | Local recovery | Immutable-world proof |
| --- | --- | --- | --- |
| Distance insufficient | Backend preflight/ESM range returns `ConstraintStateResult {constraint_type=distance_constraint, constraint_code=out_of_range, settlement_status=rejected}`; no attempt/grant/settlement exists. | Correlated `MainDemoController -> host.recover_without_grant()`: `recover_balance`, clear forced movement/yaw/IK/lease. | ESM remains closed, `mutation_count=0`, no applied result, snapshot equality, closed screenshot. |
| Binding revision, scene/policy revision, or door-state stale | Door coordinator rechecks pinned versus live binding/policy/scene/state after local contact and returns `EmbodiedSettlementResult {settlement_id, outcome=rejected, error_code=binding_revision_mismatch|revision_conflict|door_state_stale}`. | Host consumes the rejected settlement, clears local ownership, performs recovery, requests safe resync. | No ESM write, no applied object result, no leaf/blocker/occlusion change, snapshot equality. |
| Stance/occupancy conflict | Canonical physical case: host detects reviewed stance overlap during `reserve_stance`, emits `failed_precondition/stance_occupied`, and the coordinator records one `not_committed` settlement ID. Preflight's competing-attempt guard remains a separate backend regression case. | Release provisional lease, clear forced input/yaw and IK, play recovery; never enter contact. | No ESM write, contact observation absent, no applied result, snapshot equality, closed screenshot. |

`observation_rule_failed` (wrong collider/rule/error or a pre-settlement world
claim), `failed_alignment`, cancellation, missing action asset, wrong
connection, and `close` are additional fail-closed regressions. Each produces
local recovery and an unchanged door snapshot; none substitutes for any of the
three required scenarios.

### Phase 5: Focused real-MainDemo verifier, artifacts, and aggregation

**Write failing tests first**

- Add `scripts/verification/tests/test_verify_obj_archive_door_physical_embodiment.py`
  to reject a verifier that launches any scene other than `MainDemo`, does not
  start a backend/live WebSocket bridge, lacks a screenshot, lacks all four
  scenarios, or accepts semantic/chair probe artifacts.
- Extend that verifier test with the current live-launch regression: no bare
  `_finish(...)` call is allowed in `_run_probe()`, `controller_bound` must
  check `state == bound`, and the success path must not directly assign player
  position or body yaw. This test is red against the current candidate probe
  and must become green before another watchdog run is accepted.
- Add profile registry tests requiring the focused profile before it appears in
  `embodied-interaction-foundation-all`.
- Add replay validation tests that reject presentation before commit, a missing
  correlation field, a second settlement, a changed duplicate digest, and an
  artifact whose settlement ID differs from the backend record.

**Add**

- `scripts/verification/ObjArchiveDoorPhysicalEmbodimentProbe.gd`
- `scenes/phase0/ObjArchiveDoorPhysicalEmbodimentProbe.tscn` only as a launch
  harness wrapper around `MainDemo`; it may not replace the MainDemo scene.
- `scripts/verification/verify_obj_archive_door_physical_embodiment.py`
- `.harness/profiles/obj-archive-door-physical-embodiment.json`

**Modify**

- `scripts/verification/verify_embodied_interaction_foundation_all.py`
- `.harness/profiles/embodied-interaction-foundation-all.json`
- `docs/INDEX.md`
- `docs/harness.md`
- `scripts/verification/tests/test_harness_registry.py` as required by the
  existing profile registry discipline.

**Work**

- Run success, distance, binding/state stale, and stance conflict through the
  normal MainDemo `BackendBridge` path. The probe may choose deterministic
  launch-time/revision/occupancy fixtures, but it may only observe results;
  it cannot construct an applied result, set the leaf transform, teleport or
  rotate the player to manufacture the success path, or bypass the
  host/authority route.
- Make the probe's completion path await `_finish()` before return, write the
  `controller_bound` fact from the authoritative bind state, and always emit
  either a complete scenario artifact or a typed probe failure. These are
  verifier reliability repairs, not evidence of the door action itself.
- Capture a screenshot after the applied open and after each failed recovery.
  In a headless renderer, use a stable viewport capture with a nonzero file
  size and scene-visible label/door state; do not substitute a JSON-only claim.
- Add the focused profile to the aggregate only after it independently passes.

**Exit**: the focused profile produces fresh runtime, backend settlement,
replay, and screenshot artifacts for all four acceptance cases.

## 7. Evidence And Replay Contract

Generated evidence lives only under `.harness/verification/` and its run-ID
archive. Source files and profile manifests are not evidence.

| Artifact | Required fields / pass condition |
| --- | --- |
| `obj-archive-door-physical-embodiment-runtime.json` | `scene=MainDemo`, run ID, request ID, binding ID/epoch without credential, player start/stance positions, actual movement delta, facing error, IK runtime kind/chain/error, ordered phases/atoms, `motor_owner=PlayerShell`, attempt/grant/settlement IDs (explicit `null` for no-grant preflight rejection), received settlement/result, recovery flag, post-apply observation digest, and pre/post snapshot. |
| `obj-archive-door-physical-embodiment-backend-settlement-trace.json` | Redaction assertion, request/preflight decision, pinned/live revisions, one-time consume/idempotency data, ESM previous/current state, `commit_count`, `mutation_count`, settlement ID, object result ID, and ledger sequences. Success has one commit; failures have zero. |
| `obj-archive-door-physical-embodiment-replay-trace.json` | Per scenario: records sorted by `server_ledger_sequence`, request/attempt/grant/settlement IDs, source-sequence outcomes, receipt/result references, verifier-created evidence artifact names, and the matching post-apply presentation event. The range-rejected row records `attempt_id=grant_id=settlement_id=null` and joins by request/correlation ID. |
| `obj-archive-door-physical-embodiment-success.png` | Door visibly open after applied result; closed passage blocker released; IDs join to runtime/backend records. |
| `obj-archive-door-physical-embodiment-distance-failure.png` | Door visibly closed with recovery result; no grant/settlement mutation. |
| `obj-archive-door-physical-embodiment-revision-failure.png` | Door closed after rejected stale settlement; no applied presentation. |
| `obj-archive-door-physical-embodiment-stance-failure.png` | Door closed after `stance_occupied` recovery; no contact/commit. |
| `obj-archive-door-physical-embodiment-report.json` and `.md` | Each acceptance row marked proved only when all its referenced artifacts are fresh/readable and cross-correlated. |

`EmbodiedEvidenceLedger.server_ledger_sequence` is the only replay-order
source. For granted attempts, `attempt_id` is the join root and
`settlement_id` joins the receipt, applied result, Godot post-apply observation,
and verifier-created artifact. A preflight-rejected distance case joins by
request/correlation ID because no grant or settlement exists. A Godot artifact
is an auditable projection, never an authority source. The replay verifier
must assert:

1. `request_authorized -> registry_binding -> legal local_phase* -> one
   terminal_local_observation -> one settlement -> presentation` in server
   sequence order.
2. The successful settlement ID occurs exactly once; its presentation event is
   later than its committed settlement event and has the same ID.
3. Each rejected attempt has no applied presentation. Its evidence shows local
   recovery and unchanged snapshot.
4. Same digest/nonce replays the original receipt/result without a second ESM
   mutation, ledger settlement, or physical transition; a changed duplicate
   digest is rejected.
5. The public-safe projection excludes enrollment credentials, raw bones,
   NodePaths, raw input, VLA prompt/context, and private data.

The existing ledger is process-local. This plan claims repeatable, correlated
replay within a verification run; it does not claim durable restart recovery.

## 8. Expected File Inventory

### New files

The following are intended artifact names. Reconcile the currently untracked
candidate files against their failing tests first; do not overwrite a
compatible existing candidate merely because this plan lists it.

- `scripts/character/ArchiveDoorReachModifier.gd` only if the built-in
  `SkeletonIK3D` solver is absent or fails the documented capability probe
- `backend/app/services/trusted_local_embodied_controller_launcher.py`
- `scripts/launch_trusted_local_obj_archive_door.py`
- `backend/tests/test_obj_archive_door_embodied_contract.py`
- `backend/tests/test_obj_archive_door_embodied_host_contract.py`
- `backend/tests/test_obj_archive_door_embodied_ik_contract.py`
- `backend/tests/test_obj_archive_door_embodied_failure_paths.py`
- `backend/tests/test_obj_archive_door_embodied_replay.py`
- `scripts/verification/ObjArchiveDoorPhysicalEmbodimentProbe.gd`
- `scenes/phase0/ObjArchiveDoorPhysicalEmbodimentProbe.tscn`
- `scripts/verification/verify_obj_archive_door_physical_embodiment.py`
- `scripts/verification/tests/test_verify_obj_archive_door_physical_embodiment.py`
- `.harness/profiles/obj-archive-door-physical-embodiment.json`

### Existing files expected to change

- Godot: `ArchiveDoorEmbodiedActionHost.gd`,
  `ArchiveDoorEmbodiedAffordanceBridge.gd`,
  `ArchiveDoorPhysicalPresentation.gd`, `CharacterReplica.gd`,
  `KnightRoleSkin.gd`, `MainDemoController.gd`, `BackendBridge.gd`, and
  `LocalPresentationBus.gd` for bootstrap/receipt/presentation-observation
  correlation.
- Godot only if proved necessary by a named failing test: `CharacterBase.tscn`
  (existing host/modifier binding), `ArchiveDoorPhysical.tscn` (reviewed anchor
  correction), `MainDemo.tscn` (explicit integration ref), and the existing
  controller/playback/forced-movement files named in Phase 1. Do not edit them
  merely to recreate capabilities already present.
- Backend: `main.py`, `embodied_controller_auth_service.py`,
  `embodied_execution_ingress.py`, `embodied_evidence_ledger.py`,
  `default_scene_archive_door_embodied_service.py`, `esm_service.py`, strict
  interaction/world models, and the focused door/auth/ingress/replay test
  files.
- Verification/docs: aggregate verifier/profile, profile registry tests,
  `docs/INDEX.md`, and `docs/harness.md`.

Do not modify `docs/7月分析/2026-08-03-活跃plan与spec进度分析.md` or
`scripts/verification/check_godot_project.py` while executing this plan.

## 9. Exact Verification Order

Run the focused unit/integration tests after each phase and inspect their
output. After implementation is complete, run this exact order from repository
root. Replace no command with a semantic door, chair, or static-only probe.

```powershell
python -m pytest -q backend/tests/test_obj_archive_door_embodied_authority.py backend/tests/test_obj_archive_door_embodied_websocket.py backend/tests/test_obj_archive_door_embodied_contract.py backend/tests/test_obj_archive_door_embodied_host_contract.py backend/tests/test_obj_archive_door_embodied_ik_contract.py backend/tests/test_obj_archive_door_embodied_failure_paths.py backend/tests/test_obj_archive_door_embodied_replay.py backend/tests/test_obj_archive_door_embodied_godot_static.py backend/tests/test_obj_archive_door_embodied_local_static.py backend/tests/test_trusted_local_embodied_controller_launcher.py backend/tests/test_embodied_controller_auth_ingress.py backend/tests/test_embodied_authority_settlement.py backend/tests/test_embodied_evidence_ledger.py backend/tests/test_embodied_action_controller_static.py backend/tests/test_embodied_action_playback_static.py backend/tests/test_default_scene_action_atom_catalog_static.py backend/tests/test_ws_protocol.py backend/tests/test_esm_service.py scripts/verification/tests/test_verify_obj_archive_door_physical_embodiment.py scripts/verification/tests/test_harness_registry.py

python scripts/verification/harness.py --profile obj-archive-door-physical-embodiment --godot-exe D:\godot\Godot_v4.6.3-stable_win64_console.exe

python scripts/verification/harness.py --profile embodied-interaction-foundation-all

python scripts/verification/harness.py --profile mainline-unified-runtime

python scripts/verification/harness.py --profile docs

python scripts/verification/harness.py --profile all
```

The last command is conditional on every predecessor passing and all required
fresh physical evidence being present. It is intentionally last because the
full profile stops at its first failure and cannot replace diagnosis of the
narrow door contract.

## 10. Acceptance Matrix

| Case | Backend settlement acceptance | Godot physical acceptance | Required evidence |
| --- | --- | --- | --- |
| Valid open | One bound grant, one valid terminal observation, one ESM `closed -> open` commit, one `settlement_id`, one applied object result. | Measured local approach and alignment, all five atoms in the expected phase windows, hand error <= `0.08m`, then leaf opens/blocker releases/occlusion opens. | Runtime JSON, backend trace, replay trace, success PNG, focused pytest/profile. |
| Duplicate repeat | Same request/outcome returns original grant/receipt/result; exactly one commit/ledger settlement. | No second transform/collision transition; same applied settlement ID is idempotent. | Stable joined IDs and one presentation event. |
| Distance insufficient | `out_of_range`, no grant, zero mutation. | Door stays closed; host records correlated local recovery with controls cleared. | Distance JSON branch, snapshot equality, closed PNG. |
| Binding revision mismatch or door state stale | Typed rejected settlement, no commit/applied result. | Contact may have happened locally but cannot alter door; host recovers/resyncs. | Backend/replay trace, snapshot equality, closed PNG. |
| Stance/occupancy conflict | `stance_occupied` / `not_committed`, no commit. | No contact; lease/controls/IK cleared and recovery atom completes. | Local trace, settlement trace, snapshot equality, closed PNG. |
| IK unavailable or tolerance miss | No admissible contact/settlement effect. | `failed_alignment`, no contact observation, recovery and unchanged snapshot. | Capability probe and failure test. |

## 11. Rollback Points And Risks

| Rollback point | Smallest rollback | Guardrail |
| --- | --- | --- |
| Contract/revision reconciliation | Disable the door physical route before grants issue. | Do not fall back to the generic semantic `open` route. |
| Scene presentation | Leave `ArchiveDoorPhysical` unavailable/fail-closed. | A visible generic door state is not a substitute for hinge/blocker proof. |
| Host/motor/IK | Remove the narrow host/modifier binding and return a typed unavailable/recovery result. | Never restore direct transform writes or a second motor owner. |
| Authority coordinator | Disable `obj_archive_door/open` preflight until single consume/idempotency is correct. | Do not publish object results before ESM commit or re-enable direct mutation. |
| Profile aggregation | Keep the focused profile standalone until it is green. | Do not mark it optional or let aggregate success conceal a door failure. |

Primary risks are an unsupported shipped arm chain, competition between human
input and forced control, a target/revision changing after a grant, local
animation appearing successful before settlement, and artifact fabrication.
The controls are capability-gated failure, one active attempt plus terminal
cleanup, live revision/state recheck, applied-result-only presentation, and a
verifier that requires the real MainDemo/backend bridge plus screenshots and
server-ledger joins.

## 12. Human Confirmation Before Execution

A reviewed reachable `ContactAnchor` and a synchronized new binding revision
are required before the success path may continue. The required review must
pin the replacement local anchor, approach stance, contact tolerance, and
binding revision across the scene affordance record, backend policy, Godot
bridge, focused fixtures, and replay expectations. It must not be inferred
from the measured hand position alone. Until that review is supplied, the route
remains fail-closed and reports the physical geometry blocker; it must not
degrade to a semantic door probe or claim motion-warping/IK without measured
evidence.
