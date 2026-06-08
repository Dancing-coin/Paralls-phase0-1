# Stage 2 Merge And Downlink V0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After the enhanced `ESM`, `Siming`, and event-bus branches merge back, relocate the implementations into the new architecture seams and ship the first real `L2 -> L1/ESM` downlink execution slice.

**Architecture:** Stage 1 already created stable package seams and contracts. Stage 2 assumes the enhanced implementations now exist and focuses on physical relocation, compatibility cleanup, and one narrow but real downlink path. The downlink v0 scope is intentionally limited to three action families: `speak_to_actor`, `orient_to_target`, and `inspect_object`.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, pytest, Godot 4.x GDScript, current Phase 0 verification scripts, existing websocket authority path.

---

## Preconditions

Do **not** execute this plan until all of the following are true:

- enhanced `ESM` branch is merged into the current worktree
- enhanced `Siming` branch is merged into the current worktree
- enhanced event-bus branch is merged into the current worktree
- Stage 1 architecture seam files still exist and are green

If those preconditions are not true, stop after reading this plan and do not start editing.

## File Map

### Backend relocation targets

- Modify: `backend/app/l1/esm/service.py`
- Create or Modify: `backend/app/l1/esm/execution_gateway.py`
- Modify: `backend/app/l2/character_agent/service.py`
- Create or Modify: `backend/app/l2/character_agent/downlink_adapter.py`
- Modify: `backend/app/l2/siming/service.py`
- Modify: `backend/app/l6/authority_bus/router.py`
- Modify: `backend/app/l6/authority_bus/ingress.py`
- Modify: `backend/app/l6/authority_bus/message_types.py`
- Modify: `backend/app/l6/perception_chain/*`
- Modify: `backend/app/l6/replay_audit/*`
- Create: `backend/app/api/ws.py`
- Create: `backend/app/api/health.py`
- Create: `backend/app/api/debug.py`
- Create: `backend/app/bootstrap/app_factory.py`
- Modify: `backend/app/main.py`

### Legacy compatibility cleanup

- Modify: `backend/app/services/esm_service.py`
- Modify: `backend/app/services/siming_service.py`
- Modify: `backend/app/services/candidate_percept_service.py`
- Modify: `backend/app/services/per_character_percept_filter.py`
- Modify: `backend/app/debug_stream.py`
- Modify: `backend/app/verification_audit.py`

### Godot relocation and execution targets

- Modify: `scripts/l6/backend_bridge/BackendBridge.gd`
- Modify: `scripts/l6/local_presentation_bus/LocalPresentationBus.gd`
- Create or Modify: `scripts/l1/world/ActionExecutor.gd`
- Create or Modify: `scripts/presentation/character/CharacterActionReceiver.gd`
- Modify: `scripts/presentation/character/CharacterReplica.gd`
- Modify: `scripts/presentation/object/InteractiveObject.gd`
- Modify: `scripts/presentation/environment/EnvironmentStateController.gd`
- Modify: `scenes/phase0/MainDemo.tscn`

### Downlink contracts

- Modify: `backend/app/contracts/l1/action_request.py`
- Modify: `backend/app/contracts/l1/presentation_command.py`
- Modify: `backend/app/contracts/l1/execution_ack.py`
- Modify: `backend/app/contracts/l1/world_execution_result.py`

### Tests

- Create: `backend/tests/test_downlink_action_request.py`
- Create: `backend/tests/test_downlink_execution_gateway.py`
- Modify: `backend/tests/test_ws_protocol.py`
- Modify: `backend/tests/test_esm_service.py`
- Modify: `backend/tests/test_siming_service.py`
- Modify: `backend/tests/test_architecture_entrypoints.py`

---

### Task 1: Confirm Post-Merge Baseline And Preserve Stage 1 Entry Points

**Files:**
- Modify: `backend/tests/test_architecture_entrypoints.py`

- [ ] **Step 1: Add a post-merge seam preservation test**

Append:

```python
def test_stage1_entrypoints_still_exist_after_merge() -> None:
    from app.l1.esm.service import ESMServiceEntry
    from app.l2.siming.service import SimingServiceEntry
    from app.l6.authority_bus.router import handle_envelope_entry

    assert ESMServiceEntry is not None
    assert SimingServiceEntry is not None
    assert callable(handle_envelope_entry)
```

