# Unified Character Action Foundation and INF Tag Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver one import-ready, multi-action character substrate in which a player or CharacterAgent can drive qualified external characters locally, while ESM/Gameplay retains authority over every world consequence.

**Architecture:** Every human, agent, debug, and connected source produces typed proposals at the `CharacterControllerPort`. `ActorActionArbiter` admits independent `ActionInstance`s and renewable movement/facing leases by canonical resource claims, then emits exactly one `CharacterIntentFrame` per fixed physics tick. The presentation adapter realizes only registered asset profiles; `MotionContributionComposer` turns admitted movement, root motion, impulses, and corrections into one `PhysicsMotionCommand`; `CharacterMotor` is the only code allowed to move the `CharacterBody3D`. Contact is provisional evidence until ESM/Gameplay or a registered Composite authority returns an idempotent `AuthorityResult`.

**Tech Stack:** Godot 4.6, GDScript, `CharacterBody3D`, AnimationPlayer/AnimationTree, external glTF 2.0 binary (`.glb`) packages, Python backend, WebSocket protocol, pytest, and the repository Harness.

**Spec:** `docs/superpowers/specs/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-design.md`

Runtime packages use the single path convention `assets/active/<package_id>/`.
`assets/characters/...` is reserved for authoring guidance, manifests,
qualification reports, or provenance and is never a runtime package path.

**Child specifications implemented by this plan:**

- `docs/superpowers/specs/2026-09-14-character-physics-motion-and-contact-subspec.md`
- `docs/superpowers/specs/2026-09-14-character-esm-action-attempt-settlement-subspec.md`
- `docs/superpowers/specs/2026-09-14-character-connected-action-and-physical-replication-subspec.md`
- `docs/superpowers/specs/2026-09-14-character-animation-asset-qualification-and-concurrent-realization-subspec.md`

## Plan Authority And Delivery Order

This is the **only implementation order** for the unified action foundation.
The five 2026-09-14 topic plans remain useful task-level research and test
notes, but they do not define parallel runtime designs or alternate sequencing.
An executor must complete each task's completion gate before using the next
task as a dependency. Fixture authoring may happen off the critical path, but
no runtime wiring or milestone claim is valid before its listed predecessor
gate passes.

```text
baseline -> shared contracts -> arbitration -> Motor command -> contact recovery
         -> asset qualification -> asset staging -> presentation adapter
         -> minimum weapon binding/profile
         -> Agent/INF bridge -> ESM/Gameplay/Composite settlement -> Mode B transport
         -> debug tools -> replay proof -> two-character runtime -> truth closure
```

## File Map

| Area | Files | Responsibility |
| --- | --- | --- |
| Input and state | `scripts/character/CharacterControllerPort.gd`, `CharacterRuntimeState.gd`, `CharacterTagContract.gd` | Normalize ingress, store projections, reject unowned writes. |
| Arbitration | `ActorActionArbiter.gd`, `ResourceClaimScheduler.gd`, `MotionContributionComposer.gd` | Lease/action lifecycle, conflict resolution, deterministic command composition. |
| Local body | `CharacterMotor.gd`, `CharacterReplica.gd`, `PlayerShell.gd` | One kinematic body path and no direct transform/velocity writers. |
| Imported presentation | `CharacterActionAssetDescriptor.gd`, `CharacterAssetQualification.gd`, `CharacterEmbodimentAssetRegistry.gd`, `CharacterEquipmentBindingProfile.gd`, `CharacterWeaponActionProfile.gd`, `RolePresentationAdapter.gd` | Qualification, equipment binding, bounded weapon profiles, registry, and rendering only. |
| Local action bridge | `scripts/interaction/EmbodiedActionController.gd`, `EmbodiedActionPlaybackAdapter.gd` | Marker observation and authority attempt creation. |
| Authority | `backend/app/models/embodied_interaction.py`, `backend/app/services/embodied_execution_ingress.py`, `backend/app/services/embodied_authority_settlement_service.py`, `backend/app/gameplay/action_window_runtime.py` | Idempotent ESM/Gameplay settlement and committed projection. |
| Connected Mode B | `backend/app/ws_protocol.py`, `scripts/autoload/BackendBridge.gd` | Semantic control/action transport, lease expiry, resync, and mirror separation. |
| Evidence | `scripts/verification/`, `backend/tests/`, `.harness/profiles/` | Focused contracts, real Godot probes, and final integration proof. |

## Global Constraints

- Godot owns local embodiment, input capture, local collision execution, and visible/audio presentation. It is not world-truth authority or a character cognition host.
- `CharacterMotor` is the only owner of `velocity`, gravity, collision, facing, root-motion application, world displacement, and `move_and_slide()`.
- `CharacterAgent`, INF, Siming, LimboAI, the debug panel, skins, and animation nodes may propose intent or presentation only. None may write transforms, velocities, damage, death, inventory, equipment, resources, or authoritative statuses.
- ESM/Gameplay or a registered Composite coordinator owns world consequences. A local marker or `PhysicsContactEvidence` is evidence, never a hit/damage/interaction settlement.
- The first milestone is local kinematic `CharacterBody3D` execution plus connected **Mode B semantic authority**. It does not claim raw-pose replication, rigid-body server authority, `netfox` rollback, or multiplayer physics.
- Imported assets are qualified rather than replaced. Deliver `.glb`, a canonical skeleton mapping, a stable rest pose, declared import scale/transforms/frame rate, attachment slots, typed timing sheets, and a machine-readable report.
- Phase 1 weapon scope is bounded: one qualified equipment slot/hand anchor,
  one standard melee action through `ActionAttempt`, and one semantic hitscan
  request/authority fixture. It does not include ammo, magazines, chambers,
  ballistic projectiles, dual wielding, parry/clash, or arbitrary prop weaponization.
- A full-body source clip must never be silently treated as a concurrent upper-body clip. Runtime code must not delete tracks, infer bone/physics claims, or invent root-motion behavior.
- `@export var atomic_sequence: Array[StringName] = []` is present on every descriptor and must remain empty in Phase 1. There is no atom lookup, expansion, or execution in this plan.
- Logical replay is deterministic by stable IDs and fixed-tick inputs. Exact cross-machine replay of dynamic Godot rigid bodies is explicitly out of scope.
- Preserve unrelated dirty-worktree changes, including removed legacy art and scene files. This plan migrates active references; it does not restore or delete user-owned assets.

## Reserved Extension Points (Not Phase 1 Implementations)

- New input and behavior sources continue to enter through the existing proposal and lease adapters.
- Advanced equipment (two-handed tools, mounts, tails, wings), facial animation,
  foot IK, look-at, recoil, motion matching, audio, and VFX remain
  presentation/resource extensions behind the same claims and
  `RolePresentationAdapter` boundary.
- Navigation/RVO may contribute a movement suggestion but never becomes a second Motor or physics writer.
- Future compound actions may use `atomic_sequence` only after a versioned atom registry defines timing, parallel groups, claims, and authority metadata; Phase 1 performs no expansion.
- Replay capture, multiplayer prediction, physical authority, and new status/capability/affordance IDs extend the existing typed registries and schemas rather than creating a second actor substrate.

## Fixed-Tick Contract

Every actor advances on the physics clock, not the render clock. The executor
must preserve this order for tick `T` and include `physics_tick` in each frame,
command, evidence record, request, and replay record:

