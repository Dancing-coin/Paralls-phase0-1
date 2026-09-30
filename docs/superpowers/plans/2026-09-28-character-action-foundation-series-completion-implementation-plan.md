# Character Action Foundation Series Completion Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Complete the remaining action-foundation work after the StreetCombatDemo AnimationTree pilot: real root-motion locomotion, universal Motor ownership, CharacterReplica convergence, descriptor/arbiter enforcement, authority closure, asset registry admission, and synchronized documentation.

**Architecture:** Keep the external controller as the animation implementation layer. A shared actor runtime produces admitted semantic states and motion/action contributions; RoleAnimationController realizes those states; RootMotionSampler produces bounded contributions; MotionContributionComposer creates one physics command; CharacterMotor executes it; ESM/Gameplay/Composite settles world consequences.

**Tech Stack:** Godot 4.6 GDScript, AnimationTree/AnimationPlayer, CharacterBody3D, imported GLB manifests, existing Python backend authority services, pytest, Godot headless probes, Harness profiles.

**Spec:** docs/superpowers/specs/2026-09-28-character-action-foundation-series-completion-design.md

## Global Constraints

- CharacterMotor is the only active owner of body displacement, gravity, collision, root-motion consumption, and move_and_slide.
- Animation and root-motion presentation nodes never write actor transforms.
- CharacterReplica remains a compatibility shell until the migration report proves no active consumer depends on its concrete implementation.
- External clips are admitted by manifest and qualification report, never by directory or clip name.
- ESM/Gameplay/Composite remains the world-consequence authority.
- Mode B semantic transport is in scope; raw-pose replication and rollback remain deferred.
- StreetCombatDemo with the three real imported packages is the acceptance scene.

## Review Focus

- A root track with zero or malformed calibration must not move the body.
- A locomotion lease and equivalent root contribution must not double-apply displacement.
- A one-shot action must recover when a locomotion request arrives during cross-fade.
- NPC, agent, and player paths must use the same Motor boundary.
- A legacy CharacterReplica caller must continue to work without adding behavior to the compatibility shell.

### Task 1: Freeze the baseline and ownership audit

**Files:**
- Create: docs/character/action-foundation-series-baseline-2026-09-28.md
- Create: scripts/verification/CharacterActionFoundationOwnershipProbe.gd
- Modify: backend/tests/test_character_replica_convergence_static.py

- [ ] Record landed behavior, known failures, backup path, and exact StreetCombatDemo probe output.
- [ ] Scan active GDScript for position, global_position, velocity, and move_and_slide writers; fail if an active body writer exists outside Motor.
- [ ] Add static checks that StreetCharacterSkin never directly pauses AnimationPlayer and RoleAnimationController owns AnimationTree binding.
- [ ] Run the probe and focused tests. Keep raw runtime evidence in the owned temporary directory.

### Task 2: Formalize the semantic animation interface

**Files:**
- Modify: scripts/character/RoleAnimationController.gd
- Modify: scripts/street_combat/StreetCharacterSkin.gd
- Create: scripts/character/CharacterAnimationPresentation.gd
- Modify: backend/tests/test_character_replica_convergence_static.py

- [ ] Define typed semantic requests for locomotion, jump, guard, and action states.
- [ ] Keep set_state as a compatibility adapter only; new callers use semantic methods.
- [ ] Make diagnostics report state, clip, fallback, lock, and transition reason.
- [ ] Add explicit action recovery and cancel behavior for interrupted one-shots.
- [ ] Verify missing tree, clip, and descriptor fail closed to idle/fallback.

### Task 3: Qualify and calibrate real root motion

**Files:**
- Modify: scripts/character/RootMotionSampler.gd
- Modify: scripts/character/CharacterActor.gd
- Modify: scripts/character/CharacterMotor.gd
- Modify: scripts/character/MotionContributionComposer.gd
- Modify: assets/active/female_bandage_external/manifest.json
- Modify: assets/active/female_jk_external/manifest.json
- Modify: assets/active/female_t_external/manifest.json
- Create: scripts/verification/RootMotionQualificationProbe.gd
- Create: backend/tests/test_root_motion_contract_static.py

