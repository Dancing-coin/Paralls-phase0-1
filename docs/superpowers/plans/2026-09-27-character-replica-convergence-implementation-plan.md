# CharacterReplica Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 `CharacterReplica` 从混合职责脚本收敛为兼容入口，把角色编排、物理移动、动作树、根运动采样和外部角色皮肤分成明确职责，同时保持现有后端/场景调用可运行。

**Architecture:** `CharacterActor.gd` 保留 actor identity、后端事件、意图编排和兼容 API；`CharacterReplica.gd` 只作为旧场景与旧调用方的薄兼容类。`CharacterMotor` 是唯一的速度、重力、朝向、碰撞、根运动合成和 `move_and_slide()` owner。`RoleAnimationController` 管理外部 controller 风格的 AnimationTree/AnimationPlayer 状态；`RootMotionSampler` 只采样动画根骨 delta，不直接写 body；`StreetCharacterSkin` 负责资源绑定和动作树适配。

**Tech Stack:** Godot 4.x GDScript, CharacterBody3D, AnimationPlayer/AnimationTree, Skeleton3D, imported GLB, pytest, Godot headless probes.

**Spec:** `docs/superpowers/plans/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-implementation-plan.md`, `docs/superpowers/specs/2026-09-14-character-physics-motion-and-contact-subspec.md`.

## Global Constraints

- CharacterMotor remains the sole normal owner of baseline displacement and `move_and_slide()`.
- Godot owns local embodiment and presentation; backend/ESM remains authority for world consequences.
- Root motion is a motion contribution consumed by CharacterMotor and must not be added on top of equivalent locomotion velocity.
- Existing `CharacterReplica` scene and public methods remain compatible during this convergence.
- Real street GLB characters, not the greybox scene, are the action quality acceptance surface.

## Review Focus

- Existing callers must still find the public embodied control and action methods.
- Animation clips must loop for idle/walk/run and remain one-shot for jump/attack.
- Root motion must be sampled from the animation asset and consumed once by Motor.
- No skin, actor host, or controller may add a second `move_and_slide()` or direct body transform writer.
- Missing AnimationTree or missing clip must degrade to AnimationPlayer/idle without crashing.

### Task 1: Preserve and split the actor host

**Files:**
- Create: `scripts/character/CharacterActor.gd`
- Modify: `scripts/character/CharacterReplica.gd`
- Modify: `scenes/phase0/CharacterReplica.tscn`

Copy the current actor implementation into `CharacterActor.gd`, give it `class_name CharacterActor`, and keep its public methods. Replace `CharacterReplica.gd` with a compatibility subclass and explicit forwarding declarations for existing public methods/static contract probes. Keep the scene root name and CharacterBody3D shape unchanged.

### Task 2: Add animation and root-motion components

**Files:**
- Create: `scripts/character/RoleAnimationController.gd`
- Create: `scripts/character/RootMotionSampler.gd`
- Modify: `scripts/character/CharacterActor.gd`
- Modify: `scripts/character/CharacterReplica.gd`

Implement controller states `idle`, `walk`, `run`, `jump`, `boxing`, `sword_attack`, with cross-fade and action lock. Implement root sampler that reads `rig/Skeleton3D:root` tracks, returns local delta once, and supports reset. Actor delegates role state and root delta to these components while retaining old skin APIs.

### Task 3: Make CharacterMotor the single motion owner

**Files:**
- Modify: `scripts/character/CharacterMotor.gd`
- Modify: `scripts/character/CharacterActor.gd`
- Modify: `scripts/character/MotionContributionComposer.gd`

Add explicit root-motion policy metadata and prevent locomotion velocity plus identical root delta from being applied twice. Actor only creates commands; Motor applies facing, gravity, collision, root delta and velocity. Preserve current intent-frame compatibility route.

### Task 4: Integrate external street skins cleanly

**Files:**
- Modify: `scripts/street_combat/StreetCharacterSkin.gd`
- Modify: `scenes/phase0/CharacterReplica.tscn`
- Modify: `scenes/phase0/StreetCombatDemo.tscn`

Bind the skin to `RoleAnimationController` and `RootMotionSampler`, keep manifest alias resolution, loop locomotion clips, one-shot action clips, and expose clip/action diagnostics. Keep the real three imported GLB characters as the runtime surface.

### Task 5: Add verification and documentation

**Files:**
- Create: `scripts/verification/CharacterReplicaConvergenceProbe.gd`
- Create: `backend/tests/test_character_replica_convergence_static.py`
- Create: `docs/character/character-replica-convergence.md`

Probe actor loading, skeleton binding, animation state transitions, action recovery, root-motion single consumption, collision ownership, and compatibility methods. Run targeted pytest, Godot headless street probe, and backend pytest.

## Completion Evidence

- Backup exists outside the repository and contains all replaced character files.
- Targeted static tests pass.
- StreetCombatDemo headless probe reports three qualified skeletons, looping locomotion, one-shot action recovery, and no second movement owner.
- `python -m pytest -v` passes or any unrelated baseline failures are explicitly reported.
