# Character Actor Runtime Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the actor-facing runtime contract that lets backend-side `CharacterAgent` drive a shared Godot-side `CharacterActor` without collapsing world authority or creating separate player/NPC body species.

**Architecture:** Freeze `CharacterGoalCommand` as the backend-to-Godot actor contract and `CharacterIntentFrame` as the Godot-local execution frame. Keep semantic eligibility in backend `CharacterAgent`, embodied feasibility in Godot `CharacterActor`, and world-changing settlement in `ESM`.

**Tech Stack:** FastAPI websocket backend, Pydantic models, Godot GDScript, existing `CharacterAgent` services, LocalPresentationBus/BackendBridge integration, pytest, harness verification.

---

### Task 1: Freeze The Actor-Facing Contract

**Files:**
- Modify: `backend/app/models/character_agent_runtime.py`
- Create: `backend/tests/test_character_actor_contract_models.py`

- [ ] **Step 1: Write the failing contract model tests**

Add tests that lock the two-shape split:

```python
from app.models.character_agent_runtime import CharacterGoalCommand, CharacterIntentFrame


def test_character_goal_command_is_backend_actor_contract() -> None:
    command = CharacterGoalCommand(
        actor_id="char_a",
        command_type="approach",
        target_object_id="obj_letter",
        ttl_ms=1000,
        causation_id="cg:1",
        correlation_id="cg:1",
    )

    assert command.command_type == "approach"
    assert command.target_object_id == "obj_letter"


def test_character_intent_frame_is_local_execution_shape() -> None:
    frame = CharacterIntentFrame(
        actor_id="char_a",
        controller_source="agent",
        move_local=[0.0, 1.0],
        gait="walk",
        action="observe",
        ttl_ms=1000,
        causation_id="ci:1",
        correlation_id="ci:1",
    )

    assert frame.controller_source == "agent"
    assert frame.gait == "walk"
```

- [ ] **Step 2: Run the model tests to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_character_actor_contract_models.py
```

Expected before implementation: fail because the actor contract models are missing or incomplete.

- [ ] **Step 3: Implement the runtime contract models**

Add focused model types in `backend/app/models/character_agent_runtime.py`:

```python
class CharacterGoalCommand(BaseModel):
    actor_id: str
    command_type: Literal["look_at", "go_to", "approach", "observe", "interact", "speak"]
    ...


class CharacterIntentFrame(BaseModel):
    actor_id: str
    controller_source: Literal["human", "agent", "scripted"]
    ...
```

- [ ] **Step 4: Re-run the model tests**

Run:

```powershell
python -m pytest -q backend\tests\test_character_actor_contract_models.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/character_agent_runtime.py backend/tests/test_character_actor_contract_models.py
git commit -m "Freeze the Character Actor runtime command contracts"
```

### Task 2: Emit `CharacterGoalCommand` From Backend Runtime

**Files:**
- Modify: `backend/app/services/character_agent_l4_adapter.py`
- Modify: `backend/app/services/character_agent_runtime.py`
- Create: `backend/tests/test_character_agent_goal_command_runtime.py`

- [ ] **Step 1: Write the failing runtime tests**

Add tests that prove the runtime emits actor-facing high-level commands rather than directly pretending to be a body executor:

```python
def test_character_agent_runtime_emits_goal_command() -> None:
    runtime = CharacterAgentRuntime()
    event = make_character_perceived_event(actor_id="char_a", perceived_summary="visual_fact/fixed_gaze_on_target")

    commands = runtime.ingest_character_perceived_event(event)

    assert commands
    assert commands[0].command_type in {"look_at", "approach", "observe", "interact", "speak"}
```

- [ ] **Step 2: Run the runtime tests to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_character_agent_goal_command_runtime.py
```

Expected before implementation: fail because `L4` still emits the wrong shape or no actor-facing commands.

- [ ] **Step 3: Refactor `CharacterAgentL4Adapter` to emit goal commands**

The adapter should map decisions to high-level actor commands, for example:

```python
if decision.selected_intent == "observe_target":
    return [CharacterGoalCommand(actor_id=decision.actor_id, command_type="observe", ...)]
```

- [ ] **Step 4: Keep semantic eligibility in backend runtime**

Do not add frame-perfect LOS or collision assumptions here. Keep the runtime at the level of:

