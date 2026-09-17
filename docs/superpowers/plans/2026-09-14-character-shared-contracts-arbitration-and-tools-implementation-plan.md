# Character Shared Contracts, Arbitration And Developer Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish one shared actor contract for namespaced tags, sustained control leases, parallel action instances, resource claims, and development observability before the physics, asset, authority, and connected plans are integrated.

**Architecture:** Human, CharacterAgent, and program adapters produce `CharacterIntentFrame` proposals. `ActorActionArbiter` admits independent action instances against canonical claims while `ResourceClaimScheduler` resolves conflicts and `MotionContributionComposer` guarantees one final physics writer. Immutable snapshots feed debug tools; debug controls re-enter through normal adapters and never mutate private state.

**Tech Stack:** Godot 4.6 GDScript, existing character adapters and runtime state, AnimationTree-facing presentation snapshots, pytest, and Harness verification.

**Spec:** `docs/superpowers/specs/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-design.md`

**Execution status:** Task-level reference for Task 2-3 and Task 12 of
`docs/superpowers/plans/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-implementation-plan.md`.
The unified plan is the only implementation order; this file does not define
an alternate runtime path or release gate.

## Global Constraints

- Runtime tags crossing the actor boundary are namespaced and ownership-defined.
- Movement is a renewable control lease; sustained and transient actions are separate instances.
- Multiple actions may coexist only when canonical resource and physics claims are compatible.
- One final writer exists for each motion/physics channel on every physics tick.
- CharacterAgent, INF, and Siming propose intent/catalyst metadata; they do not write poses, transforms, damage, or death.
- Debug tools are observational or traceable expiring inputs; they cannot bypass admission or authority.
- Phase 1 weapon support is limited to an equipment binding, semantic `melee`
  and `hitscan` action families, canonical weapon claims, and authority-bound
  request fields; it does not implement ammo, ballistics, or arbitrary prop
  weaponization.
- `atomic_sequence` remains empty in Phase 1.
- Canonical resource IDs are `world_motion`, `pelvis`, `upper_body`,
  `left_arm`, `right_arm`, `left_hand`, `right_hand`, `left_leg`,
  `right_leg`, `head`, `root_translation`, `facing`, and the declared
  physics/weapon claims; legacy unqualified movement/chain aliases are not
  accepted at the runtime boundary.

### Task 1: Freeze tag, intent-frame, and descriptor contracts

**Files:**
- Create: `scripts/character/CharacterTagContract.gd`
- Create: `scripts/character/CharacterIntentFrame.gd`
- Modify: `scripts/character/CharacterControllerPort.gd`
- Modify: `scripts/character/CharacterRuntimeState.gd`
- Modify: `scripts/character/CharacterActionAssetDescriptor.gd`
- Create: `scripts/character/CharacterWeaponActionProfile.gd`
- Modify: `scripts/character/CharacterEquipmentBindingProfile.gd`
- Test: `backend/tests/test_character_action_tag_contract_static.py`

**Interfaces:**
- `CharacterTagContract.normalize_tag(String) -> String`
- `CharacterTagContract.namespace(String) -> String`
- `CharacterTagContract.is_allowed_for_ingress(String) -> bool`
- `CharacterIntentFrame.from_proposals(Array) -> Dictionary`
- `CharacterActionAssetDescriptor.validate() -> Dictionary`
- `CharacterWeaponActionProfile.normalize(Dictionary) -> Dictionary`

- [ ] Define `goal`, `intent`, `evidence`, `capability`, `affordance`, `constraint`, `state`, `status`, `action`, `phase`, `occupy`, `event`, `authority`, `presentation`, and `expression` namespaces.
- [ ] Treat `authority:*` as a read-only committed projection namespace;
  proposal ingress must reject authority-result fields and generic `inf`
  settlement routes.
- [ ] Reject unnamespaced ingress tags while preserving read-only compatibility for Phase 0 fields.
- [ ] Define intent-frame fields for tick, lease set, action requests, context tags, evidence refs, and provenance.
- [ ] Define descriptor fields for clips, profiles, claims, markers, cancel windows, route, fallback, and `atomic_sequence=[]`.
- [ ] Restrict Phase 1 `authority_route_ref` to `esm`, `gameplay`, or
  `composite`; keep `owner_contract_ref` server-issued and reject `inf` as a
  generic settlement route.
- [ ] Define the minimum weapon profile fields (`action_family`, `weapon_ref`,
  required slot, claims, marker/cancel metadata, and authority route) and reject
  damage, ammo, hit, or transform fields at this boundary.
- [ ] Add tests proving authoritative damage/effect values are not accepted as local action metadata.
- [ ] Run the focused test before and after implementation.

### Task 2: Implement lease, claims, and multi-action arbitration

**Files:**
- Create: `scripts/character/ActorActionArbiter.gd`
- Create: `scripts/character/ResourceClaimScheduler.gd`
- Create: `scripts/character/ActionInstance.gd`
- Modify: `scripts/character/CharacterRuntimeState.gd`
- Modify: `scripts/character/CharacterControllerPort.gd`
- Test: `backend/tests/test_actor_action_arbiter_static.py`

