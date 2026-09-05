# Stormnight Procedural Low-Poly Character Presentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four reusable, primitive-only character replicas to Stormnight and bind them to committed case/action projections without merging existing knight or church scenes.

**Architecture:** Create one reusable Godot `CharacterBody3D` scene and a profile-driven presentation script. Stormnight instances four profiles and applies only committed backend projection state; all action validity and world truth remain in existing Character Agent and P5/ActionWindow authorities.

**Tech Stack:** Godot 4.6.3, GDScript, `CapsuleMesh`, `BoxMesh`, `SphereMesh`, `AnimationPlayer`, existing Stormnight projection probe, pytest static contract tests.

---

### Task 1: Reusable primitive character scene

**Files:**
- Create: `scenes/phase0/ProceduralLowPolyCharacter.tscn`
- Create: `scripts/verification/ProceduralLowPolyCharacter.gd`
- Create: `scripts/verification/ProceduralLowPolyCharacter.gd.uid`
- Test: `backend/tests/test_stormnight_low_poly_character_contract.py`

- [x] **Step 1: Write the failing static contract test**

```python
def test_low_poly_character_is_primitive_only_and_read_only():
    scene = ...
    script = ...
    assert "CharacterBody3D" in scene
    assert "CapsuleMesh" in script and "SphereMesh" in script and "BoxMesh" in script
    assert "append_batch" not in script
    assert "BackendBridge" not in script
    assert "private_fact" not in script
```

- [x] **Step 2: Run the test and confirm it fails**

Run: `python -m pytest -q backend/tests/test_stormnight_low_poly_character_contract.py`
Expected: FAIL because the scene/script do not exist.

- [x] **Step 3: Implement the reusable scene and script**

The script must expose `configure_profile(profile: Dictionary)`,
`apply_committed_state(state: String)`, and `clear_speculative_state()`.
`configure_profile` accepts only `actor_ref`, `role_ref`,
`presentation_profile_ref`, `primary_color`, `secondary_color`, and `marker`.
Build head, torso, limbs, boots and marker from primitive meshes in `_ready()`.

- [x] **Step 4: Run the focused test**

Run: `python -m pytest -q backend/tests/test_stormnight_low_poly_character_contract.py`
Expected: PASS.

- [x] **Step 5: Commit the isolated character slice**

```bash
git add scenes/phase0/ProceduralLowPolyCharacter.tscn scripts/verification/ProceduralLowPolyCharacter.gd scripts/verification/ProceduralLowPolyCharacter.gd.uid backend/tests/test_stormnight_low_poly_character_contract.py
git commit -m "Add primitive-only Stormnight character presentation"
```

### Task 2: Stormnight profile instances and committed-state binding

**Files:**
- Modify: `scripts/verification/StormnightCopperSanatoriumProbe.gd`
- Modify: `scenes/phase0/StormnightCopperSanatorium.tscn`
- Modify: `backend/tests/test_stormnight_godot_contract_static.py`

- [x] **Step 1: Add a failing instance-count assertion**

Assert the Stormnight probe contains four profile refs and instances the
reusable scene without any `ThroneHall` or `KnightRoleSkin` reference.

- [x] **Step 2: Implement four neutral profiles**

Use fixed presentation-only profiles for investigator, guardian, witness and
suspect. Add four spawn transforms under a `StormnightActors` node. Load the
committed projection already produced by `verify_stormnight_copper_sanatorium.py`
and apply its phase/terminal state to every replica.

- [x] **Step 3: Implement rejection rollback**

Before applying a speculative state, snapshot each replica's committed state.
On rejection call `clear_speculative_state()` and restore the snapshot. Do not
send a request or write an event from Godot.

- [x] **Step 4: Run headless Godot and static tests**

Run: `python -m pytest -q backend/tests/test_stormnight_godot_contract_static.py backend/tests/test_stormnight_low_poly_character_contract.py`
Run: `D:\godot\Godot_v4.6.3-stable_win64.exe --headless --path . --scene res://scenes/phase0/StormnightCopperSanatorium.tscn --quit-after 300 --render-thread safe`
Expected: static tests pass and the probe prints `stormnight_copper_sanatorium_probe:verified=true`.

- [x] **Step 5: Commit the Stormnight character binding**

```bash
git add scenes/phase0/StormnightCopperSanatorium.tscn scripts/verification/StormnightCopperSanatoriumProbe.gd backend/tests/test_stormnight_godot_contract_static.py
git commit -m "Bind Stormnight projection to four low-poly actors"
```

### Task 3: Action and agent presentation contract

**Files:**
- Modify: `scripts/verification/StormnightCopperSanatoriumView.gd`
- Create: `backend/tests/test_stormnight_low_poly_character_runtime_contract.py`

- [x] **Step 1: Add tests for committed-state-only animation**

Verify action states map to `idle`, `observe`, `hide`, `pursue`, `controlled`,
and `returned`; arbitrary event vectors and private facts are rejected.

- [x] **Step 2: Implement deterministic state mapping**

Map only committed projection fields and explicit ActionWindow result fields to
local visual states. Unknown or rejected states return `returned` and clear
speculative data.

- [x] **Step 3: Run focused runtime-contract tests**

Run: `python -m pytest -q backend/tests/test_stormnight_low_poly_character_runtime_contract.py`
Expected: PASS.

- [x] **Step 4: Commit the action presentation contract**

```bash
git add scripts/verification/StormnightCopperSanatoriumView.gd backend/tests/test_stormnight_low_poly_character_runtime_contract.py
git commit -m "Keep Stormnight actor animation projection-bound"
```

### Task 4: Verification and documentation closure

**Files:**
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/2026-09-05-stormnight-copper-sanatorium-mystery-case-completion-audit.md`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/README.md`
- Modify: `docs/superpowers/plans/world-character-siming-authority-mainline/README.md`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/phase-five-rpg-social-gameplay/README.md`

- [x] **Step 1: Run focused Stormnight tests**

Run: `python -m pytest -q backend/tests/test_stormnight* backend/tests/test_scripted_mystery*`
Expected: all selected tests pass.

- [x] **Step 2: Run broad verification**

Run: `python -m pytest -q`; `python -m compileall -q backend`; `git diff --check`; `python scripts/verification/harness.py --profile stormnight-copper-sanatorium`; `python scripts/verification/harness.py --profile docs`.

- [x] **Step 3: Record evidence**

Document primitive-only actors, four profile instances, committed projection
binding, rollback behavior, and explicit non-use of knight/church scenes.

- [x] **Step 4: Commit and push the verified docs closure**

```bash
git add docs/superpowers/specs/world-character-siming-authority-mainline docs/superpowers/plans/world-character-siming-authority-mainline
git commit -m "Record Stormnight low-poly character verification"
git push origin main
```

## Rollback conditions

Stop and revert only the new presentation slice if headless Godot fails, a
static test detects a cross-scene reference, a character node attempts a write,
or projection rejection fails to restore the last committed state. Existing
knight/church assets and Stormnight backend facts must remain untouched.

## Execution record

All tasks completed. The focused contract suite passes (`5 passed`), full
repository pytest passes (`5143 passed, 1 warning`), compileall and diff-check
pass, and the Stormnight Harness reports `overall_passed=true` with Godot
headless and desktop smoke verified.
