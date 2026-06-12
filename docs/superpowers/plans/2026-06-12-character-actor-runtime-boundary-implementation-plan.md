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