- [ ] **Step 2: Run the seam preservation test**

Run from `backend/`:

```bash
python -m pytest -v tests/test_architecture_entrypoints.py::test_stage1_entrypoints_still_exist_after_merge
```

Expected:

- PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_architecture_entrypoints.py
git commit -m "test: preserve stage1 entrypoints after merge"
```

### Task 2: Move Enhanced Implementations Into Their Architecture Slots

**Files:**
- Modify: `backend/app/l1/esm/service.py`
- Modify: `backend/app/l2/siming/service.py`
- Modify: `backend/app/l6/authority_bus/router.py`
- Modify: legacy files only as compatibility wrappers

- [ ] **Step 1: Replace the thin `ESM` facade with the merged implementation**

Target shape:

```python
# backend/app/l1/esm/service.py
from app.services.esm_service import ESMService as _LegacyESMService


class ESMServiceEntry(_LegacyESMService):
    pass
```

If the merged branch already provides a richer implementation, adapt that richer class here instead of keeping the thin alias. Do not break the `ESMServiceEntry` name.

- [ ] **Step 2: Replace the thin `Siming` facade with the merged implementation**

Target shape:

```python
# backend/app/l2/siming/service.py
from app.services.siming_service import SimingService as _LegacySimingService


class SimingServiceEntry(_LegacySimingService):
    pass
```

Again, if the merged branch exposes a richer class, anchor it behind `SimingServiceEntry` without changing the public seam.

- [ ] **Step 3: Move authority-bus routing behind `app.l6.authority_bus.router`**

Target shape:

```python
# backend/app/l6/authority_bus/router.py
from app.main import _handle_envelope


def handle_envelope_entry(envelope):
    return _handle_envelope(envelope)
```

If the merged bus branch already split routing logic out of `main.py`, import the new router here instead and keep the `handle_envelope_entry` symbol stable.

- [ ] **Step 4: Re-run seam verification**

Run from `backend/`:

```bash
python -m pytest -v tests/test_architecture_entrypoints.py
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/l1/esm/service.py backend/app/l2/siming/service.py backend/app/l6/authority_bus/router.py backend/tests/test_architecture_entrypoints.py
git commit -m "refactor: anchor merged implementations behind architecture seams"
```

### Task 3: Split `main.py` Into API And Bootstrap Surfaces

**Files:**
- Create: `backend/app/api/ws.py`
- Create: `backend/app/api/health.py`
- Create: `backend/app/api/debug.py`
- Create: `backend/app/bootstrap/app_factory.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add a failing import test for the app factory**

Append to `backend/tests/test_architecture_entrypoints.py`:

```python
def test_app_factory_entrypoint_exists() -> None:
    from app.bootstrap.app_factory import create_app

    app = create_app()

    assert app is not None
```

- [ ] **Step 2: Run the factory test to verify failure**

Run from `backend/`:

```bash
python -m pytest -v tests/test_architecture_entrypoints.py::test_app_factory_entrypoint_exists
```

Expected:

- FAIL

- [ ] **Step 3: Create the app factory and route modules**

Use this minimal target:

```python
# backend/app/bootstrap/app_factory.py
from fastapi import FastAPI
from app.api.health import register_health_routes
from app.api.debug import register_debug_routes
from app.api.ws import register_ws_routes


def create_app() -> FastAPI:
    app = FastAPI(title="Paralls Phase0 Backend")
    register_health_routes(app)
    register_debug_routes(app)
    register_ws_routes(app)
    return app
```

`backend/app/main.py` should become:

```python
from app.bootstrap.app_factory import create_app


app = create_app()
```

Keep the current runtime objects and `_handle_envelope` reachable from the modules that need them. Do not break websocket tests.

- [ ] **Step 4: Run the focused websocket tests**

Run from `backend/`:

```bash
python -m pytest -v tests/test_health.py tests/test_debug_panel.py tests/test_ws_protocol.py
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api backend/app/bootstrap backend/app/main.py backend/tests/test_architecture_entrypoints.py
git commit -m "refactor: split app entrypoint into api and bootstrap layers"
```