1. Collect source proposals and active lease renewals for `T`.
2. Evaluate every state layer against the previous immutable runtime snapshot.
3. Resolve priority and occupancy into one `CharacterIntentFrame` for `T`.
4. Advance action executors and record marker observations with the same tick
   and action-instance identity; do not treat the presentation marker as
   contact confirmation.
5. Convert admitted movement, root, impulse, and bounded `runtime_correction` contributions into one collision-aware `PhysicsMotionCommand`.
6. Let `CharacterMotor` apply gravity, facing, velocity, sweep/collision, slide,
   and grounding; capture `PhysicsContactEvidence(T)`.
7. Join marker observations with same-tick evidence before emitting a
   contact-dependent `ActionAttempt(T)`, then publish `CharacterPresentationInput`
   to the imported RoleSkin/AnimationTree and keep rendering observational.
8. Deliver authority results/revisions after the completed tick; never retroactively rerun `T` or let a render frame become a second simulation clock.

---

### Task 1: Freeze the baseline and prohibit a second actor path

**Files:**
- Modify: `docs/character/character-action-foundation-current-state.md`
- Modify: `docs/character/character-runtime-design-drift-audit.md`
- Modify: `backend/tests/test_character_motor_ownership_audit.py`
- Modify: `backend/tests/test_character_actor_scene_convergence_static.py`
- Create: `scripts/verification/verify_unified_character_action_foundation.py`

**Interfaces:**
- Consumes: the active `CharacterReplica`, `PlayerShell`, `CharacterMotor`, RoleSkin, and controller scripts.
- Produces: `baseline.json` with `legacy_writer`, `active_writer`, `asset_reference`, `scene_reference`, and `migration_owner` rows; `verify_unified_character_action_foundation.py --stage baseline`.

- [ ] Record every existing transform/velocity/`move_and_slide()` writer, actor scene, skin, asset binding, and backend embodiment route in the current-state ledger. Mark each as `retain`, `migrate`, or `retire_reference`; do not alter its user-owned asset yet.
- [ ] Write a failing ownership-audit case that scans active scripts and fails when a class other than `CharacterMotor` assigns `global_position`, `position`, `velocity`, or calls `move_and_slide()` on the actor body.

  ```python
  def test_only_character_motor_owns_body_motion():
      violations = find_actor_body_writers(ACTIVE_ACTOR_SCRIPTS)
      assert violations == []
  ```

- [ ] Add the minimal verifier stage that parses the ledger, asserts each active scene has exactly one `CharacterBody3D` control path, and emits its evidence file under `.harness/verification/`.
- [ ] Update the drift audit with an explicit before-state: existing `CharacterActionAssetDescriptor` has a reserved atomic field but no unified arbitration/Motor/authority contract; any legacy local action playback remains presentation-only until migrated.
- [ ] Run `python -m pytest backend/tests/test_character_motor_ownership_audit.py backend/tests/test_character_actor_scene_convergence_static.py -v`.
- [ ] Run `python scripts/verification/verify_unified_character_action_foundation.py --stage baseline`.

**Completion gate:** The repository has a reviewable migration ledger and a failing-on-regression guard for direct body writers. No runtime behavior changes in this task.

### Task 2: Establish namespaced tags, proposals, runtime state, and the frame boundary

**Files:**
- Create: `scripts/character/CharacterTagContract.gd`
- Create: `scripts/character/IntentProposal.gd`
- Create: `scripts/character/LayerControlProposal.gd`
- Create: `scripts/character/CharacterIntentFrame.gd`
- Modify: `scripts/character/CharacterControllerPort.gd`
- Modify: `scripts/character/CharacterRuntimeState.gd`
- Create: `backend/tests/test_character_intent_frame_contract_static.py`

**Interfaces:**
- `CharacterTagContract.normalize_ingress_tags(tags: Array[StringName]) -> Dictionary` returns `{accepted: Array[StringName], rejected: Array[StringName]}`.
- `IntentProposal.normalize(raw: Dictionary, source_id: StringName, control_mode: StringName) -> Dictionary` returns source, intent/context tags, move/facing, optional action, target, priority, causation, and correlation.
- `LayerControlProposal.from_intent(proposal: Dictionary) -> Dictionary` includes desired channels, add/remove projection tags, requested claims, cancellation policy, and root-motion policy.
- `CharacterIntentFrame.build(physics_tick: int, admitted: Array[Dictionary], queued: Array[Dictionary], rejected: Array[Dictionary]) -> Dictionary` is immutable after construction.
- `CharacterRuntimeState.apply_authority_result(result: Dictionary) -> void` changes only the committed projection.

- [ ] Write contract tests for the allowed namespaces: `goal`, `intent`, `evidence`, `capability`, `affordance`, `constraint`, `state`, `status`, `action`, `phase`, `occupy`, `event`, `authority`, `presentation`, and `expression`; verify unnamespaced values are rejected at ingress while a read-only compatibility adapter can read legacy demo fields.
- [ ] Include representative namespaced values such as `goal:protect_target`, `intent:move_to_affordance`, `evidence:target_visible`, `capability:skill_sword`, `affordance:door_open`, `constraint:stamina_low`, `state:locomotion_run`, `status:stunned`, `action:sword_slash`, `phase:contact`, `occupy:right_arm`, `event:contact_candidate`, `authority:committed`, `presentation:locomotion_run`, and `expression:focused`; reject bare values such as `run` or `damage` at the boundary. `authority:*` is accepted only from a committed ESM/Gameplay/Composite projection.
- [ ] Treat the namespace patterns themselves as canonical (`goal:*`, `intent:*`, `evidence:*`, `capability:*`, `affordance:*`, `constraint:*`, `state:*`, `status:*`, `action:*`, `phase:*`, `occupy:*`, `event:*`, `authority:*`, `presentation:*`, `expression:*`) and keep metadata such as confidence, provenance, causation, correlation, revision, privacy scope, and authority scope outside the tag string.
- [ ] Implement the tag validator and typed dictionaries. Keep provenance, confidence, causation, correlation, revision, and privacy as metadata fields, not tags.
- [ ] Change `CharacterControllerPort` to accept only normalized `IntentProposal` objects and return a `LayerControlProposal`; reject dictionaries containing damage, hit result, inventory mutation, status write, transform, or velocity fields.
- [ ] Make `CharacterRuntimeState` hold grounded/motion projection, active lease/action summaries, occupancy, pending attempts, capability/status projections, latest authority result, and presentation cues. It must not expose a mutable transform or action-settlement writer.
- [ ] Run `python -m pytest backend/tests/test_character_intent_frame_contract_static.py backend/tests/test_character_controller_port_static.py backend/tests/test_character_runtime_state_extraction_static.py -v`.

**Completion gate:** All actor ingress uses named tags and typed proposals; one immutable frame shape exists before arbitration or Motor work begins.

### Task 3: Implement leases, independent actions, canonical claims, and deterministic arbitration

**Files:**
- Create: `scripts/character/ContinuousControlLease.gd`
- Create: `scripts/character/ActionInstance.gd`
- Create: `scripts/character/ResourceClaimScheduler.gd`
- Create: `scripts/character/ActorActionArbiter.gd`
- Modify: `scripts/character/CharacterRuntimeState.gd`
- Create: `backend/tests/test_actor_action_arbiter_contract.py`

