# CharacterReplica Retirement and Global Action Foundation Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate every active role path to `CharacterActor`, retire `CharacterReplica` as a compatibility shell, and close the action-foundation gates with fresh repository-wide evidence.

**Architecture:** Keep `CharacterActor` as the only formal actor host. Normalize player, agent, program, NPC, embodied, and compatibility inputs through `CharacterControllerPort` and `CharacterControlIntent`; arbitrate through `ActorActionArbiter`; realize presentation through `RoleAnimationController` and `CharacterPresentationRuntime`; compose and execute all body motion through `CharacterMotor`. Backend ESM/Gameplay/Composite remains the authority for committed world consequences.

**Tech Stack:** Godot 4.6 GDScript, `CharacterBody3D`, AnimationTree/AnimationPlayer, imported GLB qualification manifests, Python backend authority services, pytest, Godot headless probes, Harness profiles.

**Spec:** `docs/superpowers/specs/2026-09-29-character-replica-retirement-and-global-action-foundation-closure-design.md`

## Global Constraints

- `CharacterMotor` is the only active owner of body displacement, gravity, collision, root-motion consumption, and `move_and_slide`.
- Animation and root-motion presentation nodes never write actor transforms.
- `CharacterReplica` remains a compatibility shell until the migration report proves no active consumer depends on its concrete implementation.
- External clips are admitted by manifest and qualification report, never by directory or clip name.
- ESM/Gameplay/Composite remains the world-consequence authority.
- Mode B semantic transport is in scope; raw-pose replication and rollback remain deferred.
- StreetCombatDemo with the three real imported packages is the acceptance scene.
- No new dependency is added.
- Runtime evidence is exported outside the repository; `.harness/` keeps only reviewed metadata and contract artifacts.

## Review Focus

- A root track with zero, malformed, or stale calibration must fail closed without moving the body; Task 5 pins this with root qualification and Motor tests.
- A locomotion lease plus an equivalent root contribution must not double-apply displacement; Task 5 pins one consumption token and one Motor command per physics tick.
- A one-shot action interrupted by locomotion or cancellation must recover deterministically; Task 2 pins lock, cancel, hold, and recovery behavior.
- A legacy `CharacterReplica` caller must continue to work without adding behavior to the compatibility shell; Task 3 pins forwarding-only compatibility and call counters.
- A reconnect, duplicate, stale revision, or changed duplicate must not create a second authority write; Task 6 pins Mode B replay and recovery.

---

## File and Lane Map

| Lane | Responsibility | Primary files |
|---|---|---|
| Contract | caller inventory, static guards, migration report | `.harness/profiles/character-replica-retirement.json`, `scripts/verification/verify_character_replica_retirement.py`, `scripts/verification/CharacterReplicaRetirementProbe.gd`, `scripts/verification/tests/test_character_action_foundation_progressive_replacement.py`, `backend/tests/test_character_replica_convergence_static.py` |
| Compatibility | forwarding shell and old public surface | `scripts/character/CharacterReplica.gd`, `scenes/phase0/CharacterReplica.tscn`, `scripts/character/CharacterActor.gd` |
| Scene/player | scene roots, player bridge, shell sync | `scenes/phase0/CharacterBase.tscn`, `scenes/phase0/ValidationPlayerShell.tscn`, `scripts/player/Phase0PlayerBridge.gd`, `scripts/player/PlayerShell.gd`, `scripts/phase0/MainDemoController.gd` |
| Embodied/agent | providers, interaction hosts, execution ingress | `scripts/character/EmbodiedStateProvider.gd`, `scripts/character/EmbodiedSkeletalStateProvider.gd`, `scripts/interaction/ArchiveDoorEmbodiedActionHost.gd`, agent and Siming bridge callers discovered by Task 1 |
| Motion/assets | Motor ownership, root motion, registry admission | `scripts/character/CharacterMotor.gd`, `scripts/character/MotionContributionComposer.gd`, `scripts/character/RootMotionSampler.gd`, `scripts/character/CharacterEmbodimentAssetRegistry.gd`, active manifests |
| Authority/evidence | ActionAttempt, replay, probes, Harness metadata | `scripts/street_combat/StreetCombatCoordinator.gd`, `scripts/autoload/BackendBridge.gd`, backend authority modules, `scripts/verification/CharacterActionFoundationRuntimeProbe.gd` |

