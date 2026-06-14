# Character Actor Architecture Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optimize the current six-layer `CharacterActor` stack into a clearer, more modular, and more generalizable architecture while keeping the Phase 0 demo runnable and preserving shared actor-substrate semantics across traveler, agent player, and NPC roles.

**Architecture:** Use a dual-target approach. Freeze one new active-truth architecture spec that defines both the near-term demo-safe target and the mid-term Phase1-facing target. Execute only the near-term target in this plan: clarify the six layers, separate control source from product identity, freeze actor/presentation/asset contracts, converge code ownership, and add developer/asset integration documentation.

**Tech Stack:** Godot scenes, GDScript, FastAPI websocket backend, pytest, harness verification, existing Character Actor specs/plans, project docs index.

---

### Task 1: Freeze The New Active Architecture Truth

**Files:**
- Create: `docs/superpowers/specs/2026-06-15-character-actor-architecture-optimization-design.md`
- Modify: `docs/INDEX.md`
- Modify: `docs/superpowers/specs/2026-06-12-character-actor-unification-design.md` only if a forward reference is needed

- [ ] **Step 1: Verify the new optimization spec exists and is the intended new top-level architecture truth**

Run:

```powershell
Get-Content docs\superpowers\specs\2026-06-15-character-actor-architecture-optimization-design.md
```

Expected: the spec defines:

```text
- product identity vs runtime control mode
- formal six-layer actor stack
- physics/root-motion hybrid policy
- asset binding contracts
- near-term vs mid-term target architecture
- ControlMode transition semantics
- AssetCompatibilityLevel
- temporary diagnostics cleanup rule
```

- [ ] **Step 2: Update `docs/INDEX.md` so the new 2026-06-15 spec is listed as active architecture truth**

The active design list should include the new optimization spec above the older `2026-06-12` actor specs.

- [ ] **Step 3: Keep old actor specs as migration references rather than deleting them**

Expected repo posture:

```text
2026-06-15 optimization spec = active truth
2026-06-12 specs = historical / narrower migration references
```

- [ ] **Step 4: Run docs verification**

Run:

```powershell
python scripts/verification/harness.py --profile docs
```

Expected: docs profile stays green or reports only unrelated pre-existing issues.

- [ ] **Step 5: Commit**

```bash
git add docs/INDEX.md docs/superpowers/specs/2026-06-15-character-actor-architecture-optimization-design.md
git commit -m "Freeze the new CharacterActor optimization architecture truth"
```

### Task 2: Write The New Optimization Plan And Migration Structure

**Files:**
- Create: `docs/superpowers/plans/2026-06-15-character-actor-architecture-optimization-implementation-plan.md`

- [ ] **Step 1: Verify the plan covers both document work and first-round code convergence**

Run:

```powershell
Get-Content docs\superpowers\plans\2026-06-15-character-actor-architecture-optimization-implementation-plan.md
```

Expected: the plan phases include:

```text
- terminology freeze
- architecture docs
- code contract freeze
- controller boundary cleanup
- actor runtime cleanup
- presentation / modifier cleanup
- asset generalization entry
- final verification
```

- [ ] **Step 2: Make sure the plan only commits to the near-term demo-safe target**

The plan may describe Phase1-facing architecture, but must only implement:

```text
near-term demo-safe convergence
```

- [ ] **Step 3: Run docs verification**

Run:

```powershell
python scripts/verification/harness.py --profile docs
```