**Interfaces:**
- `ContinuousControlLease.create(source_id, lease_id, revision, expires_at_tick, world_motion, facing) -> Dictionary`.
- `ActionInstance.create(action_instance_id, descriptor_id, source_id, target_ref, requested_tick) -> Dictionary` with lifecycle `requested|admitted|queued|windup|contact|recovery|cancelled|expired|settled`.
- `ResourceClaimScheduler.decide(request: Dictionary, occupancy: Dictionary, tick: int) -> Dictionary` returns `accept_now|queue|reject`, claims, conflicting owner IDs, and reason.
- `ActorActionArbiter.resolve(physics_tick: int, leases: Array[Dictionary], actions: Array[Dictionary], runtime: Dictionary) -> Dictionary` returns one `CharacterIntentFrame`.

- [ ] Write tests for simultaneous walk plus a right-arm action, two claims on the same `right_arm`, a full-body action versus `world_motion`, expiry of a continuous lease, cancellation inside/outside its declared window, and deterministic ordering when priority ties.

  ```python
  def test_walk_and_right_arm_action_are_admitted_together():
      frame = resolve([walk_lease(), right_arm_swing()])
      assert frame["admitted_ids"] == ["lease:walk", "act:swing"]
      assert frame["rejected"] == []
  ```

- [ ] Define canonical visual and physical resource IDs, including `world_motion`, `facing`, `root_translation`, `pelvis`, `support_contact`, `upper_body`, `left_arm`, `right_arm`, `weapon_hit_volume:{weapon_id}`, `interaction_reach`, `target_occupancy:{target_id}`, and `physics_body`; document parent/child claim conflicts (a parent claim conflicts with all child claims, while a child claim does not implicitly release the parent) in code constants and the asset contract.
- [ ] Freeze the complete resource tree used by the specs: `full_body_pose` with `pelvis`, `upper_body/left_arm/left_hand`, `upper_body/right_arm/right_hand`, `left_leg`, and `right_leg`; plus `head`, `root_translation`, `world_motion`, `weapon_slot:{slot_id}`, `voice_channel`, and `ragdoll_body`. Record that visually disjoint actions can still conflict through shared physical claims.
- [ ] Implement renewable movement/facing as `ContinuousControlLease`, sustained/discrete behavior as `ActionInstance`, and admission as `accept_now`, `queue`, or `reject` with typed reasons. Priority order is `Status > Interaction > Combat > Locomotion`, but no priority may violate a physical claim conflict.
- [ ] Resolve all non-conflicting requests into the same frame. Resolve by physics tick, layer priority, source priority, stable `source_id`, then stable action/lease ID; persist the exact decisions in runtime state for replay. Apply status/death override, preemption, cancellation-window, and claim-release rules deterministically.
- [ ] Run `python -m pytest backend/tests/test_actor_action_arbiter_contract.py backend/tests/test_character_action_lock_rules.py backend/tests/test_character_control_rules_static.py -v`.

**Completion gate:** Multiple actions may coexist exactly when their declared claims and locomotion relation allow it; no code retains a global one-action-only lock.

### Task 4: Compose one physics command and converge player/NPC movement on CharacterMotor

**Files:**
- Create: `scripts/character/MotionContribution.gd`
- Create: `scripts/character/PhysicsMotionCommand.gd`
- Create: `scripts/character/MotionContributionComposer.gd`
- Modify: `scripts/character/CharacterMotor.gd`
- Modify: `scripts/character/CharacterReplica.gd`
- Modify: `scripts/player/PlayerShell.gd`
- Modify: `scenes/phase0/CharacterReplica.tscn`
- Create: `backend/tests/test_character_motion_composition_contract.py`

**Interfaces:**
- `MotionContribution.normalize(raw: Dictionary) -> Dictionary` includes `actor_ref`, `physics_tick`, `contribution_kind` (`input|root_motion|impulse|runtime_correction|gravity`), `source_kind` (`locomotion|action|impulse|runtime_correction`), `source_id`, optional `action_instance_id`, desired velocity, root delta, impulse, facing delta, constraint refs, priority, and contribution revision.
- `MotionContributionComposer.compose(frame: Dictionary, profile: Dictionary, delta: float) -> Dictionary` returns `PhysicsMotionCommand` with actor/tick, desired velocity, root delta, impulse, `runtime_correction`, facing, vertical mode, collision policy, support requirements, profile ref, and source digest.
- `CharacterMotor.apply_physics_command(body: CharacterBody3D, command: Dictionary, delta: float) -> Dictionary` returns normalized actual motion state and provisional collision observations.

- [ ] Write failing tests for a stable ordering of movement, root delta, impulses, and corrections; verify a second command cannot write `root_translation` or `physics_body` after composition.
- [ ] Define support modes, root-motion envelopes, collision-response policy, evidence digest fields, speed/acceleration/impulse/vertical/correction caps, and reject direct-transform or unbounded-correction payloads at the contribution boundary.
- [ ] Enforce the normative order exactly: choose admitted continuous-control velocity; apply permitted action/root contribution; add impulses in stable `action_instance_id` order; apply `runtime_correction` only inside its envelope; clamp speed, acceleration, vertical launch, root delta, and correction; then pass the command to Motor for gravity, sweep/collision, slide, and grounding.
- [ ] Refactor `CharacterMotor` so it alone performs facing, velocity, gravity, collision and `move_and_slide()`. Convert its existing intent-frame compatibility route to an adapter that builds a `PhysicsMotionCommand`; do not retain a second implementation of body movement.
- [ ] Route player input through `HumanControllerAdapter -> CharacterControllerPort -> ActorActionArbiter -> CharacterIntentFrame -> MotionContributionComposer -> CharacterMotor`. Route `CharacterReplica` and agent/program control through the same path.
- [ ] Add an equivalence test/probe: the same normalized frame applied to a player shell and NPC replica yields the same commanded motion state before scene-specific presentation.
- [ ] Run `python -m pytest backend/tests/test_character_motion_composition_contract.py backend/tests/test_character_motor_static_contract.py backend/tests/test_character_locomotion_motor_ownership_guard_static.py -v`.
- [ ] Run `python scripts/verification/harness.py --profile godot-project` and retain the static/import result; runtime proof is deferred to Task 14.

**Completion gate:** There is one final physics command and one body-motion owner for player and NPC paths.

### Task 5: Add root-motion policy, collision-derived evidence, and action recovery

**Files:**
- Create: `scripts/character/PhysicsContactEvidence.gd`
- Modify: `scripts/character/CharacterMotor.gd`
- Modify: `scripts/character/MotionContributionComposer.gd`
- Modify: `scripts/interaction/EmbodiedActionController.gd`
- Create: `backend/tests/test_character_root_motion_and_contact_contract.py`

**Interfaces:**
- `CharacterMotor.collect_contact_evidence(command: Dictionary, action_instances: Array[Dictionary]) -> Array[Dictionary]` emits `PhysicsContactEvidence` with `evidence_id`, actor/tick/body revision, grounded/support ref, collider and hit-sensor refs, contact points and normals, motion-command digest, marker/action identity, and `local_only=true`.
- `MotionContributionComposer.apply_root_motion_policy(contribution: Dictionary, authority_state: StringName) -> Dictionary` supports `hold`, `bounded_continue`, and `reversible_continue`.
- `EmbodiedActionController.apply_authority_recovery(result: Dictionary) -> void` releases/retains claims based on the result's recovery directive.

