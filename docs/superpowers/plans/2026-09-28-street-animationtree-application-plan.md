# StreetCombatDemo AnimationTree Application Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make all three real StreetCombatDemo characters use the external-controller-style AnimationTree state machine for locomotion, guard, jump, punch, and sword actions, with diagnostic evidence from the real scene.

**Architecture:** `RoleAnimationController` owns the generated AnimationTree state machine, playback locks, held guard poses, and diagnostics. `StreetCharacterSkin` resolves manifest clips and exposes explicit locomotion/action APIs while keeping `set_state` as compatibility. `StreetCombatDemo` calls those explicit APIs; `CharacterMotor` remains the only body movement owner.

**Tech Stack:** Godot 4.6 GDScript, AnimationPlayer, AnimationTree, AnimationNodeStateMachine, real imported GLB skins, headless Godot probe.

## Global Constraints

- The three real imported street GLBs remain the acceptance surface.
- `CharacterMotor` remains the sole `move_and_slide()` and body displacement owner.
- `StreetCharacterSkin` never directly plays or pauses `AnimationPlayer` for gameplay state changes.
- AnimationTree state names are `idle`, `walk`, `run`, `jump`, `boxing`, and `sword_attack`.
- Missing optional clips must fail safely without breaking scene startup.

## Tasks

### Task 1: Harden the controller

Modify `scripts/character/RoleAnimationController.gd` to expose active-tree/playback diagnostics, map action clips to the correct state, and implement controller-owned held poses using speed zero rather than skin-level AnimationPlayer takeover.

### Task 2: Make the street skin use controller APIs

Modify `scripts/street_combat/StreetCharacterSkin.gd` to add explicit locomotion/action methods, route all compatibility calls through them, map punch and sword clips to their correct state, and route guard stance through the controller hold API.

### Task 3: Make StreetCombatDemo explicit

Modify `scripts/street_combat/StreetCombatDemo.gd` so player locomotion and jump call the skin's explicit state methods. Keep coordinator-driven combat actions flowing through the same skin/controller path.

### Task 4: Verify the real scene

Extend `scripts/verification/CharacterReplicaConvergenceProbe.gd` to assert three active AnimationTrees, correct playback states for locomotion/action/guard, action recovery, root-track qualification, movement, and collision walls. Run targeted static tests, Godot headless probe, and `git diff --check`.