Each lane owns only its listed files plus files explicitly added by the caller inventory. Cross-lane interface changes require a focused test before implementation changes in the dependent lane.

## Task 1: Freeze the caller inventory and add retirement guards

**Files:**
- Create: `docs/character/character-replica-retirement-matrix-2026-09-29.md`
- Create: `.harness/profiles/character-replica-retirement.json`
- Create: `scripts/verification/verify_character_replica_retirement.py`
- Modify: `scripts/verification/CharacterReplicaRetirementProbe.gd`
- Modify: `scripts/verification/tests/test_character_action_foundation_progressive_replacement.py`
- Modify: `backend/tests/test_character_replica_convergence_static.py`
- Test: `scripts/verification/tests/test_character_action_foundation_progressive_replacement.py`

**Interfaces:**
- Consumes: repository paths, active `.tscn` sources, GDScript source text, current StreetCombatDemo baseline.
- Produces: a machine-readable caller matrix with `caller_path`, `category`, `current_state`, `target_entry`, `owner_lane`, `compatibility_allowed`, and `evidence_command` fields.

- [ ] **Step 1: Write the failing inventory assertions.**

Add tests that require every active `CharacterReplica` reference to appear in the matrix and reject a new runtime caller that is absent from the matrix. Keep the existing exception set limited to the compatibility shell, historical docs, and explicit migration tests.