- [ ] Write tests for a root-motion lunge blocked by a wall, slope/step clamping, support loss, an authority timeout under every root-motion policy, and a contact evidence record that does not mutate a backend or gameplay projection.
- [ ] Implement `hold` as zero contact-dependent root contribution while pending; `bounded_continue` as a profile-defined distance/time envelope; `reversible_continue` as a bounded local contribution plus the explicit reverse/correction on rejection. Reject a descriptor that requests a policy without its required safety envelope.
- [ ] Have Motor emit evidence only after collision/sensor observation; calculate a canonical digest over the evidence fields and attach the source marker/action instance. No presentation callback may synthesize confirmed contact.
- [ ] Cover every physics failure rule: wall/slope/step clamp or cancel, support-loss constraint on the next tick, repeated root-envelope overflow as a qualification diagnostic, stale `runtime_correction` ignored by projection revision with connected resync, contact without a valid marker as evidence-only, and marker without support as failed/uncertain evidence for authority revalidation.
- [ ] Keep locomotion as a renewable lease even when `drive_locomotion` or `replace_locomotion` is active: pause or limit it, then resume by revision after recovery; never silently discard the lease.
- [ ] Make `EmbodiedActionController` advance only local action phases, request attempts from typed markers, and apply `accepted`, `rejected`, `timed_out`, `cancelled`, or `target_invalid` recovery without settling damage/effects locally.
- [ ] Clear pending root deltas and authority-dependent contributions on action completion, cancellation, timeout, rejection, and actor reset; freeze unsafe contact-dependent motion while an attempt is `unknown` until the original idempotency query or resync resolves it.
- [ ] Run `python -m pytest backend/tests/test_character_root_motion_and_contact_contract.py backend/tests/test_action_window_godot_contract_static.py backend/tests/test_character_motor_ownership_audit.py -v`.

**Completion gate:** Root motion is collision-resolved through Motor, provisional contact is serializable evidence, and rejection cannot leave a claim/action permanently stuck.

### Task 6: Define canonical skeleton mapping and asset qualification

**Files:**
- Create: `scripts/character/CanonicalSkeletonProfile.gd`
- Create: `scripts/character/CharacterAssetQualification.gd`
- Modify: `scripts/qualification/CharacterAssetQualificationRunner.gd`
- Create: `assets/validation/schemas/character-action-asset-manifest.v1.json`
- Create: `assets/validation/schemas/character-qualification-report.v1.json`
- Modify: `assets/characters/README.md`
- Modify: `assets/characters/asset_manifests/README.md`
- Create: `backend/tests/test_character_asset_qualification_contract.py`
- Create: `scripts/verification/tests/test_character_asset_qualification_runtime.gd`

**Interfaces:**
- `CanonicalSkeletonProfile.validate_mapping(mapping: Dictionary, skeleton: Skeleton3D) -> Dictionary`.
- `CharacterAssetQualification.qualify(package_manifest: Dictionary) -> Dictionary` returns report status `qualified|qualified_with_fallback|rejected`.
- `CharacterAssetQualification.inspect_clip(clip: Animation, profile: Dictionary) -> Dictionary` returns bone impact, root/pelvis audit, markers, slot/mask compatibility, and root-motion audit.

- [ ] Write a manifest fixture containing a valid humanoid mapping, invalid rest pose, missing root bone, unmapped required locomotion tag, and a full-body clip incorrectly declared as upper-body concurrent. Assert only the valid package reaches `qualified`.
- [ ] Define the canonical bones, root, pelvis, spine, arm/leg chains, attachment slots, forward/up convention, rest-pose tolerance, unit/scale, and required Phase 1 locomotion tags: `idle`, `walk_forward`, `run_forward`, `jump_start`, `jump_loop` or `fall`, `jump_land`, `turn_left`, and `turn_right`.
- [ ] Make the qualification gate fail closed for missing `Skeleton3D`, invalid rest pose, missing required root bone, incompatible required slots, unmapped required action/locomotion tags, and any missing required clip; optional finger/facial bones may be reported separately without failing the body package.
- [ ] Add explicit mapping fixtures for the existing Bip001 knight and a Mixamo-style candidate skeleton. Add clip fixtures proving the knight/NPC source actions are full-body and cannot be silently admitted as upper-body concurrent.
- [ ] Support explicit external mappings and candidate lists for qualification diagnostics, but prohibit runtime name guessing; record unmapped optional finger/facial bones separately from required body failures.
- [ ] Record source frame rate and clip duration, distinguish meaningful lower-body curves from rest-pose tracks with a configured tolerance, and classify locomotion clips as `in_place` or `root_motion`.
- [ ] Inspect every source/derived clip at build time. Record actual canonical bone tracks, root/pelvis translation and rotation, lower-body rest-pose proof, seam/support compatibility, hand/weapon envelope, markers, cancel windows, and physical claims.
- [ ] Establish realization modes: `native_upper_body`, `derived_upper_body`, `full_body_exclusive`, `drive_locomotion`, and `additive`. Require an explicit fallback mode for every candidate that fails concurrent qualification.
- [ ] Encode locomotion compatibility as `coexist`, `drive_locomotion`, `replace_locomotion`, or `suspend`; enforce that `drive_locomotion`/`replace_locomotion` actions retain a paused or limited movement lease rather than creating a second movement writer.
- [ ] Keep roll, knockdown, death, climb, mount, and coordinated lunge actions full-body or locomotion-driving unless a dedicated concurrent profile passes the same qualification checks.
- [ ] Treat required root motion as a qualification failure when unavailable; allow optional root motion to fall back to Motor-driven displacement only when the descriptor declares that fallback.
- [ ] Run `python -m pytest backend/tests/test_character_asset_qualification_contract.py backend/tests/test_character_asset_contract_static.py -v`.
- [ ] Run the Godot qualification runner against the fixture package and save its machine-readable report under `.harness/verification/`; this is an importer/runtime check, not merely a static test.

**Completion gate:** A package enters the runtime only by an explicit canonical mapping and a reproducible report; source names/folders cannot grant concurrency.

### Task 7: Stage two external packages and preserve source provenance

**Files:**
- Modify: `assets/characters/asset_manifests/character_presentation_bindings.json`
- Modify: `assets/active/crusader_knight/README.md`
- Create: `assets/active/crusader_knight/manifest.json`
- Create: `assets/active/crusader_knight/docs/action-timing.json`
- Create: `assets/active/external_character_b/manifest.json`
- Create: `assets/active/external_character_b/docs/action-timing.json`
- Create: `assets/characters/qualification_reports/crusader_knight.json`
- Create: `assets/characters/qualification_reports/external_character_b.json`
- Modify: `docs/character/character-action-asset-interface.md`
- Create: `backend/tests/test_phase1_external_character_delivery_contract.py`

**Interfaces:**
- Each manifest exposes `package_id`, model digest/path, canonical mapping, rest-pose/import declaration, slots, locomotion map, action descriptors, realization profiles, fallback policy, and report path.
- Each action timing sheet has `action_id`, clip/variant, duration, windup/contact/recovery times, cancellation windows, typed marker IDs, marker kinds/evidence requirements, authority route, local-only flag, root-motion policy/envelope, declared claims, and recovery policy.