```text
meaningful / known enough / worth pursuing
```

- [ ] **Step 5: Re-run the runtime tests**

Run:

```powershell
python -m pytest -q backend\tests\test_character_agent_goal_command_runtime.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/character_agent_l4_adapter.py backend/app/services/character_agent_runtime.py backend/tests/test_character_agent_goal_command_runtime.py
git commit -m "Make CharacterAgent emit actor-facing goal commands"
```

### Task 3: Wire Goal Commands Through The Websocket Boundary

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_ws_protocol.py`
- Modify: `backend/tests/test_visual_fact_pipeline.py`

- [ ] **Step 1: Write the failing websocket tests**

Add assertions that outbound runtime messages carry `CharacterGoalCommand` semantics:

```python
assert message["message_type"] == "character_agent_output"
assert message["payload"]["command_type"] in {"observe", "approach", "speak", "interact"}
```

- [ ] **Step 2: Run the websocket tests to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_ws_protocol.py backend\tests\test_visual_fact_pipeline.py
```

Expected before implementation: fail because the backend does not yet emit the actor-facing command envelope.

- [ ] **Step 3: Add envelope conversion helper in `backend/app/main.py`**

Use a helper like:

```python
def _as_character_agent_output_envelopes(commands: list[CharacterGoalCommand]) -> list[dict[str, object]]:
    return [{"message_type": "character_agent_output", "payload": command.model_dump(exclude_none=True)} for command in commands]
```

- [ ] **Step 4: Feed filtered/private character inputs through the runtime**

Wire the runtime only from:

- filtered `CharacterPerceivedEvent`
- `SelfBodyPerceivedEvent`
- targeted `Siming` catalyst input

Do not wire raw-fact or authority settlement objects directly into the runtime business interface.

- [ ] **Step 5: Re-run the websocket tests**

Run:

```powershell
python -m pytest -q backend\tests\test_ws_protocol.py backend\tests\test_visual_fact_pipeline.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/tests/test_ws_protocol.py backend/tests/test_visual_fact_pipeline.py
git commit -m "Wire CharacterGoalCommand through the backend websocket boundary"
```

### Task 4: Adapt Godot To Consume Actor-Facing Commands

**Files:**
- Modify: `scripts/autoload/BackendBridge.gd`
- Modify: `scripts/autoload/LocalPresentationBus.gd`
- Modify: `scripts/character/CharacterReplica.gd`
- Create: `backend/tests/test_character_actor_bridge_static.py`

- [ ] **Step 1: Write the failing static contract tests**

Add tests that prove the Godot bridge exposes the new message path:

```python
assert 'signal character_agent_output_received(payload)' in bus_source
assert 'character_agent_output' in bridge_source
assert 'command_type' in replica_source
```

- [ ] **Step 2: Run the static tests to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_character_actor_bridge_static.py
```

Expected before implementation: fail because the bus/bridge/replica path is not fully wired.

- [ ] **Step 3: Add the bus signal and bridge dispatch**

In `LocalPresentationBus.gd`:

```gdscript
signal character_agent_output_received(payload)
```

In `BackendBridge.gd`:

```gdscript
"character_agent_output":
    _bus_emit("character_agent_output_received", [payload])
```

- [ ] **Step 4: Teach `CharacterReplica.gd` to adapt goal commands into local execution state**

Add a focused handler:

```gdscript
func _on_character_agent_output_received(payload: Dictionary) -> void:
    if str(payload.get("actor_id", "")) != actor_id:
        return
    match str(payload.get("command_type", "")):
        "observe":
            set_focus_target(...)
        "approach":
            set_move_target(...)
        "speak":
            queue_speak_action(payload)
