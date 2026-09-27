# Phase 0 Gate Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the remaining `harness --profile all` Phase 0 gate without weakening evidence requirements or changing backend authority boundaries.

**Architecture:** Keep Godot authoritative only for local presentation and probes. Make procedural fallback skins expose a bounded root-motion increment, let `CharacterReplica` audit the consumed increment, and make the observatory probe issue requests through the existing MainDemo controller using runtime-valid affordances. Preserve the existing audit predicates and require fresh runtime evidence.

**Tech Stack:** Godot 4.6 GDScript, Python verification scripts, pytest, repository Harness.

**Spec:** `docs/superpowers/plans/2026-09-23-character-turn-continuity-and-embodied-episode-implementation-plan.md`

## Global Constraints

- Godot owns local embodiment/presentation only; backend remains world-truth authority.
- Do not weaken `verify_phase0.py` predicates or mark missing evidence as proved.
- Use existing scene affordance and BackendBridge paths; do not add a parallel transport.
- Preserve all unrelated dirty worktree changes.

## Review Focus

- Procedural fallback root motion must be bounded, deterministic, and consumed by the controller before physics application.
- NPC audit markers must be emitted only after a non-zero root-motion delta is actually admitted.
- Observatory requests must use the existing runtime-valid object/interaction contract and produce backend state events.
- Player root-motion evidence must remain a runtime observation, not a static source claim.

### Task 1: Diagnose and prove probe call paths

**Files:** `scripts/verification/CharacterDirectorObservatoryProbe.gd`, `scripts/phase0/MainDemoController.gd`

- [x] Add temporary probe prints for method availability, target IDs, affordance resolution, and request descriptors.
- [x] Run `verify_character_director_observatory.py` and inspect the fresh log.
- [x] Remove diagnostics that are not needed for the final evidence, retaining only stable audit markers.

### Task 2: Emit bounded fallback root-motion increments

**Files:** `scripts/character/GenericRoleSkin.gd`, `scripts/character/CharacterReplica.gd`, `backend/tests/test_verification_audit.py`

- [x] Add a failing static/runtime contract test for a non-zero walk-profile fallback increment and the patrol audit marker.
- [x] Accumulate a small forward delta in `GenericRoleSkin` only while a locomotion profile is active; clear it through `reset_root_motion`.
- [x] Log `patrol_root_motion_step:<actor_id>` only when the admitted command contains a non-zero NPC root delta.
- [x] Run focused tests and the Phase 0 probe.

### Task 3: Restore observatory runtime state evidence

**Files:** `scripts/verification/CharacterDirectorObservatoryProbe.gd`, `scripts/verification/tests/test_character_agent_execution_probe_static.py`

- [x] Use the existing controller's valid target/interaction resolution instead of assuming a stale target path.
- [x] Send dialogue and inspect requests only after `BackendBridge.is_backend_open()` is true; wait for world outcome and script beat signals.
- [x] Require the state center arrays to be non-empty and retain the existing `state_payloads_ok=true` marker.
- [x] Run the observatory verifier and its static tests.

### Task 4: Verify and close the aggregate gate

**Files:** `.harness/verification/` artifacts only

- [x] Run focused pytest for modified contracts.
- [x] Run `verify_phase0.py` with the real Godot executable.
- [x] Run `harness.py --profile all` with the real Godot and Python executables.
- [x] Report remaining profile failures verbatim if aggregate exit code is non-zero.
