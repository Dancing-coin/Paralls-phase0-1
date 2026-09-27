# Street Combat Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a playable Godot street combat scene with the art repository's city environment, exactly the user's three qualified characters, backend settled combat, and live verification.

**Architecture:** A new `StreetCombatDemo.tscn` owns only presentation and input. It stages `citystreets_209/0.3.0` and mounts the three existing character packages into `CharacterReplica`; an action adapter translates semantic actions to local animations, while the existing Python settlement service owns outcomes. `MainDemo.tscn` remains available for Phase 0 verification.

**Tech Stack:** Godot 4.6 GDScript and scenes, Python FastAPI/WebSocket, pytest, repository harness.

**Spec:** `docs/superpowers/specs/2026-09-26-street-combat-demo-design.md`

## Global Constraints

- Environment: `citystreets_209/0.3.0` environment, collision, navigation only; do not bring the art repository's characters.
- Characters: `female_jk_external`, `female_t_external`, `female_bandage_external` from this Godot repository only.
- Preserve `scenes/phase0/MainDemo.tscn`, `.blend`, Task 8 qualification, and `session_store`.
- Godot owns local input, motor and animation; backend ESM/Gameplay owns results.
- No second scheduler, authority writer, cross-boundary raw clips, or Mode C.
- Store fresh runtime evidence under `.harness/verification/`; run `python scripts/verification/harness.py --profile all` before claiming release closure.

## Review Focus

- Missing or changed art pack files must fail staging validation before opening the scene; Task 1 tests hashes and file presence.
- A damaged art character must never become a scene fallback; Task 2 tests exactly the three local package paths.
- Unqualified skeleton mapping or missing action clip must fail the live probe; Task 3 tests each package's bones and required animations.
- A delayed or duplicate backend result must update the HUD once and preserve attempt ID; Task 4 tests result correlation and replay.
- Backend disconnect must leave combat pending or visibly unavailable, without local damage; Task 4 tests disconnect behavior.

---

### Task 1: Stage the Street Environment

**Files:**
- Create: `assets/active/citystreets_209/0.3.0/environment.glb`, `collision.glb`, `navigation.glb`, `manifest.json`, `metadata/anchors.json`, `metadata/navigation.json`, `scene-binding.md`.
- Create: `scripts/verification/tests/test_street_combat_assets.py`.

**Interfaces:** Consumes the art export at `D:/Users/User/Documents/paralls-art-assets/exports/citystreets_209/0.3.0`. Produces versioned `res://assets/active/citystreets_209/0.3.0/*.glb` scene resources and manifest.

- [ ] Write a failing Python test that opens the staged manifest, confirms pack/version, confirms all three GLBs exist, compares SHA256 digests with source, and rejects any scene reference to an art character.
- [ ] Run `python -m pytest scripts/verification/tests/test_street_combat_assets.py -v` and record expected missing-asset failure.
- [ ] Copy only the named environment files and required metadata; preserve source manifest fields and add source digest evidence without modifying source files.
- [ ] Rerun the focused test and inspect Godot import diagnostics.

### Task 2: Build the Playable Scene Shell

**Files:**
- Create: `scenes/phase0/StreetCombatDemo.tscn`.
- Create: `scripts/street_combat/StreetCombatDemo.gd`.
- Modify: `project.godot` main scene path.
- Test: `scripts/verification/tests/test_street_combat_scene.py`.

**Interfaces:** Consumes Task 1 GLBs and the three local `CharacterReplica.tscn` instances. Produces named `PlayerCharacter`, `AgentCharacterJK`, `AgentCharacterT`, camera, environment, collision, navigation and HUD anchors.

- [ ] Write a failing scene test asserting new main scene, all three staged environment resources, exactly the three local character GLBs, and no voxel character reference.
- [ ] Run that test and confirm it fails for missing scene.
- [ ] Add the scene with spawn coordinates converted from art Z-up to Godot Y-up, visible lighting/camera, collision and navigation host, and character capsules.
- [ ] Run the scene test and a headless Godot import/scene load; record any asset import errors.

