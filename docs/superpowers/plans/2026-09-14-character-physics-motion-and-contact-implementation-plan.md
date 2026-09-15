# Character Physics Motion And Contact Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `CharacterMotor` the single local owner of movement, root motion, collision response, support state, and provisional physical evidence for every actor.

**Architecture:** Action and locomotion layers emit typed `MotionContribution` values. The composer resolves them into one `PhysicsMotionCommand`; the Motor applies that command through Godot's kinematic body and emits evidence. ESM/Gameplay remain the authority for semantic consequences.

**Tech Stack:** Godot 4.6 `CharacterBody3D`, GDScript, existing `CharacterMotor`, `CharacterReplica`, physics query APIs, pytest, and headless/runtime harness checks.

**Spec:** `docs/superpowers/specs/2026-09-14-character-physics-motion-and-contact-subspec.md`

**Execution status:** Task-level reference for Task 4-5 of
`docs/superpowers/plans/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-implementation-plan.md`.
The unified plan is the only implementation order; this file does not define
an alternate runtime path or release gate.

## Global Constraints

- `CharacterMotor` is the only owner of velocity, gravity, facing, collision, support, root-motion application, and `move_and_slide()`.
- Presentation code may sample root motion but may not write actor transforms.
- Contact evidence is provisional and cannot mutate ESM/Gameplay truth.
- Every contribution carries source, tick, priority, envelope, and cancellation semantics.
- Physics failures produce typed recovery; they never fake successful authority settlement.
- Mode B uses `runtime_correction` as a bounded Gameplay/runtime contribution;
  Mode C `body_correction` is future-only and requires a separate
  `PhysicalAuthority` body stream. Do not use an unqualified "correction"
  label for both modes.
- Phase 1 weapon evidence is limited to qualified `weapon_hit_volume:<id>`
  sensor references for melee and bounded ray/origin observations for hitscan;
  neither may write damage, ammo, object state, or a held-item rigid body.

### Task 1: Add typed physics contracts

**Files:**
- Create: `scripts/character/CharacterPhysicsContracts.gd`
- Modify: `scripts/character/CharacterMotor.gd`
- Test: `backend/tests/test_character_physics_contract_static.py`

**Interfaces:**
- `CharacterPhysicsContracts.motion_contribution(Dictionary) -> Dictionary`
- `CharacterPhysicsContracts.physics_motion_command(Dictionary) -> Dictionary`
- `CharacterPhysicsContracts.contact_evidence(Dictionary) -> Dictionary`

- [ ] Define contribution kinds `input`, `root_motion`, `impulse`,
  `runtime_correction`, and `gravity`; reserve `body_correction` for the
  future Mode C stream.
- [ ] Define support modes, root-motion envelopes, collision response, and evidence digest fields.
- [ ] Reject direct transform and unbounded correction payloads at the contract boundary.
- [ ] Run the focused static test and verify malformed contributions fail closed.

### Task 2: Implement deterministic composition

**Files:**
- Create: `scripts/character/MotionContributionComposer.gd`
- Modify: `scripts/character/CharacterRuntimeState.gd`
- Test: `backend/tests/test_motion_contribution_composer_static.py`

**Interfaces:**
- `MotionContributionComposer.compose(Array, Dictionary) -> Dictionary`

- [ ] Order contributions by physics tick, source priority, and stable contribution ID.
- [ ] Compose locomotion, root motion, impulse, gravity, and correction into one bounded command.
- [ ] Apply speed/acceleration/impulse caps from the physics profile.
- [ ] Emit deterministic traces for equivalent input frames and replay them in the focused test.

### Task 3: Converge Motor execution

**Files:**
- Modify: `scripts/character/CharacterMotor.gd`
- Modify: `scripts/character/CharacterReplica.gd`
- Modify: `scripts/player/PlayerShell.gd`
- Test: `backend/tests/test_character_replica_motor_boundary_static.py`

**Interfaces:**
- `CharacterMotor.apply_motion_command(CharacterBody3D, Dictionary, float) -> Dictionary`
- `CharacterMotor.apply_intent_frame(CharacterBody3D, Dictionary, float) -> Dictionary`

- [ ] Remove or isolate every direct `global_position`, `position`, and `velocity` write outside Motor.
- [ ] Route player and NPC movement through the same intent-frame entry point.
- [ ] Preserve camera and input shell behavior while moving authority to Motor.
- [ ] Add static assertions that reject a second locomotion writer.
- [ ] Run the focused boundary test and existing character control tests.

### Task 4: Add support and collision evidence

**Files:**
- Create: `scripts/character/CharacterPhysicsEvidenceCollector.gd`
- Modify: `scripts/character/CharacterMotor.gd`
- Test: `backend/tests/test_character_physics_evidence_static.py`

**Interfaces:**
- `CharacterPhysicsEvidenceCollector.collect(CharacterBody3D, int) -> Dictionary`

- [ ] Record grounded state, support collider/reference, collision normals, travel, slide count, and evidence digest.
- [ ] Keep evidence local and provisional; expose only typed references to action attempts.
- [ ] Enforce evidence bounds: `collider_refs <= 32`, `hit_sensor_refs <= 16`,
  `contact_points <= 32`, serialized evidence `<= 16 KiB`; reject overages as
  `payload_limit_exceeded` without truncation.
- [ ] Cover a melee sensor evidence record and a hitscan ray evidence record;
  both must remain `local_only=true` and authority-neutral.
- [ ] Add slope, step, wall, and support-loss cases to the test fixture.
- [ ] Verify collisions clamp command displacement without creating semantic success.

### Task 5: Integrate root-motion policies and failure recovery

**Files:**
- Modify: `scripts/character/KnightRoleSkin.gd`
- Modify: `scripts/character/GenericRoleSkin.gd`
- Modify: `scripts/interaction/EmbodiedActionController.gd`
- Test: `backend/tests/test_root_motion_policy_static.py`

**Interfaces:**
- `CharacterMotor.submit_root_motion(Dictionary) -> Dictionary`
- `CharacterMotor.freeze_contact_dependent_motion(String, int) -> void`

- [ ] Implement `hold`, `bounded_continue`, and `reversible_continue` policies.
- [ ] Consume root deltas through Motor and clear them on action completion, cancellation, timeout, and reset.
- [ ] Join marker observations to Motor evidence on the same physics tick before
  the ESM/Gameplay `ActionAttempt` emitter runs; presentation markers alone do
  not confirm contact.
- [ ] Freeze unsafe contact-dependent motion while an authority result is unknown.
- [ ] Add recovery tests for rejection, stale contact, target loss, and support loss.

### Task 6: Physics verification and regression closure

**Files:**
- Create: `scripts/verification/verify_character_physics_motion.py`
- Test: `backend/tests/test_character_physics_motion_profile.py`

- [ ] Verify equivalent player/NPC intent produces equivalent Motor projections.
- [ ] Verify multiple contributions have one final writer and stable replay output.
- [ ] Verify evidence is emitted without ESM/Gameplay mutation.
- [ ] Run `python -m pytest backend/tests/test_character_physics_motion_profile.py -v`.
- [ ] Run `python scripts/verification/harness.py --profile godot-project` with a scene showing wall, slope, step, and support-loss behavior.

## Completion Criteria

- [ ] No non-Motor actor transform or velocity writes remain on the tested action path.
- [ ] Root motion, input locomotion, impulses, and corrections compose into one bounded Motor command.
- [ ] Contact evidence is reproducible and authority-neutral.
- [ ] Physics tests pass with explicit recovery behavior for failure cases.