**Interfaces:**
- `ActorActionArbiter.resolve(Dictionary, Array, Dictionary) -> Dictionary`
- `ResourceClaimScheduler.admit(Dictionary, Dictionary) -> Dictionary`
- `ActionInstance.to_snapshot() -> Dictionary`

- [ ] Freeze canonical visual/physical claim IDs and parent-child conflict rules.
- [ ] Model movement as a renewable lease independent of transient or sustained action instances.
- [ ] Admit non-conflicting same-tick actions and return `accept_now`, `queue`, or `reject` with a typed reason.
- [ ] Apply status constraints, cancellation windows, priority, recovery, and death override deterministically.
- [ ] Guarantee stable ordering by tick, layer priority, source priority, and action instance ID.
- [ ] Run replay tests for movement plus upper-body action, conflicting hand actions, and full-body override.
- [ ] Include one admitted melee profile and one hitscan profile fixture; prove
  both use the ordinary Arbiter lifecycle and cannot create a second scheduler.

### Task 3: Compose motion contributions without a second writer

**Files:**
- Create: `scripts/character/MotionContributionComposer.gd`
- Modify: `scripts/character/CharacterMotor.gd`
- Test: `backend/tests/test_character_motion_composition_static.py`

**Interfaces:**
- `MotionContributionComposer.compose(CharacterIntentFrame, Dictionary) -> Dictionary`

- [ ] Accept locomotion, root motion, impulse, correction, and gravity contributions from admitted layers.
- [ ] Enforce caps and envelopes from the active physics profile.
- [ ] Emit one `PhysicsMotionCommand` per actor/tick and a deterministic composition trace.
- [ ] Reject direct transform payloads and undeclared contribution sources.
- [ ] Run equivalent-input replay tests and conflict tests.

### Task 4: Handoff Agent/INF bridge ownership

This child plan deliberately does not implement the CharacterAgent, INF, or
Siming bridge. Unified-plan Task 9 is the sole owner of that boundary,
including proposal normalization, metadata preservation, and committed-result
projection. This plan consumes the resulting `CharacterIntentFrame` and must
not add a second adapter, settlement route, or authority writer.

### Task 5: Add immutable debug snapshots and overlay data

**Files:**
- Create: `scripts/character/CharacterDebugSnapshot.gd`
- Create: `scripts/ui/CharacterActionDebugOverlay.gd`
- Modify: `scripts/character/CharacterRuntimeState.gd`
- Test: `backend/tests/test_character_debug_snapshot_static.py`

**Interfaces:**
- `CharacterDebugSnapshot.capture(Dictionary) -> Dictionary`
- `CharacterActionDebugOverlay.bind_snapshot(Dictionary) -> void`

- [ ] Capture active leases, action instances, claims, intent frame, motion contributions, Motor state, markers, and bounded timing telemetry.
- [ ] Make snapshots immutable copies so the overlay cannot mutate runtime state.
- [ ] Show claim conflicts, queue/reject reasons, and authority pending state.
- [ ] Add tests that mutate an overlay-bound dictionary without changing runtime state.

### Task 6: Add safe test control panel, animation debugger, and performance telemetry

**Files:**
- Create: `scripts/ui/CharacterTestControlPanel.gd`
- Create: `scripts/ui/CharacterAnimationDebugger.gd`
- Create: `scripts/character/CharacterPerformanceTelemetry.gd`
- Test: `backend/tests/test_character_debug_tools_boundary_static.py`

**Interfaces:**
- `CharacterTestControlPanel.submit_debug_request(Dictionary) -> Dictionary`
- `CharacterAnimationDebugger.preview_clip(StringName, float) -> void`
- `CharacterPerformanceTelemetry.snapshot() -> Dictionary`

- [ ] Route forced state/action/test-enemy controls through expiring debug leases and normal adapters.
- [ ] Keep animation preview isolated from simulation: no attempts, no Motor commands, no world writes.
- [ ] Measure FPS, frame time, physics time, arbiter, scheduler, composer, Motor, and presentation duration.
- [ ] Add tests for expiry, unauthorized direct mutation, preview isolation, and bounded telemetry under sustained action load.

### Task 7: Shared-spine verification

**Files:**
- Create: `scripts/verification/verify_character_shared_spine.py`
- Test: `backend/tests/test_character_shared_spine_profile.py`

- [ ] Verify player, agent, and program proposals normalize into one intent-frame shape.
- [ ] Verify movement plus non-conflicting upper-body action can coexist while conflicting claims queue or reject.
- [ ] Verify a qualified held-item binding and melee claim reach the shared
  action frame, while a hitscan request remains semantic until authority.
- [ ] Verify death/status override and cancellation release claims deterministically.
- [ ] Verify debug tools cannot bypass arbiter, Motor, ESM, or Gameplay boundaries.
- [ ] Run `python -m pytest backend/tests/test_character_shared_spine_profile.py -v`.

## Completion Criteria

- [ ] Namespaced tags, intent frames, action descriptors, claims, leases, and action instances are stable and tested.
- [ ] Parallel action semantics are deterministic and independent of raw animation clip names.
- [ ] Agent/INF/Siming metadata enters only through proposal adapters.
- [ ] Debug tools are observational or traceable inputs with no authority bypass.
- [ ] Child physics, asset, ESM, and connected plans can consume the shared interfaces without redefining them.