### Task 3: Bind Real Skeleton Animation

**Files:**
- Create: `scripts/street_combat/StreetCharacterSkin.gd` and local adapter scenes as needed under `scenes/phase0/`.
- Modify: `scenes/phase0/StreetCombatDemo.tscn`.
- Test: `scripts/verification/StreetCombatProbe.gd` and `scripts/verification/tests/test_street_combat_scene.py`.

**Interfaces:** Consumes each package manifest's `canonical_mapping`, `clip_aliases`, and `actions`; exposes `configure_role`, `set_motion_profile`, `play_qualified_profile`, `get_current_clip_name`, and `consume_root_motion_delta` to `CharacterReplica`.

- [ ] Add a failing live probe for imported skeleton bones, idle/walk/attack/hit/attention playback markers for all three packages.
- [ ] Run Godot probe and observe the missing binding marker.
- [ ] Add a thin shared skin adapter around each imported GLB; resolve AnimationPlayer and Skeleton3D dynamically and fail closed on missing bones/clips.
- [ ] Rerun live probe and focused package qualification checks.

### Task 4: Wire Player and Agent Combat Through Authority

**Files:**
- Modify: `scripts/street_combat/StreetCombatDemo.gd`.
- Create: `scripts/street_combat/StreetCombatCoordinator.gd`.
- Modify: `backend/app/main.py` only if the existing settlement probe route cannot be promoted to a proper combat request route.
- Test: `backend/tests/test_street_combat_transport.py`, `scripts/verification/StreetCombatProbe.gd`.

**Interfaces:** Consumes input, character-agent execution payloads and the backend's `ActionAttempt` settlement. Produces correlated `street_combat_result` payloads for HUD and local presentation; only backend result may alter combat state.

- [ ] Write failing backend transport tests for real request/result lineage, valid melee, out-of-range rejection, duplicate replay, stale rejection, and recovery.
- [ ] Run the focused backend tests and capture the expected missing route/contract failure.
- [ ] Implement the smallest WebSocket route using the existing settlement service; implement Godot request correlation, player controls, agent intent consumption, result presentation, and disconnect handling.
- [ ] Rerun backend tests and live probe, including both player and agent attempts.

### Task 5: Build the Combat HUD

**Files:**
- Create: `scenes/phase0/StreetCombatHUD.tscn`, `scripts/street_combat/StreetCombatHUD.gd`.
- Modify: `scenes/phase0/StreetCombatDemo.tscn`.
- Test: `scripts/verification/StreetCombatProbe.gd`.

**Interfaces:** Consumes coordinator state and correlated backend results. Displays player status, target/distance, three actor states, combat feed and agent intent; never writes world authority.

- [ ] Extend live probe with failing HUD assertions for target, three actor entries, request ID, hit/rejection and agent intent.
- [ ] Run probe and observe the missing HUD assertion.
- [ ] Add accessible high-contrast HUD with controls, state bars, target status and event feed; bind to coordinator signals.
- [ ] Rerun live probe and inspect a rendered screenshot.

### Task 6: Verification and Release Gate

**Files:**
- Create: `scripts/verification/verify_street_combat.py`.
- Create: `.harness/profiles/street-combat.json`.
- Modify: `docs/harness.md`.

**Interfaces:** Produces `.harness/verification/street-combat-runtime.json` from a fresh backend and Godot scene run. The harness profile fails on missing live markers.

- [ ] Add a failing verifier test for the required runtime evidence fields and profile registration.
- [ ] Run the focused test to prove absence is detected.
- [ ] Implement fresh backend launch, Godot probe, JSON evidence checks and profile registration.
- [ ] Run `python scripts/verification/verify_street_combat.py`, then fresh Phase 0 twice, then `python scripts/verification/harness.py --profile street-combat` and `python scripts/verification/harness.py --profile all`.
- [ ] Diagnose and fix any new profile failures with a red/green regression test; report an unresolved failure as a release blocker.