- [ ] Register the existing `assets/active/crusader_knight/crusader_knight.glb` as package A without moving or reimporting it. Deliver the second externally authored runtime-ready model under the fixed package path `assets/active/external_character_b/`; store both source digests and provenance in the manifests.
- [ ] Preserve the asset staging rules: active wrappers must be self-contained or co-located with their textures; legacy `assets/characters/shared/...` and removed art-pack paths are not runtime dependencies; archive sources remain untouched; candidate packages remain visibly `candidate` until headless qualification and visual review; any female-trio candidate is opt-in and cannot be promoted from a rejected visual result without a new report.
- [ ] Run the qualification matrix for the knight, NPC candidate, and one female-trio candidate as separate entries. The female-trio entry is opt-in evidence only; a rejected visual 0.4.0 result remains rejected and is never promoted by filename or folder.
- [ ] Record the external authoring contract in package docs: lower-case `snake_case` clip names, category directories such as `assets/characters/player/animations/locomotion/`, runtime-ready GLB preferred over FBX, metres, applied transforms, declared source rate, stable root/rest pose, canonical forward/up, and explicit root translation/rotation policy.
- [ ] Write timing sheets for locomotion and one external attack or interaction per character. Keep semantic action IDs independent from clip names and set `atomic_sequence` to `[]` for every entry.
- [ ] Require at least one accepted package to declare a held-item slot/hand
  anchor, `weapon_slot:<id>`, `weapon_hit_volume:<id>`, and a phase-marked
  semantic melee action. The hitscan profile is a route fixture and does not
  require projectile or ammunition assets in this task.
- [ ] Qualify an action that can coexist with Walk/Run using native or build-time-derived upper body, and a full-body fallback for an action that cannot. A full-body-only clip must be registered as exclusive, locomotion-driving, queue-until-compatible, or rejected.
- [ ] Fail the delivery test unless both packages have complete mappings/rest poses, the required locomotion suite, one phase-marked action, declared physical/root profiles, required slots, and a non-rejected report.
- [ ] Classify each package's accepted delivery level as `minimum_movement`, `full_body_action`, `concurrent_action`, or `presentation_extension`; do not claim Walk/Run coexistence for a package that only passes the movement or full-body level.
- [ ] Run `python -m pytest backend/tests/test_phase1_external_character_delivery_contract.py -v`.
- [ ] Run `godot --headless --path . --script res://scripts/qualification/CharacterAssetQualificationRunner.gd -- --package assets/active/crusader_knight` and repeat for `assets/active/external_character_b` using the repository's configured Godot executable; record both reports.

**Completion gate:** Two independently authored external packages are reproducibly acceptable or explicitly rejected with actionable reports; no source asset is silently modified.

### Task 8: Build the registry and presentation adapter without creating gameplay truth

**Files:**
- Modify: `scripts/character/CharacterActionAssetDescriptor.gd`
- Modify: `scripts/character/CharacterEmbodimentAssetRegistry.gd`
- Create: `scripts/character/CharacterWeaponActionProfile.gd`
- Modify: `scripts/character/CharacterEquipmentBindingProfile.gd`
- Create: `scripts/character/RolePresentationAdapter.gd`
- Modify: `scripts/character/GenericRoleSkin.gd`
- Modify: `scripts/character/KnightRoleSkin.gd`
- Modify: `scripts/interaction/EmbodiedActionPlaybackAdapter.gd`
- Create: `backend/tests/test_role_presentation_adapter_contract.py`

**Interfaces:**
- `CharacterActionAssetDescriptor.validate_phase1() -> Dictionary` rejects non-empty `atomic_sequence`, missing route/claim/profile fields, and authority-effect fields; it preserves `required_clips`, `optional_clips`, and optional `allowed_control_modes`.
- `CharacterEmbodimentAssetRegistry.resolve(package_id: StringName, action_id: StringName, claims: Array[StringName]) -> Dictionary` returns only qualified profile/fallback entries.
- `CharacterWeaponActionProfile.normalize(raw: Dictionary) -> Dictionary` returns
  semantic `melee|hitscan` metadata without world-truth fields.
- `CharacterEquipmentBindingProfile.resolve_slot(slot_id: StringName) -> Dictionary`
  returns a qualified attachment anchor and declared attachment mode.
- `RolePresentationAdapter.apply_input(input: Dictionary) -> Dictionary` consumes `CharacterPresentationInput`, selected profiles, and markers; it returns playback observations only.

- [ ] Write tests proving a rejected profile is unavailable, an incompatible full-body clip takes its declared fallback, and playback cannot set body transform, velocity, `ActionAttempt`, hit, damage, status, inventory, or ESM/Gameplay state.
- [ ] Expand the descriptor to include stable action ID/tag, required clips/slots, realization profile, required claims, locomotion relation, root-motion policy/envelope, marker/timing definitions, cancellation windows, physics profile reference, authority route reference, and `@export var atomic_sequence: Array[StringName] = []`.
- [ ] Add the minimum weapon slice: one qualified equipment slot/hand anchor,
  one `melee` action profile with `weapon_hit_volume:<id>`, and a semantic
  `hitscan` profile fixture. Reject damage, hit, ammo, projectile, and direct
  transform fields.
- [ ] Require `semantic_action_id` to remain independent of clip filenames; preserve source/derived clip provenance, canonical mask, qualification report, fallback rank/policy, and package digest for every registered profile.
- [ ] Preserve typed marker fields (`marker_id`, `time_seconds`, `marker_kind`, `emits_attempt`, `evidence_requirement`) and ensure time-based marker timing survives source-to-derived packaging.
- [ ] Retain the existing descriptor compatibility normalization only as an explicit migration adapter. It must reject `atomic_sequence != []` in Phase 1 and must not resolve the existing action-atom catalog.
- [ ] Make the registry read qualification reports and resolve profile/fallback from the arbiter's claims and locomotion relation. Make the RoleSkin/AnimationTree consume `CharacterPresentationInput`; it may sample root motion and emit marker observations, but never mutate the actor body.
- [ ] Forbid CharacterAgent, INF, Siming, and network payloads from selecting raw clip names; they request only semantic action IDs. Profile selection remains a local qualified-asset decision correlated with package/descriptor digest.
- [ ] Resolve weapon profiles by semantic action ID and claims; ensure both
  melee and hitscan use the same action lifecycle and never create a parallel
  WeaponLayer scheduler.
- [ ] Run `python -m pytest backend/tests/test_role_presentation_adapter_contract.py backend/tests/test_character_asset_registry_static.py backend/tests/test_character_presentation_asset_resolver_static.py -v`.

**Completion gate:** The asset registry and all skins are presentation consumers of qualified profiles, not hidden movement or authority controllers.

### Task 9: Bridge CharacterAgent, INF, and Siming to semantic intent

**Files:**
- Modify: `backend/app/character_agent/execution/l4_executor.py`
- Modify: `backend/app/character_agent/execution/l4_adapter.py`
- Modify: `backend/app/models/siming_character_bridge.py`
- Modify: `backend/app/services/siming_character_dispatch_adapter.py`
- Modify: `scripts/character/AgentControllerAdapter.gd`
- Modify: `scripts/character/CharacterRuntimeState.gd`
- Create: `backend/tests/test_character_agent_inf_intent_boundary.py`