```

- [ ] **Step 5: Re-run the static tests**

Run:

```powershell
python -m pytest -q backend\tests\test_character_actor_bridge_static.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/autoload/BackendBridge.gd scripts/autoload/LocalPresentationBus.gd scripts/character/CharacterReplica.gd backend/tests/test_character_actor_bridge_static.py
git commit -m "Adapt Godot to consume actor-facing CharacterGoalCommands"
```

### Task 5: Remove Greybox And Verify Boundary Integrity

**Files:**
- Modify: `scenes/phase0/CharacterReplica.tscn`
- Modify: `scripts/character/CharacterReplica.gd`
- Create: `backend/tests/test_character_actor_boundary_audit.py`

- [ ] **Step 1: Write the failing boundary audit**

Add assertions that:

- `GreyboxHumanoidVisual` is gone from `CharacterReplica.tscn`
- `CharacterAgentRuntime` is not imported into `ESM` authority code
- `CharacterActor` side does not claim semantic eligibility ownership

```python
assert "GreyboxHumanoidVisual" not in scene_source
assert "CharacterAgentRuntime" not in esm_source
```

- [ ] **Step 2: Run the audit to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_character_actor_boundary_audit.py
```

Expected before implementation: fail until the scene and audit match the intended boundary.

- [ ] **Step 3: Remove the greybox runtime dependency**

Delete the greybox scene node from `CharacterReplica.tscn` and remove fallback logic from `CharacterReplica.gd`.

- [ ] **Step 4: Run verification**

Run:

```powershell
python -m pytest -q backend\tests\test_character_actor_boundary_audit.py backend\tests\test_character_actor_contract_models.py backend\tests\test_character_agent_goal_command_runtime.py
python scripts/verification/harness.py --profile godot-project
python scripts/verification/harness.py --profile phase0
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scenes/phase0/CharacterReplica.tscn scripts/character/CharacterReplica.gd backend/tests/test_character_actor_boundary_audit.py
git commit -m "Remove greybox and verify Character Actor runtime boundaries"
```

### Task 6: Enforce Focus, Reacquisition, And Embodied Eligibility Feedback

**Files:**
- Modify: `scripts/character/CharacterReplica.gd`
- Modify: `scripts/autoload/LocalPresentationBus.gd`
- Modify: `scripts/autoload/BackendBridge.gd`
- Modify: `backend/app/main.py` only if structured status envelopes must cross the websocket boundary
- Create: `backend/tests/test_character_actor_reacquisition_runtime.py`

- [x] **Step 1: Write the failing focus/reacquisition tests**

Add tests that lock the actor-side fairness rules:

```python
assert "FocusState" in runtime_boundary_spec_text
assert "target_id is a request, not authority" in runtime_boundary_spec_text
assert failure_reason in {"target_not_visible", "target_out_of_range", "target_unreachable", "target_not_perceived"}
```