### Task 4: Make Legacy Flat Modules Compatibility Wrappers

**Files:**
- Modify: `backend/app/services/esm_service.py`
- Modify: `backend/app/services/siming_service.py`
- Modify: `backend/app/services/candidate_percept_service.py`
- Modify: `backend/app/services/per_character_percept_filter.py`
- Modify: `backend/app/debug_stream.py`
- Modify: `backend/app/verification_audit.py`

- [ ] **Step 1: Convert legacy modules into wrappers where feasible**

Example:

```python
# backend/app/services/esm_service.py
from app.l1.esm.service import ESMServiceEntry


class ESMService(ESMServiceEntry):
    pass
```

Do the same pattern for:

- `SimingService`
- `compile_candidate_percepts`
- `filter_candidate_for_actor`
- debug-stream exports
- verification-audit exports

The goal is that old import paths still work, but new work should point at the layered structure.

- [ ] **Step 2: Run focused regression tests**

Run from `backend/`:

```bash
python -m pytest -v tests/test_esm_service.py tests/test_siming_service.py tests/test_candidate_percept_service.py tests/test_per_character_percept_filter.py
```

Expected:

- PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/esm_service.py backend/app/services/siming_service.py backend/app/services/candidate_percept_service.py backend/app/services/per_character_percept_filter.py backend/app/debug_stream.py backend/app/verification_audit.py
git commit -m "refactor: preserve legacy imports through compatibility wrappers"
```

### Task 5: Define Downlink V0 Contracts As Real Runtime Objects

**Files:**
- Modify: `backend/app/contracts/l1/action_request.py`
- Modify: `backend/app/contracts/l1/presentation_command.py`
- Modify: `backend/app/contracts/l1/execution_ack.py`
- Modify: `backend/app/contracts/l1/world_execution_result.py`
- Create: `backend/tests/test_downlink_action_request.py`

- [ ] **Step 1: Add failing tests for downlink contracts**

Create `backend/tests/test_downlink_action_request.py`:

```python
from app.contracts.l1.action_request import ActionRequest
from app.contracts.l1.execution_ack import ExecutionAck
from app.contracts.l1.presentation_command import PresentationCommand
from app.contracts.l1.world_execution_result import WorldExecutionResult


def test_action_request_shape() -> None:
    event = ActionRequest(
        request_id="req1",
        actor_id="char_a",
        action_type="inspect_object",
        target_object_id="obj_letter",
        payload={"interaction_type": "inspect"},
    )

    assert event.action_type == "inspect_object"
    assert event.target_object_id == "obj_letter"


def test_execution_ack_shape() -> None:
    ack = ExecutionAck(
        request_id="req1",
        accepted=True,
        execution_lane="esm",
    )

    assert ack.accepted is True
    assert ack.execution_lane == "esm"


def test_presentation_command_shape() -> None:
    cmd = PresentationCommand(
        command_id="cmd1",
        actor_id="char_a",
        command_type="orient_to_target",
        payload={"target_actor_id": "char_c"},
    )

    assert cmd.command_type == "orient_to_target"


def test_world_execution_result_shape() -> None:
    result = WorldExecutionResult(
        request_id="req1",
        result_type="object_interaction_result",
        payload={"target_object_id": "obj_letter"},
    )

    assert result.result_type == "object_interaction_result"