**Interfaces:**
- Backend L4 output: `intent_proposal(actor_ref, source_id, intent_tags, context_tags, action_id?, target_ref?, move?, facing?, causation, correlation)`.
- `AgentControllerAdapter.build_intent_proposal(message: Dictionary) -> Dictionary` validates the exact Task 2 contract.
- `CharacterRuntimeState.apply_authority_result(result: Dictionary) -> void` accepts committed projections/recovery only.

- [ ] Write a test in which Agent goals/evidence/capabilities/affordances/constraints become the correct namespaced context tags, Siming emits only catalysts/presentation hints, and attempts to emit transforms, animation states, direct status changes, or damage are rejected.
- [ ] Map CharacterAgent L4 candidate behavior to semantic action/movement/facing proposals rather than local animation commands. Preserve source, confidence, provenance, privacy scope, authority scope, causation, correlation, and expected revision metadata as metadata fields.
- [ ] Map INF and Siming data to `goal:*`, `constraint:*`, `evidence:*`,
  allowed context tags, and presentation cues. Preserve `reason_codes` as
  metadata, allow consumption of committed authority projections, and never
  route INF or Siming as authority settlement services or generic writers.
- [ ] Update the Godot agent adapter to feed only `CharacterControllerPort`; accepted/rejected results update the local projection after arbiter/authority processing, not before.
- [ ] Run `python -m pytest backend/tests/test_character_agent_inf_intent_boundary.py backend/tests/test_character_agent_l4_execution.py backend/tests/test_siming_adaptive_bridge.py -v`.

**Completion gate:** Character cognition can influence local embodiment through the same semantic ingress as player control, while authority ownership remains unchanged.

### Task 10: Settle ActionAttempt through ESM/Gameplay atomically and idempotently

**Files:**
- Modify: `backend/app/models/embodied_interaction.py`
- Modify: `backend/app/services/embodied_execution_ingress.py`
- Modify: `backend/app/gameplay/action_window_runtime.py`
- Modify: `backend/app/services/embodied_authority_settlement_service.py`
- Modify: `scripts/interaction/EmbodiedActionController.gd`
- Modify: `scripts/interaction/GameplayRuntimeStateMirrorConsumer.gd`
- Create: `backend/tests/test_character_action_attempt_settlement_contract.py`

**Interfaces:**
- `ActionAttempt` includes the canonical fields `attempt_id`, `actor_ref`,
  `action_instance_id`, `semantic_action_id`, bounded `target_refs[]`,
  `contact_marker_id`, optional `contact_marker_time_seconds`, optional
  `action_family`/`weapon_ref`, `physics_tick`, bounded
  `physics_evidence_refs[]`, optional evidence digest, Phase 1 route
  (`esm|gameplay|composite`), optional server-issued `owner_contract_ref`,
  expected revision vector, idempotency key, command version,
  causation/correlation, source/privacy scope, and audit-only `submitted_at`.
- `AuthorityResult` includes attempt/action IDs, `transaction_id?`, outcome `committed|rejected|unknown`, committed event IDs, resulting revision vector, failed stage/code/precondition, recovery action, causation/correlation, authority scope, and committed projection.
- `EmbodiedAuthoritySettlementService.settle(attempt) -> AuthorityResult` returns the original result on identical duplicate delivery.
- `ActionAttempt.canonical_payload() -> Dictionary` excludes `submitted_at` and
  produces the exact idempotency comparison payload; `AuthorityResult.to_payload() -> Dictionary` is the only result envelope exposed to Godot and the Gameplay mirror.

- [ ] Write tests for two independent same-tick attempts, a shared-aggregate conflict, a duplicate with the same payload, a duplicate key with a different payload, stale expected revisions returning typed `revision_conflict` or `precondition_failed`, an unauthorized route, and a composite action that must not partially write ESM and Gameplay.
- [ ] Include one end-to-end melee settlement and one hitscan semantic-route
  fixture; reject client-supplied damage, hit confirmation, ammo mutation, or
  ballistic outcome fields before authority append.

  ```python
  def test_duplicate_attempt_returns_original_transaction():
      first = settle(valid_attempt(idempotency_key="k-1"))
      second = settle(valid_attempt(idempotency_key="k-1"))
      assert second.transaction_id == first.transaction_id
      assert second.outcome == "committed"
  ```

- [ ] Extend the existing embodied request/window models rather than adding a competing action channel. Validate actor/action/target, marker window, evidence shape, capability/status/resource gates, access/range/occupancy, route, expected revisions, and idempotency before append.
- [ ] Enforce `ActionAttempt <= 32 KiB`, `target_refs <= 8`,
  `physics_evidence_refs <= 8`, `collider_refs <= 32`, `hit_sensor_refs <= 16`,
  and `contact_points <= 32`; reject all overages as `payload_limit_exceeded`
  without truncating evidence.
- [ ] Record presentation marker observation before Motor execution, collect
  `PhysicsContactEvidence(T)` from Motor, and join them at the same-tick
  settlement boundary before emitting a contact-dependent `ActionAttempt(T)`.
- [ ] Implement the settlement pipeline in order: decode/schema validation; authenticate/authorize; idempotency lookup before loading mutable aggregates; pin policy/package/world revisions; load expected actor/world streams; validate `ActionWindowIntent` and affordance/status preconditions; revalidate physical evidence; produce typed effect proposals; validate the complete batch; atomically append or commit zero events; publish committed projection/outbox; return `AuthorityResult`.
- [ ] Send environment affordance/spatial/occupancy/object transitions to ESM; send resources/status/capabilities/equipment/body facts to Gameplay; use a single composite coordinator batch when both must commit atomically. If the store cannot atomically commit the required aggregates, reject or use an explicit predeclared reservation/compensation lifecycle.
- [ ] Project only committed results to `CharacterRuntimeState` and the Godot mirror. `unknown` triggers a query by the original idempotency key; it never creates a new attempt.
- [ ] Treat `unknown` as append/transport uncertainty only: query with the original idempotency key, freeze unsafe authority-dependent root motion, and never create a replacement attempt. Reject late results that would resurrect a cancelled or expired action.
- [ ] Run `python -m pytest backend/tests/test_character_action_attempt_settlement_contract.py backend/tests/test_action_window_runtime.py backend/tests/test_character_skill_settlement_integration.py -v`.

**Completion gate:** An action marker can request authority but no local or duplicate delivery can create a second or partial world consequence.

### Task 11: Implement Mode B connected semantic transport and reserve physical authority

**Files:**
- Modify: `backend/app/ws_protocol.py`
- Modify: `scripts/autoload/BackendBridge.gd`
- Modify: `scripts/interaction/GameplayMirrorBridge.gd`
- Create: `backend/tests/test_character_connected_action_protocol.py`
- Create: `scripts/verification/CharacterConnectedActionProbe.gd`