- [x] **Step 2: Run the tests to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_character_actor_reacquisition_runtime.py
```

Expected before implementation: fail because reacquisition feedback and focus fairness are not yet fully locked.

- [x] **Step 3: Enforce local embodied gates before final interaction**

The Godot actor path must treat agent `target_id` as a request only and require current embodied eligibility before final local execution:

```text
goal target
-> local focus / perception / reachability gate
-> recover by turn / approach / search if possible
-> only then submit final authority-facing interaction
```

- [x] **Step 4: Emit structured lifecycle status for reacquisition and embodied failure**

At minimum, preserve explicit statuses/reasons for:

```text
accepted_by_actor_adapter
recovering_approach
recovering_turn
embodied_target_not_visible
embodied_out_of_range
submitted_to_authority
failed
```

- [x] **Step 5: Re-run the tests**

Run:

```powershell
python -m pytest -q backend\tests\test_character_actor_reacquisition_runtime.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/character/CharacterReplica.gd scripts/autoload/LocalPresentationBus.gd scripts/autoload/BackendBridge.gd backend/app/main.py backend/tests/test_character_actor_reacquisition_runtime.py
git commit -m "Enforce Character Actor focus fairness and reacquisition feedback"
```

Evidence:

- RED: `python -m pytest -q backend\tests\test_character_actor_reacquisition_runtime.py` failed because `CharacterReplica.gd` did not yet expose target-request fairness/status feedback.
- GREEN: `python -m pytest -q backend\tests\test_character_actor_reacquisition_runtime.py` passed (`2 passed`).
- Risk hardening: `python -m pytest -q backend\tests\test_character_actor_reacquisition_runtime.py backend\tests\test_pytest_config_static.py` passed (`4 passed`) after replacing unconditional embodied gate placeholders with Godot direct-space raycast / tree-membership checks and pinning pytest-asyncio loop scope.
- Static project check: `python scripts\verification\harness.py --profile godot-project` passed (`overall_godot_project_passed=True`).

### Task 7: Freeze Autonomy Modes, Shared Command Permissions, And Speak Embodiment

**Files:**
- Modify: `backend/app/models/character_agent_runtime.py`
- Modify: `backend/app/services/character_agent_runtime.py`
- Modify: `scripts/character/CharacterReplica.gd`
- Create: `backend/tests/test_character_actor_autonomy_modes.py`

- [x] **Step 1: Write the failing autonomy-mode tests**

Add tests that lock:

- the reserved autonomy modes
- the shared command surface
- the conservative restrictions
- `speak` as embodied action rather than local text generation

```python
assert mode in {"human_controlled", "agent_controlled", "idle_autonomous", "away_conservative_takeover", "scripted_test"}
assert command in {"look_at", "go_to", "approach", "observe", "interact", "speak"}
```

- [x] **Step 2: Run the tests to verify failure**

Run:

```powershell
python -m pytest -q backend\tests\test_character_actor_autonomy_modes.py
```

Expected before implementation: fail because permissions and embodied `speak` semantics are not yet frozen.

- [x] **Step 3: Encode the autonomy-mode and permission contract**

Implementation must preserve:

```text
human_controlled
agent_controlled
idle_autonomous
away_conservative_takeover
scripted_test
```

and keep away-conservative behavior limited to low-risk continuity commands.

- [x] **Step 4: Keep `speak` embodied but not generative**

Preserve:

```text
CharacterAgent / dialogue service owns text
CharacterActor owns facing, focus, playback, and local role/auditory fact emission
```

- [x] **Step 5: Re-run the tests**

Run:

```powershell
python -m pytest -q backend\tests\test_character_actor_autonomy_modes.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/character_agent_runtime.py backend/app/services/character_agent_runtime.py scripts/character/CharacterReplica.gd backend/tests/test_character_actor_autonomy_modes.py
git commit -m "Freeze Character Actor autonomy modes and embodied speak rules"
```

Evidence:

- RED: `python -m pytest -q backend\tests\test_character_actor_autonomy_modes.py` failed because autonomy mode constants, runtime permission checks, and embodied speak helper were missing.
- GREEN: `python -m pytest -q backend\tests\test_character_actor_autonomy_modes.py` passed (`3 passed`).

### Task 8: Final Runtime-Boundary Verification

**Files:**
- Modify: `scripts/verification/verify_phase0.py` only if verified evidence shows a real gap
- Modify: `docs/demo-script.md` only if the verified actor-facing runtime behavior changes observably

- [x] **Step 1: Run the focused runtime-boundary suite**

Run:

```powershell
python -m pytest -q backend\tests\test_character_actor_contract_models.py backend\tests\test_character_agent_goal_command_runtime.py backend\tests\test_character_actor_bridge_static.py backend\tests\test_character_actor_boundary_audit.py backend\tests\test_character_actor_reacquisition_runtime.py backend\tests\test_character_actor_autonomy_modes.py backend\tests\test_ws_protocol.py backend\tests\test_visual_fact_pipeline.py
```

Expected: PASS.

- [x] **Step 2: Run project verification**

Run:

```powershell
python scripts/verification/harness.py --profile godot-project
python scripts/verification/harness.py --profile phase0
```

Expected:

- Godot project integrity passes
- Phase 0 loop remains green

- [ ] **Step 3: Commit**

```bash
git add scripts/verification/verify_phase0.py docs/demo-script.md
git commit -m "Verify the Character Actor runtime boundary end to end"
```

Evidence:

- Focused suite: `python -m pytest -q backend\tests\test_character_actor_contract_models.py backend\tests\test_character_agent_goal_command_runtime.py backend\tests\test_character_actor_bridge_static.py backend\tests\test_character_actor_boundary_audit.py backend\tests\test_character_actor_reacquisition_runtime.py backend\tests\test_character_actor_autonomy_modes.py backend\tests\test_ws_protocol.py backend\tests\test_visual_fact_pipeline.py` passed (`62 passed`).
- Hardened focused suite plus pytest config guard passed (`64 passed`) with `backend\tests\test_pytest_config_static.py` included.
- `python scripts\verification\harness.py --profile godot-project` passed (`overall_godot_project_passed=True`).
- `python scripts\verification\harness.py --profile phase0` passed (`overall_strict_phase0_passed=True`).