- [ ] **Step 2: Run the focused guard tests and confirm the baseline failure.**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py
```

Expected: the new inventory assertions fail for at least the known `CharacterBase`, validation, provider, and integration references until the matrix is populated.

- [ ] **Step 3: Build the caller matrix from the repository.**

Record each match from `rg -n "CharacterReplica|CharacterReplica\.tscn|CharacterReplica\.gd" scenes scripts backend`, classify it into scene/player/embodied/interaction/agent or compatibility, and record the exact migration target and verification command in `docs/character/character-replica-retirement-matrix-2026-09-29.md`.

- [ ] **Step 4: Make `CharacterReplicaRetirementProbe.gd` consume the matrix.**

The probe must report active scene instances, runtime script references, provider lookups, direct movement writers, direct animation calls, compatibility call counts, and the list of unregistered callers. It must return `passed=false` when any active caller is missing from the matrix or any forbidden owner is found.

- [ ] **Step 5: Add a Harness profile for the retirement gate.**

Create `.harness/profiles/character-replica-retirement.json` with the existing profile schema, pointing to `scripts/verification/verify_character_replica_retirement.py`, requiring the matrix, the static caller tests, and a Godot marker from `CharacterReplicaRetirementProbe.inspect()`. The Python verifier must fail closed when the matrix, source digest, or Godot marker is missing.

- [ ] **Step 6: Run the focused guards and commit the baseline.**

Run the focused command again and commit only the inventory, probe, and tests:

```powershell
python scripts/verification/harness.py --profile character-replica-retirement
git add docs/character/character-replica-retirement-matrix-2026-09-29.md .harness/profiles/character-replica-retirement.json scripts/verification/verify_character_replica_retirement.py scripts/verification/CharacterReplicaRetirementProbe.gd scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py
git commit -m "test: freeze CharacterReplica retirement inventory"
```

## Task 2: Reduce `CharacterReplica` to a forwarding-only compatibility shell

**Files:**
- Modify: `scripts/character/CharacterReplica.gd`
- Modify: `scripts/character/CharacterActor.gd`
- Modify: `scripts/character/CharacterControlIntent.gd`
- Modify: `scripts/character/CharacterPresentationRuntime.gd`
- Create: `backend/tests/test_character_replica_forwarding_contract.py`
- Modify: `backend/tests/test_character_replica_convergence_static.py`

**Interfaces:**
- Consumes: `CharacterControlIntent.create/normalize`, `CharacterActor.submit_action_intent`, actor presentation methods, and the matrix from Task 1.
- Produces: compatibility methods that return the same public result shapes while emitting `compatibility_call` diagnostics with caller and actor identity.

- [ ] **Step 1: Pin the forwarding contract with failing tests.**

Add tests for `begin_embodied_control_frame`, `apply_embodied_pose_sync`, `perform_action`, `play_reviewed_action_atom`, `restore_reviewed_action_playback`, and `apply_presentation_asset_binding`. Each test must assert that the shell delegates to an actor-owned method, returns the actor result, and does not write `global_position`, `velocity`, animation playback, or authority state.

- [ ] **Step 2: Run the new contract tests before implementation.**

Run:

```powershell
python -m pytest -q backend/tests/test_character_replica_forwarding_contract.py backend/tests/test_character_replica_convergence_static.py
```

Expected: failures identify shell methods that still expose inherited behavior or lack structured compatibility diagnostics.

- [ ] **Step 3: Add actor-owned forwarding seams.**

Implement actor methods that accept normalized intent or presentation dictionaries. The shell must call those methods and only translate legacy arguments. Use this shape for legacy movement input:

```gdscript
var intent := CharacterControlIntentRef.normalize({
    "move_direction": move_direction,
    "wants_run": wants_run,
    "gait": gait_name,
    "stance": stance_name,
    "jump_type": jump_type,
    "source_kind": "compatibility",
    "actor_id": actor_id,
})
return apply_control_intent(intent)
```

The actor method must stage the intent for the arbiter; it must not let the shell call `move_and_slide` or directly mutate the body.

- [ ] **Step 4: Add strict compatibility diagnostics.**

Record `caller_path`, `method`, `actor_id`, `source_kind`, `intent_digest`, and `forwarded_to` for each compatibility call. In strict test mode, fail if a compatibility method performs a transform write, invokes an animation player directly, or appends an authority event.

- [ ] **Step 5: Run focused forwarding and ownership tests.**

Run:

```powershell
python -m pytest -q backend/tests/test_character_replica_forwarding_contract.py backend/tests/test_character_motor_ownership_audit.py backend/tests/test_character_action_foundation_progressive_replacement.py
```

- [ ] **Step 6: Commit the shell contraction.**

```powershell
git add scripts/character/CharacterReplica.gd scripts/character/CharacterActor.gd scripts/character/CharacterControlIntent.gd scripts/character/CharacterPresentationRuntime.gd backend/tests/test_character_replica_forwarding_contract.py backend/tests/test_character_replica_convergence_static.py
git commit -m "refactor: make CharacterReplica forwarding-only"
```

## Task 3: Migrate scene roots and player-facing callers

**Files:**
- Modify: `scenes/phase0/CharacterBase.tscn`
- Modify: `scenes/phase0/ValidationCharacterReplica.tscn`
- Modify: `scenes/phase0/ValidationPlayerShell.tscn`
- Modify: `scripts/player/Phase0PlayerBridge.gd`
- Modify: `scripts/player/PlayerShell.gd`
- Modify: `scripts/phase0/MainDemoController.gd`
- Modify: `backend/tests/test_character_scene_migration.py`
- Modify: `backend/tests/test_character_actor_scene_convergence_static.py`
- Test: `backend/tests/test_character_scene_migration.py`

**Interfaces:**
- Consumes: actor-owned intent/presentation methods from Task 2.
- Produces: player and scene paths whose concrete runtime type is `CharacterActor`, with old NodePaths and signals preserved only where a documented external probe still consumes them.

- [ ] **Step 1: Add failing scene and player migration assertions.**

Require `CharacterBase.tscn`, validation scenes, `Phase0PlayerBridge`, `PlayerShell`, and `MainDemoController` to resolve the actor host through `CharacterActor` or an interface method, and reject new direct `CharacterReplica` typed references.

- [ ] **Step 2: Run the scene migration tests and record failures.**

```powershell
python -m pytest -q backend/tests/test_character_scene_migration.py backend/tests/test_character_actor_scene_convergence_static.py
```

- [ ] **Step 3: Switch scene inheritance and node lookup to the actor host.**

Update scene instance references and script type checks so the node exposes the same external anchors while the instantiated script is `CharacterActor`. Preserve only the public signals and paths listed in the retirement matrix.

- [ ] **Step 4: Route player shell updates through `CharacterControlIntent`.**

Replace inline movement and pose writes in `Phase0PlayerBridge`, `PlayerShell`, and `MainDemoController` with actor calls that stage intent and presentation input. Keep camera and UI reads read-only.

- [ ] **Step 5: Run player and action-focused tests.**

```powershell
python -m pytest -q backend/tests/test_character_scene_migration.py backend/tests/test_character_actor_scene_convergence_static.py backend/tests/test_character_controller_boundary_static.py backend/tests/test_action_window_godot_contract.py
```

- [ ] **Step 6: Commit the scene/player migration.**

```powershell
git add scenes/phase0/CharacterBase.tscn scenes/phase0/ValidationCharacterReplica.tscn scenes/phase0/ValidationPlayerShell.tscn scripts/player/Phase0PlayerBridge.gd scripts/player/PlayerShell.gd scripts/phase0/MainDemoController.gd backend/tests/test_character_scene_migration.py backend/tests/test_character_actor_scene_convergence_static.py
git commit -m "refactor: migrate scene and player callers to CharacterActor"
```

## Task 4: Migrate embodied, interaction, agent, and Siming callers

**Files:**
- Modify: `scripts/character/EmbodiedStateProvider.gd`
- Modify: `scripts/character/EmbodiedSkeletalStateProvider.gd`
- Modify: `scripts/interaction/ArchiveDoorEmbodiedActionHost.gd`
- Modify: active Agent/Siming execution callers listed in the Task 1 matrix
- Modify: corresponding static and runtime backend tests
- Create: `scripts/verification/CharacterActorCallerMigrationProbe.gd`

**Interfaces:**
- Consumes: actor intent, presentation, and compatibility diagnostics from Tasks 2–3.
- Produces: embodied and autonomous paths that address `CharacterActor` through an interface or actor group, never by concrete Replica lookup.

- [ ] **Step 1: Add failing provider and interaction assertions.**

Assert that providers resolve an actor host without `get_node`/type checks for `CharacterReplica`, that ArchiveDoor physical attempts use the actor body and authority result, and that agent execution enters through the same actor ingress as player intent.

- [ ] **Step 2: Run the affected focused tests before migration.**

```powershell
python -m pytest -q backend/tests/test_verification_audit.py backend/tests/test_visual_fact_pipeline.py backend/tests/test_obj_archive_door_embodied_authority.py backend/tests/test_obj_archive_door_embodied_godot_static.py backend/tests/test_character_actor_reacquisition_runtime.py
```

- [ ] **Step 3: Replace Replica lookups with actor capability lookups.**

Use a narrow capability interface: resolve the node, require `apply_control_intent`, `get_focus_anchor_position`, `get_embodied_forward_vector`, and the required presentation/interaction methods, then fail closed with a typed reason when a capability is absent.

- [ ] **Step 4: Route embodied and autonomous input into semantic intent.**

Convert approach, speak, interact, perception-driven movement, and agent execution payloads into `CharacterControlIntent` with `source_kind` set to `agent`, `program`, or `compatibility`. Do not add low-level pose fields or authority fields to the intent.

- [ ] **Step 5: Add the caller migration probe.**

The probe must enumerate live actor nodes, report concrete Replica instances, provider lookups, compatibility calls, and the ingress source for each embodied attempt. It must distinguish a compatibility call from a concrete Replica dependency.

- [ ] **Step 6: Run the embodied and agent gates.**

```powershell
python -m pytest -q backend/tests/test_verification_audit.py backend/tests/test_visual_fact_pipeline.py backend/tests/test_obj_archive_door_embodied_authority.py backend/tests/test_obj_archive_door_embodied_godot_static.py backend/tests/test_character_actor_reacquisition_runtime.py
python scripts/verification/harness.py --profile character-agent-execution
```

- [ ] **Step 7: Commit the embodied and agent migration.**

```powershell
git add scripts/character/EmbodiedStateProvider.gd scripts/character/EmbodiedSkeletalStateProvider.gd scripts/interaction/ArchiveDoorEmbodiedActionHost.gd scripts/verification/CharacterActorCallerMigrationProbe.gd backend/tests
git commit -m "refactor: migrate embodied and autonomous callers to CharacterActor"
```

## Task 5: Finish Motor ownership, root-motion qualification, and registry admission

**Files:**
- Modify: `scripts/character/CharacterMotor.gd`
- Modify: `scripts/character/MotionContributionComposer.gd`
- Modify: `scripts/character/RootMotionSampler.gd`
- Modify: `scripts/character/CharacterActor.gd`
- Modify: `scripts/character/CharacterEmbodimentAssetRegistry.gd`
- Modify: `scripts/street_combat/StreetCharacterSkin.gd`
- Modify: `assets/active/female_bandage_external/manifest.json`
- Modify: `assets/active/female_jk_external/manifest.json`
- Modify: `assets/active/female_t_external/manifest.json`
- Create or modify: `scripts/verification/RootMotionQualificationProbe.gd`
- Create or modify: `scripts/verification/CharacterMotorOwnershipProbe.gd`
- Modify: `backend/tests/test_root_motion_contract_static.py`
- Create: `backend/tests/test_character_asset_admission_runtime.py`

**Interfaces:**
- Consumes: normalized intent and actor caller migration from Tasks 2–4.
- Produces: exactly one physics command and one root consumption token per actor/tick, plus registry-qualified action packages with explicit root policy.

- [ ] **Step 1: Pin root and Motor failure cases.**

Add tests for missing profile, zero envelope, malformed delta, stale token, duplicate consumption, lease-plus-root double application, wall collision, slope, stop/restart, and lost support. Add a static assertion that only `CharacterMotor.gd` contains `move_and_slide(` and direct body transform writes.

- [ ] **Step 2: Run the root and ownership tests before implementation.**

```powershell
python -m pytest -q backend/tests/test_root_motion_contract_static.py backend/tests/test_character_motor_ownership_audit.py backend/tests/test_character_locomotion_motor_ownership_guard_static.py
```

- [ ] **Step 3: Implement one composed physics command.**

`MotionContributionComposer` must return a typed dictionary containing `actor_id`, `physics_tick`, `move_local`, `root_delta_local`, `root_policy`, `consumption_token`, and `source_digest`. `CharacterMotor` consumes it once, applies facing/gravity/collision, and emits the post-collision observation.

- [ ] **Step 4: Replace temporary root policies only after measured qualification.**

`RootMotionQualificationProbe.gd` must measure local forward axis, distance, cadence, envelope, and support conditions from the actual imported package. Update a manifest only when the probe and backend contract test accept the measured profile; otherwise keep `hold` and return a typed rejection.

- [ ] **Step 5: Enforce Registry-only admission.**

Reject unknown package, digest mismatch, missing skeleton mapping, missing marker, invalid root profile, and raw clip lookup. Record `package_id`, `manifest_digest`, `action_id`, `root_policy`, `fallback_mode`, and `rejection_reason`.

- [ ] **Step 6: Run the motion and asset gates.**

```powershell
python -m pytest -q backend/tests/test_root_motion_contract_static.py backend/tests/test_character_motor_ownership_audit.py backend/tests/test_character_locomotion_motor_ownership_guard_static.py backend/tests/test_character_asset_admission_runtime.py
python scripts/verification/harness.py --profile street-combat
```

- [ ] **Step 7: Commit the Motor, root, and Registry closure.**

```powershell
git add scripts/character/CharacterMotor.gd scripts/character/MotionContributionComposer.gd scripts/character/RootMotionSampler.gd scripts/character/CharacterActor.gd scripts/character/CharacterEmbodimentAssetRegistry.gd scripts/street_combat/StreetCharacterSkin.gd assets/active backend/tests scripts/verification
git commit -m "feat: close global Motor root-motion and registry ownership"
```

## Task 6: Close generic ActionAttempt authority and Mode B recovery

**Files:**
- Modify: `scripts/street_combat/StreetCombatCoordinator.gd`
- Modify: `scripts/autoload/BackendBridge.gd`
- Modify: existing backend ESM/Gameplay/Composite action route modules identified by the current authority tests
- Create: `backend/tests/test_character_action_attempt_closure.py`
- Create: `scripts/verification/StreetActionAttemptProbe.gd`

**Interfaces:**
- Consumes: actor action admission, Motor contact evidence, and registry action descriptors from Tasks 2 and 5.
- Produces: one typed ActionAttempt request with idempotency, expected revision, connection epoch, client sequence, physics tick, causation, correlation, and recovery evidence.

- [ ] **Step 1: Write failing authority closure tests.**

Cover accepted hit, duplicate replay, changed duplicate rejection, stale revision zero-write, missing contact evidence, disconnected transport, reconnect snapshot, stale epoch rejection, and recovery only after the new epoch is accepted.

- [ ] **Step 2: Run the authority tests before implementation.**

```powershell
python -m pytest -q backend/tests/test_character_action_attempt_closure.py backend/tests/test_ws_protocol.py backend/tests/test_obj_archive_door_embodied_authority.py
```

- [ ] **Step 3: Build the typed request from actor evidence.**

The coordinator must collect the arbiter result, Motor contact observation, action descriptor digest, and target identity. It must never derive a committed hit from local animation or HUD state.

- [ ] **Step 4: Add duplicate, stale, and reconnect fences.**

Bind each request to `connection_epoch`, `client_sequence`, `physics_tick`, `causation_id`, and `correlation_id`. Reject old epochs before authority submission; after reconnect require a fresh snapshot and resync marker before accepting a new attempt.

- [ ] **Step 5: Add the runtime probe and replay comparison.**

`StreetActionAttemptProbe.gd` must write accepted, duplicate, stale, disconnected, reconnect, and recovery markers for player and agent actions. The verifier compares request digest, authority result, projection digest, and event identity across replay.

- [ ] **Step 6: Run the authority and StreetCombat gates.**

```powershell
python -m pytest -q backend/tests/test_character_action_attempt_closure.py backend/tests/test_ws_protocol.py backend/tests/test_character_action_foundation_progressive_replacement.py
python scripts/verification/harness.py --profile street-combat
```

- [ ] **Step 7: Commit the authority closure.**

```powershell
git add scripts/street_combat/StreetCombatCoordinator.gd scripts/autoload/BackendBridge.gd scripts/verification/StreetActionAttemptProbe.gd backend/tests
git commit -m "feat: close semantic ActionAttempt and Mode B recovery"
```

## Task 7: Prove zero active Replica callers and switch all scenes to actor-only

**Files:**
- Modify: all remaining active files listed by the Task 1 matrix
- Modify: `scripts/verification/CharacterReplicaRetirementProbe.gd`
- Modify: `docs/character/character-replica-convergence.md`
- Create: `docs/character/character-replica-retirement-report-2026-09-29.md`
- Modify: `backend/tests/test_character_replica_convergence_static.py`
- Modify: `backend/tests/test_character_actor_boundary_audit.py`

**Interfaces:**
- Consumes: completed migrations from Tasks 2–6.
- Produces: a zero-caller report proving no active scene, provider, bridge, interaction host, agent path, or verifier depends on concrete `CharacterReplica` behavior.

- [ ] **Step 1: Add the zero-caller failing gate.**

Require the report to contain `active_scene_instances=0`, `runtime_replica_lookups=0`, `compatibility_call_count=0`, `direct_body_writers_outside_motor=0`, and `direct_animation_writers_outside_controller=0`.

- [ ] **Step 2: Run the retirement profile and record all remaining references.**

```powershell
python scripts/verification/harness.py --profile character-replica-retirement
python -m pytest -q backend/tests/test_character_replica_convergence_static.py backend/tests/test_character_actor_boundary_audit.py
```

Use the exported profile report to drive the final caller edits. Do not delete the shell while any active reference remains.

- [ ] **Step 3: Switch the remaining scene and script references.**

Replace each runtime reference with `CharacterActor` or a narrow capability interface. Keep historical documentation references only when the file is explicitly marked historical/transitional.

- [ ] **Step 4: Run actor-only StreetCombatDemo and Phase 0 probes.**

```powershell
python scripts/verification/harness.py --profile street-combat
python scripts/verification/harness.py --profile character-agent-execution
python scripts/verification/harness.py --profile phase0
```

- [ ] **Step 5: Write and verify the retirement report.**

The report must list every previous caller, its target actor entry point, the evidence command, and the final state `retired`. It must include the exact source digest used by the probe.

- [ ] **Step 6: Commit the actor-only switch.**

```powershell
git add scenes scripts backend/tests docs/character/character-replica-convergence.md docs/character/character-replica-retirement-report-2026-09-29.md
git commit -m "refactor: complete actor-only CharacterReplica migration"
```

## Task 8: Delete the compatibility shell and update the documentation gates

**Files:**
- Delete: `scripts/character/CharacterReplica.gd`
- Delete: `scenes/phase0/CharacterReplica.tscn`
- Delete: `scenes/phase0/ValidationCharacterReplica.tscn` when the matrix proves no active consumer remains
- Modify: `docs/character/action-foundation-series-status.md`
- Modify: `docs/character/character-action-foundation-current-state.md`
- Modify: `docs/character/character-action-foundation-operator-guide-and-index.md`
- Modify: `docs/character/character-replica-convergence.md`
- Modify: `docs/character/character-debug-and-verification.md`
- Modify: `docs/INDEX.md`
- Modify: relevant Harness profile metadata
- Test: `scripts/verification/tests/test_docs_checks.py`, `scripts/verification/tests/test_street_combat_verifier.py`

**Interfaces:**
- Consumes: zero-caller retirement report and all runtime evidence from Tasks 1–7.
- Produces: an actor-only repository with no compatibility runtime dependency and documentation that points to the new spec and plan as the sole execution source.

- [ ] **Step 1: Add failing deletion guards.**

Assert that no active source, scene, profile, or verification entry imports `CharacterReplica.gd` or instantiates `CharacterReplica.tscn`. Keep only explicitly historical references in documentation.

- [ ] **Step 2: Run the deletion guards before removing files.**

```powershell
python -m pytest -q backend/tests/test_character_replica_convergence_static.py scripts/verification/tests/test_docs_checks.py
```

- [ ] **Step 3: Delete the shell and obsolete scene assets.**

Remove only the files listed in the zero-caller report. If a validation scene still serves an independent contract, migrate its root to `CharacterActor` before deletion rather than preserving a second Replica path.

- [ ] **Step 4: Reconcile documentation and profile metadata.**

Mark StreetCombatDemo as a pilot that is now subsumed by the global actor-only closure. Update the current-state and operator documents to state that `CharacterReplica` is retired, and link this spec and plan as the only active execution references.

- [ ] **Step 5: Run documentation and focused action checks.**

```powershell
python -m pytest -q scripts/verification/tests/test_docs_checks.py scripts/verification/tests/test_street_combat_verifier.py scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py
git diff --check
```

- [ ] **Step 6: Commit compatibility-shell deletion.**

```powershell
git add -A scripts/character/CharacterReplica.gd scenes/phase0/CharacterReplica.tscn scenes/phase0/ValidationCharacterReplica.tscn docs .harness backend/tests scripts/verification
git commit -m "refactor: retire CharacterReplica compatibility shell"
```

## Task 9: Run the repository-wide closure gates and publish evidence

**Files:**
- Modify: `docs/character/action-foundation-series-status.md`
- Modify: `docs/character/character-action-foundation-current-state.md`
- Modify: `docs/character/character-replica-retirement-report-2026-09-29.md`
- Export outside repository: fresh Harness evidence directory selected by the run

**Interfaces:**
- Consumes: actor-only source tree, retirement report, runtime probes, and all focused test evidence.
- Produces: a fresh, source-bound closure matrix that either proves completion or records exact remaining blockers without overclaiming.

- [ ] **Step 1: Run the focused action-foundation suite.**

```powershell
python -m pytest -q scripts/verification/tests/test_character_action_foundation_progressive_replacement.py backend/tests/test_character_replica_convergence_static.py backend/tests/test_character_motor_ownership_audit.py backend/tests/test_root_motion_contract_static.py backend/tests/test_character_asset_admission_runtime.py backend/tests/test_character_action_attempt_closure.py
```

- [ ] **Step 2: Run the runtime profiles with an explicit Godot executable.**

```powershell
$env:GODOT_EXE='D:\godot\Godot_v4.6.3-stable_win64.exe'
python scripts/verification/harness.py --profile street-combat --export-evidence D:\CurrentActionFoundationEvidence-street
python scripts/verification/harness.py --profile character-agent-execution --export-evidence D:\CurrentActionFoundationEvidence-agent
```

- [ ] **Step 3: Run the complete repository gates.**

```powershell
python -m pytest -v
python scripts/verification/harness.py --profile all --export-evidence D:\CurrentActionFoundationEvidence-all
```

The completion claim is blocked if either command exits nonzero, if a fresh report is missing, or if cleanup fails.

- [ ] **Step 4: Reconcile status documents from fresh evidence.**

Record exact collection/pass/fail counts, profile statuses, evidence paths, source digests, and remaining risks. A green StreetCombatDemo result must not be used to mask a red repository-wide gate.

- [ ] **Step 5: Run final integrity checks and commit the evidence metadata.**

```powershell
git diff --check
git status --short -- .harness
python -m pytest -q scripts/verification/tests/test_docs_checks.py scripts/verification/tests/test_drift_checks.py
git add docs/character/action-foundation-series-status.md docs/character/character-action-foundation-current-state.md docs/character/character-replica-retirement-report-2026-09-29.md
git commit -m "docs: publish global action foundation closure evidence"
```

## Final Completion Gate

The plan is complete only when all of the following are backed by fresh evidence from the same source state:

1. No active scene, script, provider, bridge, interaction host, agent path, or verifier depends on `CharacterReplica`.
2. `CharacterMotor` is the only body movement owner and `RoleAnimationController` is the only action-state owner.
3. Root-motion profiles are measured, qualified, bounded, and consumed exactly once by Motor.
4. Registry admission, ActionAttempt authority, duplicate/stale handling, reconnect, recovery, and replay are closed.
5. Focused tests, full pytest, `street-combat`, and `all` Harness profiles pass.
6. The final status documents say `CharacterReplica retired` and identify this spec/plan as the active source of truth.

If any condition fails, the status remains blocked and the exact failure is retained as an open gate; no partial pilot is promoted to a global replacement claim.