Expected: docs profile recognizes the new plan file.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-06-15-character-actor-architecture-optimization-implementation-plan.md
git commit -m "Add the CharacterActor architecture optimization plan"
```

### Task 3: Add Developer Architecture Documentation

**Files:**
- Create: `docs/character/character-actor-architecture.md`
- Create: `docs/character/character-control-chain.md`

- [ ] **Step 1: Write `character-actor-architecture.md`**

This doc must explain:

```text
- the six formal layers
- current file-to-layer mapping
- control mode vs product identity
- near-term vs mid-term architecture
```

- [ ] **Step 2: Write `character-control-chain.md`**

This doc must explain:

```text
- traveler input path
- agent command path
- program control path
- left-click and right-click action path
- locomotion execution path
- where to debug each break
```

- [ ] **Step 3: Add both docs to `docs/INDEX.md` or a role/character section reference**

Expected outcome: future developers can find the architecture explanation without reverse-engineering scripts first.

- [ ] **Step 4: Run docs verification**

Run:

```powershell
python scripts/verification/harness.py --profile docs
```

Expected: new architecture docs are recognized and do not break docs checks.

- [ ] **Step 5: Commit**

```bash
git add docs/character/character-actor-architecture.md docs/character/character-control-chain.md docs/INDEX.md
git commit -m "Document the CharacterActor layers and control chain"
```

### Task 4: Add Asset Integration Documentation

**Files:**
- Create: `docs/character/character-asset-integration.md`
- Create: `docs/character/character-action-asset-interface.md`

- [ ] **Step 1: Write `character-asset-integration.md`**

This doc must explain:

```text
- how to replace a role model
- how to define/update skeleton binding candidates
- how to attach equipment slots
- how to validate a new model against the shared actor substrate
```

- [ ] **Step 2: Write `character-action-asset-interface.md`**

This doc must explain:

```text
- future action asset descriptor shape
- future expression asset descriptor shape
- required equipment/action tags
- how runtime asks for action assets without hardcoding model-specific behavior
```

- [ ] **Step 3: Add these docs to `docs/INDEX.md`**

Expected outcome: future model/action/equipment work has one discoverable integration guide.

- [ ] **Step 4: Run docs verification**

Run:

```powershell
python scripts/verification/harness.py --profile docs
```

Expected: docs profile remains green.

- [ ] **Step 5: Commit**

```bash
git add docs/character/character-asset-integration.md docs/character/character-action-asset-interface.md docs/INDEX.md
git commit -m "Document model, skeleton, equipment, and action asset integration"
```

### Task 5: Freeze Shared Terminology In Code

**Files:**
- Create: `scripts/character/CharacterControlMode.gd`
- Create: `scripts/character/CharacterLocomotionExecutionMode.gd`
- Create: `scripts/character/CharacterPresentationInput.gd`
- Modify: `scripts/player/PlayerShell.gd`
- Modify: `scripts/player/Phase0PlayerBridge.gd`
- Modify: `scripts/character/CharacterReplica.gd`
- Create: `backend/tests/test_character_actor_modes_static.py`

- [ ] **Step 1: Write failing static tests for new mode and contract files**

Add tests that require:

```text
ControlMode
- human_controlled
- agent_controlled
- program_controlled

LocomotionExecutionMode
- physics
- root_motion
- hybrid
```

And require `CharacterPresentationInput.gd` to exist.

- [ ] **Step 2: Run the tests to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_character_actor_modes_static.py
```

Expected before implementation: fail because files or symbols do not exist yet.

- [ ] **Step 3: Add the mode and presentation contract files**

The files may start as simple script constants or enum-style helpers, but must centralize the new vocabulary.

- [ ] **Step 3a: Record the control-mode transition rules in code comments or helper docs**

The code-facing terminology should make it clear that:

```text
human_controlled <-> agent_controlled
human_controlled <-> program_controlled
agent_controlled <-> program_controlled
```

describe controller-source switching, not actor-substrate replacement.

- [ ] **Step 4: Replace scattered string literals where low-risk**

Low-risk targets:

```text
- Control mode references
- locomotion execution terminology
- new presentation-input references
```

Do not do a repository-wide risky rewrite in one step.

- [ ] **Step 5: Re-run the tests**

Run:

