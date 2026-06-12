# Character Actor Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sequence Character Actor unification so runtime-boundary work and control/locomotion work land in a stable order without breaking the existing Phase 0 demo loop.

**Architecture:** Treat this as a coordination plan above two narrower implementation plans. Land the actor-facing runtime contract first, then land the shared control/motor substrate, then converge scene shape and verification so `CharacterAgent`, `CharacterActor`, and `ESM` remain cleanly separated.

**Tech Stack:** Godot scenes and GDScript, FastAPI websocket backend, Pydantic models, pytest, harness verification, existing Phase 0 static and runtime checks.

---

### Task 1: Freeze Migration Order And File Ownership

**Files:**
- Modify: `docs/superpowers/specs/2026-06-12-character-actor-unification-design.md`
- Modify: `docs/INDEX.md`
- Create: `docs/superpowers/plans/2026-06-12-character-actor-runtime-boundary-implementation-plan.md`
- Create: `docs/superpowers/plans/2026-06-12-character-actor-control-and-locomotion-implementation-plan.md`

- [ ] **Step 1: Confirm the umbrella spec only owns migration and boundary summary**

Check that the umbrella spec remains short and delegates details downward:

```text
Spec A owns runtime boundary and command contracts.
Spec B owns control, camera, motor, and locomotion rules.
```

- [ ] **Step 2: Verify the docs index points at the umbrella spec and both child specs**

Run:

```powershell
Get-Content docs\INDEX.md
```

Expected: the active design list includes the three `2026-06-12-character-actor-*` specs.

- [ ] **Step 3: Add the two child implementation plans before any code migration**

Create the matching plan files:

```text
docs/superpowers/plans/2026-06-12-character-actor-runtime-boundary-implementation-plan.md
docs/superpowers/plans/2026-06-12-character-actor-control-and-locomotion-implementation-plan.md
```

- [ ] **Step 4: Run docs verification**

Run:

```powershell
python scripts/verification/harness.py --profile docs
```

Expected: the `superpowers_specs_have_plans` check no longer reports missing plans.

- [ ] **Step 5: Commit**

```bash
git add docs/INDEX.md docs/superpowers/specs/2026-06-12-character-actor-unification-design.md docs/superpowers/plans/2026-06-12-character-actor-runtime-boundary-implementation-plan.md docs/superpowers/plans/2026-06-12-character-actor-control-and-locomotion-implementation-plan.md docs/superpowers/plans/2026-06-12-character-actor-unification-implementation-plan.md
git commit -m "Sequence Character Actor unification into umbrella and child plans"
```

### Task 2: Execute Runtime Boundary Plan Before Control Refactor

**Files:**
- Modify: `backend/app/models/character_agent_runtime.py`
- Modify: `backend/app/services/character_agent_runtime.py`
- Modify: `backend/app/main.py`
- Modify: `scripts/autoload/BackendBridge.gd`
- Modify: `scripts/autoload/LocalPresentationBus.gd`
- Modify: `scripts/character/CharacterReplica.gd`
- Modify: `scenes/phase0/CharacterReplica.tscn`

- [ ] **Step 1: Execute the runtime-boundary plan first**

The runtime-boundary plan must land before control refactors so the actor-facing contract is frozen first:

```text
CharacterGoalCommand -> ActorControllerAdapter -> CharacterIntentFrame
```

- [ ] **Step 2: Keep world-changing authority in backend/ESM during this phase**

Review any new movement or interaction code and reject patterns like:

```gdscript
global_position = target_position
perform_action("interact") # without reacquisition/authority path
```

Use:

```text
local approach/search/facing in Godot
authoritative world settlement in backend/ESM
```

- [ ] **Step 3: Remove `GreyboxHumanoidVisual` from the actor migration path during runtime-boundary work**

Expected outcome after this phase:

```text
CharacterReplica -> KnightRoleSkin only
```

- [ ] **Step 4: Run focused verification after runtime-boundary implementation**

Run:

```powershell
python -m pytest -q backend\tests\test_character_agent_runtime.py backend\tests\test_visual_fact_pipeline.py backend\tests\test_ws_protocol.py
python scripts/verification/harness.py --profile godot-project
```

Expected: the contract path is wired and static Godot integrity still passes.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/character_agent_runtime.py backend/app/services/character_agent_runtime.py backend/app/main.py scripts/autoload/BackendBridge.gd scripts/autoload/LocalPresentationBus.gd scripts/character/CharacterReplica.gd scenes/phase0/CharacterReplica.tscn
git commit -m "Land the Character Actor runtime boundary before control refactor"
```

### Task 3: Execute Control And Locomotion Plan After Contract Freeze

**Files:**
- Modify: `scenes/phase0/CharacterBase.tscn`
- Modify: `scripts/player/PlayerShell.gd`
- Modify: `scripts/player/Phase0PlayerBridge.gd`
- Modify: `scripts/player/PlayerController.gd`
- Modify: `scripts/character/KnightRoleSkin.gd`
- Create: `scripts/character/CharacterMotor.gd`
- Create: `backend/tests/test_character_actor_static_contract.py`

- [ ] **Step 1: Apply the control-and-locomotion plan after the runtime contract is stable**

The control refactor should consume the frozen runtime contract instead of redefining it.

- [ ] **Step 2: Converge player movement onto motor-owned displacement**

The target execution path is:

```text
HumanController
-> CharacterIntentFrame
-> CharacterMotor
-> CharacterMotionState
-> KnightRoleSkin
```

- [ ] **Step 3: Keep camera/body yaw locked while preserving root-motion diagnostics**

Reject regressions toward an orbit/hybrid controller unless a new approved spec changes the rule:

```text
camera forward yaw == body forward yaw == aim forward yaw
```

- [ ] **Step 4: Run focused control verification**

Run:

```powershell
python -m pytest -q backend\tests\test_character_actor_static_contract.py
python scripts/verification/harness.py --profile godot-project
python scripts/verification/harness.py --profile phase0
```

Expected: the scene still runs, and the actor motor/control invariants are statically or runtime-verified.

- [ ] **Step 5: Commit**

```bash
git add scenes/phase0/CharacterBase.tscn scripts/player/PlayerShell.gd scripts/player/Phase0PlayerBridge.gd scripts/player/PlayerController.gd scripts/character/KnightRoleSkin.gd scripts/character/CharacterMotor.gd backend/tests/test_character_actor_static_contract.py
git commit -m "Converge Character Actor control and locomotion onto the shared substrate"
```

### Task 4: Final Convergence And Verification

**Files:**
- Modify: `scenes/phase0/MainDemo.tscn`
- Modify: `scripts/verification/verify_phase0.py` only if verification evidence shows a real gap
- Modify: `docs/demo-script.md` only if the verified flow changes observably

- [ ] **Step 1: Check that player and agent paths now share the intended actor substrate**

Review the final scene path and confirm there is no separate NPC-only body runtime species left in normal execution.

- [ ] **Step 2: Run repository verification**

Run:

```powershell
python -m pytest -v
python scripts/verification/harness.py --profile phase0
python scripts/verification/harness.py --profile phase1-slice
python scripts/verification/harness.py --profile all
```

Expected:

- pytest passes
- `phase0` stays green
- `phase1-slice` stays green
- `all` stays green

- [ ] **Step 3: Commit**

```bash
git add scenes/phase0/MainDemo.tscn scripts/verification/verify_phase0.py docs/demo-script.md
git commit -m "Close Character Actor unification with full verification"
```