**Interfaces:**
- `actor_control_intent(session_id, actor_ref, connection_epoch, client_sequence, physics_tick, lease_revision, control_intents[], action_request_ids[], sent_at)`.
- `actor_action_request(session_id, actor_ref, connection_epoch, client_sequence, physics_tick, action_instance_id, idempotency_key, expected_revisions, request)`; `request` may contain semantic `action_family`/`weapon_ref` but no raw hit, damage, ammo, projectile, pose, or transform fields.
- Future-only `actor_body_snapshot|actor_body_delta(actor_ref, authority_epoch, physics_tick, body_revision, base_body_revision, position, velocity, facing, grounded, support_ref, active_action_ids[], correction_reason, snapshot_checksum)` plus `actor_body_correction(actor_ref, authority_epoch, base_body_revision, target_physics_tick, position, velocity, facing, correction_envelope_ref, reason)`.

- [ ] Write protocol tests for duplicate client sequence, sequence gap, stale lease revision, old connection epoch, unknown actor, impossible future tick, reconnect with stale leases, an action result after action expiry, and correction delivery. Assert Gameplay mirror `delivery_sequence`/`facade_revision` cannot be parsed as body stream revisions.
- [ ] Implement Mode B validation/serialization for semantic control and actions. On reconnect, increment `connection_epoch`, clear local stale leases/action pending state, request a fresh actor/runtime snapshot, and reject old-epoch messages.
- [ ] Preserve the admission/settlement distinction: request -> local
  accept/queue/reject -> optional local presentation -> marker observation ->
  same-tick evidence join -> `ActionAttempt` -> authority result. An admission
  acknowledgement never confirms damage, pickup, occupancy, or another world
  consequence.
- [ ] Preserve existing Gameplay mirror subscription, prediction, snapshot/delta base checks, and `facade_revision`. Keep its delivery protocol separate from the future physical body fields.
- [ ] Define but do not activate the future body-stream schema. It must contain
  fixed tick, declared physical authority owner/epoch, body revision/base
  revision, and a typed `body_correction`; Mode B uses only bounded
  `runtime_correction`. The stream must never carry raw bone poses or permit
  remote direct transform writes.
- [ ] Document the seven Mode C gates before activation: physical authority owner/trust boundary; fixed tick/body schema; collision/rigid-body determinism; prediction/correction budget; remote interpolation/interest management; body revision/replay/rollback evidence; and abuse validation for client control/contact evidence. Until all exist, report Mode B.
- [ ] Run `python -m pytest backend/tests/test_character_connected_action_protocol.py backend/tests/test_character_actor_bridge_static.py backend/tests/test_character_dynamic_state_delta_contract.py -v`.
- [ ] Run the connected Godot probe against a live backend; store a trace demonstrating normal delivery, duplicate handling, gap/resync, reconnect, and old-epoch rejection.

**Completion gate:** Phase 1 truthfully supports Mode B semantic authority/prediction recovery and has an explicit, non-enabled Mode C reservation.

### Task 12: Add read-only debugging, safe test controls, animation inspection, and bounded telemetry

**Files:**
- Create: `scripts/debug/CharacterRuntimeDebugSnapshot.gd`
- Create: `scripts/debug/CharacterRuntimeDebugOverlay.gd`
- Create: `scripts/debug/CharacterRuntimeTestPanel.gd`
- Create: `scripts/debug/CharacterAnimationDebugger.gd`
- Create: `scripts/debug/CharacterPerformanceMonitor.gd`
- Modify: `scenes/phase0/MainDemo.tscn`
- Create: `backend/tests/test_character_debug_tools_contract.py`

**Interfaces:**
- `CharacterRuntimeDebugSnapshot.capture(runtime, frame, command, motor_state) -> Dictionary` has no live mutable references.
- `CharacterRuntimeTestPanel.inject(proposal: Dictionary) -> Dictionary` applies `source=debug_fixture`, correlation ID, normal admission, and expiry.
- `CharacterAnimationDebugger.preview(profile_id, clip_id, time_s) -> Dictionary` cannot submit attempts or advance simulation.
- `CharacterPerformanceMonitor.record(stage: StringName, duration_us: int) -> void` keeps a fixed-size rolling/capture buffer.

- [ ] Write tests proving a debug injection goes through the controller/arbiter/authority path, a test panel cannot write private runtime fields/body transforms/world facts, an animation preview cannot move a body or emit `ActionAttempt`, and sustained recording remains bounded.
- [ ] Implement a selected-actor overlay from post-arbiter/post-Motor snapshots: leases, active/queued/rejected actions and active action/claim counts, claims/conflicts, frame and deterministic ordering key, contributions/command, grounded/velocity/collisions, pending attempt/revision, profile/clip/canonical mask/marker/root extraction, and bounded timing data.
- [ ] Implement editor/test-only panel controls to create expiring leases/action requests, select registered test actors, and use explicit simulated-authority fixtures. Every injected value must be visibly labeled and traceable.
- [ ] Implement presentation-only clip/mask/marker/root-motion and qualification-report inspection with play, pause, seek, and frame advance. Keep animation preview and a simulation fixed-step as separate controls.
- [ ] Monitor FPS, frame time, physics time, arbiter, claim scheduler, composition, Motor, and presentation costs using fixed maximum sample counts and capture windows.
- [ ] Run `python -m pytest backend/tests/test_character_debug_tools_contract.py backend/tests/test_character_debug_toggle_static.py backend/tests/test_character_observer_panel_static.py -v`.

**Completion gate:** Developers can inspect and inject through real boundaries without creating a privileged second gameplay path.

### Task 13: Capture replay traces and prove logical determinism

**Files:**
- Create: `scripts/character/CharacterActionReplayTrace.gd`
- Create: `scripts/verification/CharacterActionReplayProbe.gd`
- Create: `backend/tests/test_character_action_replay_determinism.py`
- Modify: `scripts/verification/verify_unified_character_action_foundation.py`
- Create: `.harness/profiles/unified-character-action-foundation.json`

**Interfaces:**
- `CharacterActionReplayTrace.append(tick: int, proposal: Dictionary, admission: Dictionary, command: Dictionary, evidence: Array[Dictionary], authority: Dictionary) -> void` stores normalized, immutable records.
- `CharacterActionReplayTrace.replay(records: Array[Dictionary]) -> Dictionary` returns frame/admission/command/evidence/authority digests.

- [ ] Write a deterministic trace fixture with simultaneous walk/right-arm action, claim conflict, root motion, collision evidence, duplicate authority delivery, stale result, lease expiry, and rejection recovery. Run it twice and compare all normalized digests.
- [ ] Serialize stable action/lease IDs, source/order keys, descriptor/profile version, physics tick/delta profile, quantized network command where applicable, normalized frame, scheduler decision, command, evidence digest, attempt/result identity, and recovery. Record engine/version/profile identity for any future physical-authority trace; redact private data from development overlays and exported reports.
- [ ] Compare logical results rather than exact floating-point collision internals: scheduler/admission decisions, normalized command inputs, evidence digest, authority request ordering, idempotency result, and final accepted projection must match within configured local floating-point tolerances.
- [ ] Add the profile to Harness with a backend contract step and a Godot runtime probe. Its report must state that dynamic rigid-body bitwise replay is not claimed.
- [ ] Run `python -m pytest backend/tests/test_character_action_replay_determinism.py -v`.
- [ ] Run `python scripts/verification/harness.py --profile unified-character-action-foundation`.

**Completion gate:** Failures in arbitration, root-motion composition, authority ordering, or recovery can be reproduced from a bounded trace.