```powershell
python -m pytest -q backend\tests\test_character_actor_modes_static.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/character/CharacterControlMode.gd scripts/character/CharacterLocomotionExecutionMode.gd scripts/character/CharacterPresentationInput.gd scripts/player/PlayerShell.gd scripts/player/Phase0PlayerBridge.gd scripts/character/CharacterReplica.gd backend/tests/test_character_actor_modes_static.py
git commit -m "Freeze shared CharacterActor control and locomotion terminology"
```

### Task 6: Clean Up The Controller Boundary

**Files:**
- Modify: `scripts/player/PlayerShell.gd`
- Modify: `scripts/player/Phase0PlayerBridge.gd`
- Create: `backend/tests/test_character_controller_boundary_static.py`

- [ ] **Step 1: Write failing boundary tests**

Add tests that prove:

```text
PlayerShell owns raw input and camera coupling.
Phase0PlayerBridge owns adaptation into actor-facing actions/intents.
Bridge does not need multiple parallel input-entry fallback paths for the same concern.
```

- [ ] **Step 2: Run the tests to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_character_controller_boundary_static.py
```

Expected before cleanup: fail because the current files still overlap in input responsibilities.

- [ ] **Step 3: Narrow `PlayerShell` to raw input, shell state, and camera**

Expected near-term shape:

```text
PlayerShell
- raw human input
- camera/body yaw coupling
- shell locomotion state assembly
```

- [ ] **Step 4: Narrow `Phase0PlayerBridge` to adaptation**

Expected near-term shape:

```text
Phase0PlayerBridge
- consume already-received input meaning
- issue actor actions / sync requests
- avoid acting as a second full input reader
```

- [ ] **Step 5: Re-run the controller-boundary tests**

Run:

```powershell
python -m pytest -q backend\tests\test_character_controller_boundary_static.py
```

Expected: PASS.

- [ ] **Step 6: Run targeted actor control tests**

Run:

```powershell
python -m pytest -q backend\tests\test_player_combat_action_static.py backend\tests\test_player_control_static_contract.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/player/PlayerShell.gd scripts/player/Phase0PlayerBridge.gd backend/tests/test_character_controller_boundary_static.py
git commit -m "Separate raw input from CharacterActor control adaptation"
```

### Task 7: Clean Up The Actor Runtime Boundary

**Files:**
- Modify: `scripts/character/CharacterReplica.gd`
- Modify: `scripts/phase0/MainDemoController.gd`
- Create: `backend/tests/test_character_runtime_boundary_static.py`

- [ ] **Step 1: Write failing runtime-boundary tests**

Add tests that prove:

```text
CharacterReplica is the actor runtime shell.
MainDemoController does not continue accumulating player-actor-specific runtime behavior unnecessarily.
```

- [ ] **Step 2: Run the tests to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_character_runtime_boundary_static.py
```

Expected before cleanup: fail because current responsibilities are still mixed.

- [ ] **Step 3: Narrow `CharacterReplica` to actor-runtime concerns**

Keep:

```text
- role/action state
- focus/interaction runtime
- presentation input aggregation
- command status
```

Avoid growing:

```text
- ad-hoc scene orchestration
- unrelated demo-only helpers
```

- [ ] **Step 4: Remove or quarantine scene-controller-owned player-specific logic**

Only keep player-specific behavior in `MainDemoController` when it truly requires scene-level orchestration.

- [ ] **Step 5: Re-run runtime-boundary tests**

Run:

```powershell
python -m pytest -q backend\tests\test_character_runtime_boundary_static.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/character/CharacterReplica.gd scripts/phase0/MainDemoController.gd backend/tests/test_character_runtime_boundary_static.py
git commit -m "Converge CharacterReplica toward a cleaner actor runtime shell"
```

### Task 8: Harden Presentation And Modifier Separation

**Files:**
- Modify: `scripts/character/KnightRoleSkin.gd`
- Modify: `scripts/character/KnightCombatModifier.gd`
- Modify: `scenes/phase0/KnightRoleSkin.tscn`
- Create: `backend/tests/test_character_presentation_modifier_static.py`