- [ ] Measure walking and running root tracks in local space and record forward axis, distance, cadence, and support requirements.
- [ ] Replace zero-distance placeholder policies only after measured profiles pass envelope checks.
- [ ] Emit typed MotionContribution values with source, policy, clip, tick, local delta, and consumption token.
- [ ] Suppress equivalent lease velocity when drive_locomotion or replace_locomotion is active.
- [ ] Reject malformed, unsupported, over-envelope, and unsupported-support root contributions.
- [ ] Verify single consumption, loop boundary, facing rotation, slope, wall, stop/restart, and lost-support behavior.

### Task 4: Make Motor ownership universal

**Files:**
- Modify: scripts/character/CharacterActor.gd
- Modify: scripts/character/CharacterMotor.gd
- Modify: scripts/character/MotionContributionComposer.gd
- Modify: scripts/character/CharacterReplica.gd
- Modify: active NPC and agent movement callers found by Task 1
- Create: scripts/verification/CharacterMotorOwnershipProbe.gd

- [ ] Route player, NPC, agent, and program movement through ControllerPort -> Arbiter -> Frame -> Composer -> Motor.
- [ ] Remove or isolate direct coordinate stepping in active paths.
- [ ] Keep compatibility methods as command adapters, never movement methods.
- [ ] Prove exactly one move_and_slide owner and no direct body transform writer in StreetCombatDemo and the main Phase 0 scene.

### Task 5: Close CharacterReplica migration

**Files:**
- Modify: scripts/character/CharacterActor.gd
- Modify: scripts/character/CharacterReplica.gd
- Modify: scenes/phase0/CharacterReplica.tscn
- Modify: docs/character/character-replica-convergence.md
- Create: scripts/verification/CharacterReplicaCompatibilityProbe.gd

- [ ] Inventory every active scene, bridge, probe, and backend-facing caller referencing CharacterReplica.
- [ ] Move remaining runtime behavior into CharacterActor or dedicated components.
- [ ] Keep only explicit forwarding methods and class identity in CharacterReplica.
- [ ] Replace tests that assume implementation is in CharacterReplica with interface and ownership tests, preserving intentional compatibility assertions.
- [ ] Produce a migration report listing remaining concrete dependencies and removal conditions.

### Task 6: Enforce descriptors and arbitration

**Files:**
- Modify: scripts/character/ActorActionArbiter.gd
- Modify: scripts/character/CharacterActionAssetRegistry.gd
- Modify: scripts/character/CharacterRuntimeState.gd
- Modify: scripts/street_combat/StreetCombatCoordinator.gd
- Modify: scripts/street_combat/StreetCharacterSkin.gd
- Create: backend/tests/test_character_action_descriptor_runtime.py

- [ ] Require semantic action ID, canonical claims, locomotion relation, root policy, markers, cancel windows, and authority route before admission.
- [ ] Reject raw clip requests from runtime callers.
- [ ] Resolve boxing and sword actions through the same arbiter and lock/cancel rules.
- [ ] Preserve full-body-exclusive fallback for currently unqualified street actions.
- [ ] Verify deterministic priority, resource conflicts, cancellation, death override, and same-tick ordering.

### Task 7: Close ActionAttempt authority and Mode B recovery

**Files:**
- Modify: scripts/street_combat/StreetCombatCoordinator.gd
- Modify: relevant backend ESM/Gameplay action route modules
- Modify: scripts/autoload/BackendBridge.gd
- Create: backend/tests/test_character_action_attempt_closure.py
- Create: scripts/verification/StreetActionAttemptProbe.gd