```

- [ ] **Step 2: Run the contract tests**

Run from `backend/`:

```bash
python -m pytest -v tests/test_downlink_action_request.py
```

Expected:

- PASS or minimal shape failures that tell you what fields need adjustment

- [ ] **Step 3: Commit**

```bash
git add backend/app/contracts/l1/*.py backend/tests/test_downlink_action_request.py
git commit -m "feat: define downlink v0 contract coverage"
```

### Task 6: Add A Backend Downlink Execution Gateway

**Files:**
- Create or Modify: `backend/app/l1/esm/execution_gateway.py`
- Create: `backend/tests/test_downlink_execution_gateway.py`

- [ ] **Step 1: Add failing gateway tests**

Create `backend/tests/test_downlink_execution_gateway.py`:

```python
from app.contracts.l1.action_request import ActionRequest
from app.l1.esm.execution_gateway import execute_action_request


def test_execute_orient_to_target_returns_presentation_command() -> None:
    request = ActionRequest(
        request_id="req_orient",
        actor_id="char_a",
        action_type="orient_to_target",
        target_actor_id="char_c",
    )

    ack, outputs = execute_action_request(request)

    assert ack.accepted is True
    assert ack.execution_lane == "presentation"
    assert outputs[0].command_type == "orient_to_target"


def test_execute_inspect_object_routes_to_esm() -> None:
    request = ActionRequest(
        request_id="req_inspect",
        actor_id="char_a",
        action_type="inspect_object",
        target_object_id="obj_letter",
        payload={"interaction_type": "inspect"},
    )

    ack, outputs = execute_action_request(request)

    assert ack.accepted is True
    assert ack.execution_lane == "esm"
    assert outputs[0].result_type in {"object_interaction_result", "constraint_state_result"}
```

- [ ] **Step 2: Implement the minimal gateway**

Target shape:

```python
from app.contracts.l1.execution_ack import ExecutionAck
from app.contracts.l1.presentation_command import PresentationCommand
from app.contracts.l1.world_execution_result import WorldExecutionResult
from app.l1.esm.service import ESMServiceEntry


def execute_action_request(request):
    if request.action_type == "orient_to_target":
        ack = ExecutionAck(request_id=request.request_id, accepted=True, execution_lane="presentation")
        outputs = [
            PresentationCommand(
                command_id=f"cmd:{request.request_id}",
                actor_id=request.actor_id,
                command_type="orient_to_target",
                payload={"target_actor_id": request.target_actor_id},
            )
        ]
        return ack, outputs

    if request.action_type == "inspect_object":
        esm = ESMServiceEntry()
        result = esm.resolve_interaction(
            type(
                "InspectEvent",
                (),
                {
                    "room_id": "room_demo",
                    "target_object_id": request.target_object_id,
                    "interaction_type": request.payload.get("interaction_type", "inspect"),
                    "producer_ts": 1,
                },
            )()
        )
        ack = ExecutionAck(request_id=request.request_id, accepted=True, execution_lane="esm")
        outputs = [WorldExecutionResult(request_id=request.request_id, result_type=result.result_type, payload=result.model_dump())]
        return ack, outputs

    ack = ExecutionAck(request_id=request.request_id, accepted=False, execution_lane="none", rejection_reason="unsupported_action")
    return ack, []
```

- [ ] **Step 3: Run the gateway tests**

Run from `backend/`:

```bash
python -m pytest -v tests/test_downlink_execution_gateway.py
```

Expected:

- PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/l1/esm/execution_gateway.py backend/tests/test_downlink_execution_gateway.py
git commit -m "feat: add downlink v0 backend execution gateway"
```

### Task 7: Route L2 Outputs Into The Downlink Gateway

**Files:**
- Modify: `backend/app/l2/character_agent/downlink_adapter.py`
- Modify: `backend/app/l2/character_agent/service.py`
- Modify: `backend/app/l2/siming/service.py`

- [ ] **Step 1: Create a narrow downlink adapter**

Target:

```python
from app.contracts.l1.action_request import ActionRequest


def build_orient_request(actor_id: str, target_actor_id: str) -> ActionRequest:
    return ActionRequest(
        request_id=f"orient:{actor_id}:{target_actor_id}",
        actor_id=actor_id,
        action_type="orient_to_target",
        target_actor_id=target_actor_id,
    )
```

- [ ] **Step 2: Add a single real L2-to-downlink usage**

The first narrow path should be:

- when Siming or character-side logic decides an object inspection should happen,
- emit an `ActionRequest`,
- route it into `execute_action_request(...)`,
- return the resulting `ExecutionAck` and execution outputs into the authority path.

Do **not** attempt a full planner.
This is downlink v0 only.

- [ ] **Step 3: Add a focused websocket or direct service test**

Use a new direct service test or extend `test_ws_protocol.py` so that one narrow L2-driven path produces:

- an `ExecutionAck`
- and either a `PresentationCommand` or `WorldExecutionResult`

- [ ] **Step 4: Run focused tests**

Run from `backend/`:

```bash
python -m pytest -v tests/test_downlink_action_request.py tests/test_downlink_execution_gateway.py tests/test_ws_protocol.py
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/l2/character_agent/downlink_adapter.py backend/app/l2/character_agent/service.py backend/app/l2/siming/service.py backend/tests/test_ws_protocol.py
git commit -m "feat: connect l2 outputs to downlink v0 gateway"
```

### Task 8: Add Godot-Side Receivers For Presentation Commands

**Files:**
- Create or Modify: `scripts/presentation/character/CharacterActionReceiver.gd`
- Modify: `scripts/presentation/character/CharacterReplica.gd`
- Modify: `scripts/l6/backend_bridge/BackendBridge.gd`
- Modify: `scripts/l6/local_presentation_bus/LocalPresentationBus.gd`
- Modify: `scenes/phase0/MainDemo.tscn`

- [ ] **Step 1: Add a presentation command bus signal**

Add to `LocalPresentationBus.gd`:

```gdscript
signal presentation_command_received(payload)
```

Add dispatch handling to `BackendBridge.gd` for a new `presentation_command` message type:

```gdscript
"presentation_command":
    _bus_emit("presentation_command_received", [payload])
```

- [ ] **Step 2: Add a minimal receiver that can handle `orient_to_target` and `speak_to_actor`**

`CharacterActionReceiver.gd` should:

- receive a payload,
- check target actor,
- call `perform_action("observe")` or `perform_action("speak")`,
- optionally set look target if target coordinates or ids are present.

- [ ] **Step 3: Wire the receiver into `CharacterReplica` or the scene**

Keep it minimal.
Do not rewrite presentation architecture broadly.

- [ ] **Step 4: Add a narrow runtime verification**

Use one log-based or screenshot-based verification proving:

- a backend-issued `presentation_command` can reach a character and change local presentation.

- [ ] **Step 5: Commit**

```bash
git add scripts/presentation/character/CharacterActionReceiver.gd scripts/presentation/character/CharacterReplica.gd scripts/l6/backend_bridge/BackendBridge.gd scripts/l6/local_presentation_bus/LocalPresentationBus.gd scenes/phase0/MainDemo.tscn
git commit -m "feat: add Godot presentation command receiver"
```

### Task 9: Final Verification

**Files:**
- Modify: `docs/superpowers/specs/2026-06-08-architecture-realignment-and-downlink-prep-design.md`
- Modify: `docs/superpowers/plans/2026-06-08-stage2-merge-and-downlink-v0-implementation-plan.md`

- [ ] **Step 1: Run the full backend test suite**

Run from `backend/`:

```bash
python -m pytest -v
```

Expected:

- PASS

- [ ] **Step 2: Re-run existing verification scripts**

Run from repo root:

```bash
python scripts/verification/verify_phase0.py
python scripts/verification/verify_phase1_slice.py
python scripts/verification/verify_l1_runtime_edges.py
```

Expected:

- PASS

- [ ] **Step 3: Add one explicit downlink proof command**

Run from `backend/` or repo root, depending on the final harness:

```bash
rg -n "presentation_command|ExecutionAck|execute_action_request|ActionRequest" backend scripts
```

Expected:

- the real downlink v0 path is now present in both backend and Godot code

- [ ] **Step 4: Record closeout notes**

Add a final section to the spec summarizing:

- which merged systems now live behind the Stage 1 seams,
- which physical relocation work was completed,
- which downlink actions are supported in v0,
- and what still remains for full `L3/L4/L5`.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-06-08-architecture-realignment-and-downlink-prep-design.md docs/superpowers/plans/2026-06-08-stage2-merge-and-downlink-v0-implementation-plan.md
git commit -m "docs: record stage2 merge and downlink v0 closeout"
```

## Execution Handoff

This Stage 2 plan is only valid after the enhanced `ESM`, `Siming`, and event-bus branches have merged.

Until then:

- Stage 1 is the active completed preparation layer
- Stage 2 remains queued
- downlink v0 should not be started on top of incomplete merged implementations