- [ ] **Step 1: Write failing presentation/modifier boundary tests**

Add tests that prove:

```text
KnightRoleSkin owns presentation composition state.
KnightCombatModifier owns post-animation combat correction.
Bone-writing combat overlay does not live in the same layer as clip/motion-profile selection.
```

- [ ] **Step 2: Run the tests to verify failure or partial mismatch**

Run:

```powershell
python -m pytest -q backend\tests\test_character_presentation_modifier_static.py
```

Expected before cleanup: fail or reveal remaining mixed responsibilities.

- [ ] **Step 3: Keep locomotion composition in `KnightRoleSkin` and final correction in the modifier**

Near-term expectation:

```text
KnightRoleSkin
- clip / profile / timer / presentation state

KnightCombatModifier
- final post-animation combat pose
- weapon/shield final local correction
```

- [ ] **Step 4: Re-run tests and script validation**

Run:

```powershell
python -m pytest -q backend\tests\test_character_presentation_modifier_static.py backend\tests\test_player_combat_action_static.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/character/KnightRoleSkin.gd scripts/character/KnightCombatModifier.gd scenes/phase0/KnightRoleSkin.tscn backend/tests/test_character_presentation_modifier_static.py
git commit -m "Separate CharacterActor presentation composition from post-animation correction"
```

### Task 9: Freeze Asset Generalization Entry Points

**Files:**
- Create: `scripts/character/CharacterAssetBindingProfile.gd`
- Create: `scripts/character/CharacterEquipmentBindingProfile.gd`
- Create: `scripts/character/CharacterActionAssetDescriptor.gd`
- Create: `backend/tests/test_character_asset_contract_static.py`

- [ ] **Step 1: Write failing static tests**

Require the contract files and expected top-level fields to exist.

- [ ] **Step 2: Run the tests to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_character_asset_contract_static.py
```

Expected before implementation: fail because these files do not exist yet.

- [ ] **Step 3: Add minimal contract files**

These may begin as GDScript resource-like schema helpers or typed dictionaries, but must freeze:

```text
- model binding
- skeleton binding
- equipment slots
- action descriptors
- compatibility level
```

- [ ] **Step 4: Re-run the tests**

Run:

```powershell
python -m pytest -q backend\tests\test_character_asset_contract_static.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/character/CharacterAssetBindingProfile.gd scripts/character/CharacterEquipmentBindingProfile.gd scripts/character/CharacterActionAssetDescriptor.gd backend/tests/test_character_asset_contract_static.py
git commit -m "Freeze CharacterActor model, skeleton, equipment, and action contracts"
```

### Task 10: Final Verification And Documentation Closeout

**Files:**
- Modify only if needed after verification:
  - `docs/demo-script.md`
  - `docs/current-project-implementation-summary.md`
  - `docs/character/character-actor-migration-status.md`
  - `docs/character/character-debug-and-verification.md`

- [ ] **Step 1: Run focused repository verification**

Run:

```powershell
python -m pytest -v
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile godot-project
python scripts/verification/harness.py --profile phase0
```

Expected:

- targeted static and contract tests pass
- docs and godot-project profiles remain healthy
- phase0 stays runnable or any new gap is documented precisely

- [ ] **Step 2: Update migration-status and debug docs**

Record:

```text
- what is now aligned to the new optimization spec
- what remains transitional
- what future work is intentionally deferred to Phase1-facing follow-up
- which diagnostics are temporary and should be removed
- which diagnostics survive behind explicit debug flags
```

- [ ] **Step 3: Commit**

```bash
git add docs/character/character-actor-migration-status.md docs/character/character-debug-and-verification.md docs/demo-script.md docs/current-project-implementation-summary.md
git commit -m "Close the first CharacterActor architecture optimization migration"
```