### Task 14: Demonstrate the first milestone with two qualified characters

**Files:**
- Create: `scenes/integration/UnifiedCharacterActionFoundation.tscn`
- Create: `scripts/verification/UnifiedCharacterActionFoundationProbe.gd`
- Modify: `scripts/verification/verify_unified_character_action_foundation.py`
- Modify: `.harness/profiles/unified-character-action-foundation.json`
- Create: `backend/tests/test_unified_character_action_foundation_profile.py`

**Interfaces:**
- The integration scene mounts one player and one NPC as `CharacterBody3D` actors with distinct qualified package IDs, shared controller/arbiter/Motor/presentation services, an action target, and the debug overlay.
- Probe result fields: `package_reports`, `actor_motion_paths`, `visible_actions`, `attempts`, `authority_results`, `root_motion_cases`, `transport_cases`, and `runtime_capture_paths`.

- [ ] Write the profile test to require two qualified reports, shared Motor ownership, locomotion on both actors, one action lifecycle and presentation per actor, an Agent/INF-produced intent, success/rejection authority paths, and no transform/velocity writer outside Motor.
- [ ] Build the narrow integration scene using active package assets only. Do not revive the removed throne-hall scenes or make them a runtime dependency.
- [ ] Execute player and agent actions through the real boundary; verify Idle/Walk/Run/Jump/Turn, one external action with windup/contact/recovery/cancellation, concurrent walk plus a qualified upper-body action, and declared full-body fallback behavior.
- [ ] Verify one qualified equipment slot/hand anchor, one melee marker-to-
  `ActionAttempt` settlement, and one semantic hitscan request/authority
  fixture. Do not add ammo, projectile, or client damage truth to the scene.
- [ ] Exercise a wall, slope, step, support loss, movement/root/impulse composition, local contact with no settlement, successful settlement, rejected/timed-out recovery, independent same-tick attempts, and duplicate/stale transport behavior.
- [ ] Exercise one real ESM interaction, one Gameplay resource/status rejection with zero partial commit, and one composite actor-plus-world action. Verify duplicate retry returns the original transaction identity and same-revision races commit at most once.
- [ ] Verify Mode B body-stream fields are absent from runtime evidence and record the explicit absence of rollback, raw-pose replication, and server-authoritative rigid-body claims.
- [ ] Capture Godot runtime evidence with the actual configured editor/runtime plus backend trace. Screenshots/logs must identify the active scene, both package IDs, and probe result; static inspection alone cannot pass this task.
- [ ] Run `python -m pytest backend/tests/test_unified_character_action_foundation_profile.py -v`.
- [ ] Run `python scripts/verification/harness.py --profile unified-character-action-foundation` and then `python scripts/verification/harness.py --profile all`.

**Completion gate:** Both external characters visibly operate through one action substrate with real authority outcomes. The reported milestone is Mode B, never authoritative multiplayer physics.

### Task 15: Close documentation drift and apply the release gate

**Files:**
- Modify: `docs/INDEX.md`
- Modify: `docs/character/character-action-foundation-current-state.md`
- Modify: `docs/character/character-action-asset-interface.md`
- Modify: `docs/character/character-actor-architecture.md`
- Modify: `docs/character/character-agent-runtime-architecture.md`
- Modify: `docs/character/character-debug-and-verification.md`
- Modify: `docs/character/character-runtime-design-drift-audit.md`
- Modify: `docs/superpowers/plans/2026-09-14-character-shared-contracts-arbitration-and-tools-implementation-plan.md`
- Modify: `docs/superpowers/plans/2026-09-14-character-animation-asset-qualification-and-concurrent-realization-implementation-plan.md`
- Modify: `docs/superpowers/plans/2026-09-14-character-physics-motion-and-contact-implementation-plan.md`
- Modify: `docs/superpowers/plans/2026-09-14-character-esm-action-attempt-settlement-implementation-plan.md`
- Modify: `docs/superpowers/plans/2026-09-14-character-connected-action-and-physical-replication-implementation-plan.md`
- Modify: `scripts/verification/verify_unified_character_action_foundation.py`

**Interfaces:**
- `docs/INDEX.md` links this master plan as the single execution order.
- Child-plan headers declare themselves task-level reference material and link to this master plan; they must not contradict its ownership/mode/asset rules.
- `verify_unified_character_action_foundation.py --stage release` checks active artifact/version/report references and explicit Mode B wording.

- [ ] Update repository truth documents to state the completed ownership boundary, action/asset contracts, current migration status, debugging tools, verification commands, explicit deferrals, and any remaining active legacy adapter.
- [ ] Replace child-plan language that suggests an independent execution order with a link to the matching task in this plan. Preserve useful detailed test cases, but remove conflicting authority or animation claims.
- [ ] Add a documentation test that fails on a second Motor owner, a claim that Godot/animation/INF settles world truth, a claim that Mode B is physical multiplayer authority, or a Phase 1 descriptor with non-empty `atomic_sequence`.
- [ ] Run the repository placeholder-token scan over `docs/superpowers/plans/2026-09-14-*.md` and resolve every match in this plan set.
- [ ] Run `python scripts/verification/verify_unified_character_action_foundation.py --stage release`.
- [ ] Run `python -m pytest -v`.
- [ ] Run `python scripts/verification/harness.py --profile all`.
- [ ] Run `git diff --check` and record the actual command outcomes and Godot runtime evidence locations in `character-action-foundation-current-state.md`.

**Completion gate:** Specs, plans, asset guidance, runtime documentation, and executable checks describe one coherent active design with no inflated physical-networking claim.

## First-Milestone Acceptance Checklist

- [ ] Two external packages pass the canonical mapping and qualification report requirements.
- [ ] Player and NPC share controller proposal, arbiter, command composition, `CharacterMotor`, and presentation-input boundaries.
- [ ] Independent, non-conflicting actions can run concurrently; conflicts are explicable by canonical claims and lifecycle state.
- [ ] A qualified held-item binding and melee profile use the shared claims and
  attempt path; a hitscan profile remains semantic and authority-bound.
- [ ] Qualified root motion, movement, impulses, collision, and recovery converge through one Motor command.
- [ ] Every contact-dependent consequence is an `ActionAttempt` and becomes visible world truth only after idempotent ESM/Gameplay settlement.
- [ ] A real CharacterAgent/INF message creates a visible, boundary-compliant local intent.
- [ ] Connected Mode B verifies sequence/idempotency/reconnect/recovery; the project makes no Mode C/rollback claim.
- [ ] Debug, test, animation, performance, and replay tools are bounded and cannot bypass normal ownership.
- [ ] Full test/Harness results and real Godot runtime evidence are recorded before declaring the milestone complete.

## Explicitly Deferred After This Plan

- Authored replacement animation production, a generic combo library, broad hit-reaction/death/survival coverage, and runtime module hot-unplug.
- Atomic action-sequence expansion, despite preserving the empty descriptor field.
- Complete weapon runtime (ammo, magazine/chamber, ballistic projectiles,
  dual wield, parry/clash, and arbitrary prop weaponization).
- Raw-pose networking, netfox rollback, server-authoritative rigid bodies, ragdoll authority, and cross-machine bitwise physics replay.
- A new global cognition system, full Siming implementation, generic ESM domain expansion, or a replacement world/network authority model.