- [ ] Attach marker and Motor contact evidence to one typed ActionAttempt candidate.
- [ ] Route through the existing ESM/Gameplay/Composite authority boundary.
- [ ] Enforce idempotency, changed-duplicate rejection, expected revision checks, and zero-write local-only failure.
- [ ] Add connection epoch, client sequence, physics tick, causation, and correlation to Mode B requests.
- [ ] On reconnect, clear stale lease/prediction, obtain a fresh snapshot, and resume only after the new epoch is accepted.
- [ ] Verify punch and sword authority outcomes in StreetCombatDemo with a real backend.

### Task 8: Enforce asset registry admission

**Files:**
- Modify: scripts/character/CharacterEmbodimentAssetRegistry.gd
- Modify: assets/active/*/manifest.json
- Modify: scripts/street_combat/StreetCharacterSkin.gd
- Create: scripts/verification/CharacterAssetAdmissionProbe.gd
- Create: backend/tests/test_character_asset_admission_runtime.py

- [ ] Load only qualified manifests with digest, canonical mapping, action descriptors, and root profile.
- [ ] Distinguish full_body_exclusive, derived_upper_body, drive_locomotion, and fallback modes.
- [ ] Reject unknown package, digest mismatch, missing skeleton mapping, missing marker, and invalid root profile.
- [ ] Record package admission and fallback reason in diagnostics.
- [ ] Verify the three street packages and future packages through the same registry path.

### Task 9: Add deterministic runtime evidence and tooling

**Files:**
- Modify: scripts/verification/CharacterReplicaConvergenceProbe.gd
- Create: scripts/verification/CharacterActionFoundationRuntimeProbe.gd
- Modify: docs/character/character-debug-and-verification.md
- Modify: relevant Harness profile metadata

- [ ] Report package, skeleton qualification, tree binding, state, lock, root policy, root contribution, Motor command, contact evidence, and authority result per actor.
- [ ] Add replay comparison for intent admission, action state, motion command, evidence digest, attempt ordering, and final projection.
- [ ] Keep raw reports outside the repository and export only reviewable summaries.
- [ ] Add StreetCombatDemo runtime evidence to the appropriate Harness profile.

### Task 10: Reconcile and publish the documentation set

**Status:** **complete, but affected by the Task 9 external blocker**. Task 9
remains **blocked** by the repository-wide pytest gate; that blocker limits the
release claim but does not leave the documentation reconciliation incomplete.

**Files:**
- Modify: docs/character/character-action-foundation-current-state.md
- Modify: docs/character/character-action-foundation-operator-guide-and-index.md
- Modify: docs/character/character-replica-convergence.md
- Modify: docs/character/character-asset-integration.md
- Modify: docs/character/character-debug-and-verification.md
- Modify: docs/INDEX.md
- Create: docs/character/action-foundation-series-status.md

- [x] Mark the 2026-09-28 pilot as landed and separate it from remaining gates.
- [x] Make the new spec the action-foundation series entry point.
- [x] Make this plan the only execution order for the remaining work.
- [x] Label old June plans and pre-convergence statements historical or transitional where needed.
- [x] Add a gap table mapping each remaining issue to code owner, spec section, plan task, verification command, and completion evidence.
- [x] Run documentation link checks, focused tests, Godot headless probe, and git diff --check.

The Task 10 documentation result is complete. The remaining repository-wide
pytest failures belong to Task 9's external release blocker and must not be
reclassified as a Task 10 documentation failure.

## Verification Ladder

1. Documentation baseline: link and Markdown structure checks.
2. Animation gate: focused static tests plus StreetCombatDemo headless probe.
3. Motion gate: root-motion qualification and Motor ownership probes.
4. Authority gate: backend ActionAttempt and Mode B probes.
5. Final gate: python -m pytest -v, relevant Harness profiles, StreetCombatDemo runtime evidence, and a fresh documentation/index audit.

## Completion Criteria

The series is complete only when fresh evidence exists for every gate. Passing the StreetCombatDemo animation probe closes the animation pilot; it does not close the full series.
