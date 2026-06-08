# Stage 1 Architecture Realignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce stable `L1/L2/L6` package seams, explicit `L3/L4/L5` placeholders, and merge-ready facades without changing current Phase 0 runtime behavior.

**Architecture:** Keep all existing runtime behavior on the current implementation paths, and add a new architecture skeleton beside it. New backend entrypoints should re-export or delegate to current implementations instead of moving them immediately. New Godot-side scripts should be compatibility shells that point at current scripts so the repository gains the target structure now, while enhanced `ESM`, `Siming`, and event-bus branches can merge into stable slots later.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, pytest, Godot 4.x GDScript, current Phase 0 verification scripts.

---

## Execution Status

Stage 1 implementation has been completed in the current worktree.

Completed results:

- backend layer skeleton and explicit `L3/L4/L5` placeholders were added
- stable `contracts/` entrypoints were added
- merge-ready `ESM / Siming / authority_bus / perception_chain / replay_audit` facades were added
- Godot-side `scripts/l6/*` and `scripts/presentation/*` shell paths were added
- architecture entrypoint tests were added
- authority-bus guardrail coverage was added to `backend/tests/test_ws_protocol.py`
- Stage 1 closeout notes were written back into the architecture spec

Verified results:

- from `backend/`: `python -m pytest -v tests/test_architecture_entrypoints.py`
- from `backend/`: `python -m pytest -v tests/test_esm_service.py tests/test_siming_service.py tests/test_ws_protocol.py`
- from `backend/`: `python -m pytest -v`
- from repo root:
  - `python scripts/verification/verify_phase0.py`
  - `python scripts/verification/verify_phase1_slice.py`
  - `python scripts/verification/verify_l1_runtime_edges.py`

Observed outcome:

- backend test suite: `112 passed`
- `verify_phase0.py`: `overall_strict_phase0_passed=True`
- `verify_phase1_slice.py`: `overall_phase1_slice_passed=True`
- `verify_l1_runtime_edges.py`: `overall_l1_runtime_edges_passed=True`

Important note:

- the implementation work is present in the worktree, but the per-task commit steps in this plan have **not** been executed yet
- if you want commit-by-commit history, replay the plan in smaller commits from the current tree or create intentional grouped commits now

---

## File Map

### Backend architecture skeleton

- Create: `backend/app/l1/__init__.py`
- Create: `backend/app/l1/esm/__init__.py`
- Create: `backend/app/l1/esm/service.py`
- Create: `backend/app/l2/__init__.py`
- Create: `backend/app/l2/character_agent/__init__.py`
- Create: `backend/app/l2/character_agent/service.py`
- Create: `backend/app/l2/siming/__init__.py`
- Create: `backend/app/l2/siming/service.py`
- Create: `backend/app/l3/__init__.py`
- Create: `backend/app/l3/README.md`
- Create: `backend/app/l4/__init__.py`
- Create: `backend/app/l4/README.md`
- Create: `backend/app/l5/__init__.py`
- Create: `backend/app/l5/README.md`
- Create: `backend/app/l6/__init__.py`
- Create: `backend/app/l6/authority_bus/__init__.py`
- Create: `backend/app/l6/authority_bus/ingress.py`
- Create: `backend/app/l6/authority_bus/router.py`
- Create: `backend/app/l6/authority_bus/message_types.py`
- Create: `backend/app/l6/perception_chain/__init__.py`
- Create: `backend/app/l6/perception_chain/candidate_compiler.py`
- Create: `backend/app/l6/perception_chain/per_character_filter.py`
- Create: `backend/app/l6/perception_chain/perceived_event_dispatch.py`
- Create: `backend/app/l6/replay_audit/__init__.py`
- Create: `backend/app/l6/replay_audit/debug_stream.py`
- Create: `backend/app/l6/replay_audit/event_trace.py`
- Create: `backend/app/l6/replay_audit/verification_audit.py`

### Backend contracts and merge facades

- Create: `backend/app/contracts/__init__.py`
- Create: `backend/app/contracts/l1/__init__.py`
- Create: `backend/app/contracts/l1/action_request.py`
- Create: `backend/app/contracts/l1/presentation_command.py`
- Create: `backend/app/contracts/l1/execution_ack.py`
- Create: `backend/app/contracts/l1/world_execution_result.py`
- Create: `backend/app/contracts/l2/__init__.py`
- Create: `backend/app/contracts/l2/character_output.py`
- Create: `backend/app/contracts/l2/siming_message.py`
- Create: `backend/app/contracts/l6/__init__.py`
- Create: `backend/app/contracts/l6/envelope.py`
- Create: `backend/app/contracts/l6/raw_fact.py`
- Create: `backend/app/contracts/l6/candidate_percept.py`
- Create: `backend/app/contracts/l6/character_perceived.py`
- Create: `backend/app/adapters/__init__.py`
- Create: `backend/app/adapters/branch_merge/__init__.py`
- Create: `backend/app/adapters/branch_merge/esm_facade.py`
- Create: `backend/app/adapters/branch_merge/siming_facade.py`
- Create: `backend/app/adapters/branch_merge/bus_facade.py`

### Godot architecture shells

- Create: `scripts/l6/backend_bridge/BackendBridge.gd`
- Create: `scripts/l6/local_presentation_bus/LocalPresentationBus.gd`
- Create: `scripts/presentation/character/CharacterReplica.gd`
- Create: `scripts/presentation/object/InteractiveObject.gd`
- Create: `scripts/presentation/environment/EnvironmentStateController.gd`
- Create: `scripts/presentation/audio/SpatialVoiceController.gd`

### Tests

- Create: `backend/tests/test_architecture_entrypoints.py`
- Modify: `backend/tests/test_ws_protocol.py`
- Modify: `backend/tests/test_siming_service.py`
- Modify: `backend/tests/test_esm_service.py`

### Verification

- Reuse: `scripts/verification/verify_phase0.py`
- Reuse: `scripts/verification/verify_phase1_slice.py`
- Reuse: `scripts/verification/verify_l1_runtime_edges.py`

---

### Task 1: Create The Backend Layer Skeleton And Placeholder Packages

**Files:**
- Create: `backend/app/l1/__init__.py`
- Create: `backend/app/l1/esm/__init__.py`
- Create: `backend/app/l2/__init__.py`
- Create: `backend/app/l2/character_agent/__init__.py`
- Create: `backend/app/l2/siming/__init__.py`
- Create: `backend/app/l3/__init__.py`
- Create: `backend/app/l3/README.md`
- Create: `backend/app/l4/__init__.py`
- Create: `backend/app/l4/README.md`
- Create: `backend/app/l5/__init__.py`
- Create: `backend/app/l5/README.md`
- Create: `backend/app/l6/__init__.py`
- Create: `backend/app/l6/authority_bus/__init__.py`
- Create: `backend/app/l6/perception_chain/__init__.py`
- Create: `backend/app/l6/replay_audit/__init__.py`
- Create: `backend/tests/test_architecture_entrypoints.py`

- [ ] **Step 1: Write the failing package-layout test**

Create `backend/tests/test_architecture_entrypoints.py` with:

```python
from importlib import import_module


def test_backend_layer_packages_exist() -> None:
    assert import_module("app.l1") is not None
    assert import_module("app.l1.esm") is not None
    assert import_module("app.l2") is not None
    assert import_module("app.l2.character_agent") is not None
    assert import_module("app.l2.siming") is not None
    assert import_module("app.l3") is not None
    assert import_module("app.l4") is not None
    assert import_module("app.l5") is not None
    assert import_module("app.l6") is not None
    assert import_module("app.l6.authority_bus") is not None
    assert import_module("app.l6.perception_chain") is not None
    assert import_module("app.l6.replay_audit") is not None
```

- [ ] **Step 2: Run the test to verify it fails**

Run from `backend/`:

```bash
python -m pytest -v tests/test_architecture_entrypoints.py::test_backend_layer_packages_exist
```

Expected:

- FAIL with `ModuleNotFoundError` for `app.l1` and the other new packages.

- [ ] **Step 3: Create the package skeleton and placeholder docs**

Create these minimal files:

`backend/app/l1/__init__.py`

```python
"""System-level L1 package."""
```

`backend/app/l1/esm/__init__.py`

```python
"""System-level L1 ESM namespace."""
```

`backend/app/l2/__init__.py`

```python
"""System-level L2 package."""
```

`backend/app/l2/character_agent/__init__.py`

```python
"""Character-agent namespace."""
```

`backend/app/l2/siming/__init__.py`

```python
"""Siming namespace."""
```

`backend/app/l3/__init__.py`

```python
"""System-level L3 placeholder package."""
```

`backend/app/l3/README.md`

```markdown
# L3 Placeholder

This package is intentionally present before implementation.

Status: unimplemented placeholder for the main-project L3 layer.
```

`backend/app/l4/__init__.py`

```python
"""System-level L4 placeholder package."""
```

`backend/app/l4/README.md`

```markdown
# L4 Placeholder

This package is intentionally present before implementation.

Status: unimplemented placeholder for the main-project L4 layer.
```

`backend/app/l5/__init__.py`

```python
"""System-level L5 placeholder package."""
```

`backend/app/l5/README.md`

```markdown
# L5 Placeholder

This package is intentionally present before implementation.

Status: unimplemented placeholder for the main-project L5 layer.
```

`backend/app/l6/__init__.py`

```python
"""System-level L6 package."""
```

`backend/app/l6/authority_bus/__init__.py`

```python
"""Authority-bus namespace."""
```

`backend/app/l6/perception_chain/__init__.py`

```python
"""Perception-chain namespace."""
```

`backend/app/l6/replay_audit/__init__.py`

```python
"""Replay/audit namespace."""
```

- [ ] **Step 4: Run the package-layout test again**

Run from `backend/`:

```bash
python -m pytest -v tests/test_architecture_entrypoints.py::test_backend_layer_packages_exist
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/l1 backend/app/l2 backend/app/l3 backend/app/l4 backend/app/l5 backend/app/l6 backend/tests/test_architecture_entrypoints.py
git commit -m "chore: add backend layer package skeleton"
```

### Task 2: Introduce Merge-Ready Contract Modules Without Changing Behavior

**Files:**
- Create: `backend/app/contracts/__init__.py`
- Create: `backend/app/contracts/l1/__init__.py`
- Create: `backend/app/contracts/l1/action_request.py`
- Create: `backend/app/contracts/l1/presentation_command.py`
- Create: `backend/app/contracts/l1/execution_ack.py`
- Create: `backend/app/contracts/l1/world_execution_result.py`
- Create: `backend/app/contracts/l2/__init__.py`
- Create: `backend/app/contracts/l2/character_output.py`
- Create: `backend/app/contracts/l2/siming_message.py`
- Create: `backend/app/contracts/l6/__init__.py`
- Create: `backend/app/contracts/l6/envelope.py`
- Create: `backend/app/contracts/l6/raw_fact.py`
- Create: `backend/app/contracts/l6/candidate_percept.py`
- Create: `backend/app/contracts/l6/character_perceived.py`
- Modify: `backend/tests/test_architecture_entrypoints.py`

- [ ] **Step 1: Add failing contract-entrypoint tests**

Append to `backend/tests/test_architecture_entrypoints.py`:

```python
def test_contract_entrypoints_exist() -> None:
    from app.contracts.l1.action_request import ActionRequest
    from app.contracts.l1.execution_ack import ExecutionAck
    from app.contracts.l1.presentation_command import PresentationCommand
    from app.contracts.l1.world_execution_result import WorldExecutionResult
    from app.contracts.l6.envelope import EnvelopeContract
    from app.contracts.l6.raw_fact import RawFactContract
    from app.contracts.l6.candidate_percept import CandidatePerceptContract
    from app.contracts.l6.character_perceived import CharacterPerceivedContract

    assert ActionRequest.__name__ == "ActionRequest"
    assert ExecutionAck.__name__ == "ExecutionAck"
    assert PresentationCommand.__name__ == "PresentationCommand"
    assert WorldExecutionResult.__name__ == "WorldExecutionResult"
    assert EnvelopeContract.__name__ == "EnvelopeContract"
    assert RawFactContract.__name__ == "RawFactContract"
    assert CandidatePerceptContract.__name__ == "CandidatePerceptContract"
    assert CharacterPerceivedContract.__name__ == "CharacterPerceivedContract"
```

- [ ] **Step 2: Run the contract test to verify failure**

Run from `backend/`:

```bash
python -m pytest -v tests/test_architecture_entrypoints.py::test_contract_entrypoints_exist
```

Expected:

- FAIL with import errors because the contract modules do not exist yet.

- [ ] **Step 3: Create the contract modules**

Create `backend/app/contracts/l1/action_request.py`:

```python
from pydantic import BaseModel, Field


class ActionRequest(BaseModel):
    request_id: str
    actor_id: str
    action_type: str
    target_actor_id: str = ""
    target_object_id: str = ""
    target_environment_id: str = ""
    payload: dict[str, object] = Field(default_factory=dict)
```

Create `backend/app/contracts/l1/presentation_command.py`:

```python
from pydantic import BaseModel, Field


class PresentationCommand(BaseModel):
    command_id: str
    actor_id: str
    command_type: str
    payload: dict[str, object] = Field(default_factory=dict)
```

Create `backend/app/contracts/l1/execution_ack.py`:

```python
from pydantic import BaseModel


class ExecutionAck(BaseModel):
    request_id: str
    accepted: bool
    execution_lane: str
    rejection_reason: str = ""
```

Create `backend/app/contracts/l1/world_execution_result.py`:

```python
from pydantic import BaseModel, Field


class WorldExecutionResult(BaseModel):
    request_id: str
    result_type: str
    payload: dict[str, object] = Field(default_factory=dict)
```

Create `backend/app/contracts/l6/envelope.py`:

```python
from pydantic import BaseModel, Field


class EnvelopeContract(BaseModel):
    message_type: str
    payload: dict[str, object] = Field(default_factory=dict)
```

Create `backend/app/contracts/l6/raw_fact.py`:

```python
from app.models.raw_fact import RawFactEvent


class RawFactContract(RawFactEvent):
    pass
```

Create `backend/app/contracts/l6/candidate_percept.py`:

```python
from app.models.candidate_percept import CandidatePerceptEvent


class CandidatePerceptContract(CandidatePerceptEvent):
    pass
```

Create `backend/app/contracts/l6/character_perceived.py`:

```python
from app.models.character_perceived import CharacterPerceivedEvent


class CharacterPerceivedContract(CharacterPerceivedEvent):
    pass
```

Create `backend/app/contracts/l2/character_output.py`:

```python
from app.models.ai_output import DialogueResponse


CharacterOutput = DialogueResponse
```

Create `backend/app/contracts/l2/siming_message.py`:

```python
from app.models.siming_output import AttentionPrompt


SimingMessage = AttentionPrompt
```

Create `backend/app/contracts/__init__.py`, `backend/app/contracts/l1/__init__.py`, `backend/app/contracts/l2/__init__.py`, and `backend/app/contracts/l6/__init__.py` with minimal package docstrings.

- [ ] **Step 4: Re-run the contract test**

Run from `backend/`:

```bash
python -m pytest -v tests/test_architecture_entrypoints.py::test_contract_entrypoints_exist
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/contracts backend/tests/test_architecture_entrypoints.py
git commit -m "chore: add stable contract entrypoints"
```

### Task 3: Add Merge-Ready Service And Bus Facades That Delegate To Current Implementations

**Files:**
- Create: `backend/app/l1/esm/service.py`
- Create: `backend/app/l2/character_agent/service.py`
- Create: `backend/app/l2/siming/service.py`
- Create: `backend/app/l6/authority_bus/ingress.py`
- Create: `backend/app/l6/authority_bus/router.py`
- Create: `backend/app/l6/authority_bus/message_types.py`
- Create: `backend/app/l6/perception_chain/candidate_compiler.py`
- Create: `backend/app/l6/perception_chain/per_character_filter.py`
- Create: `backend/app/l6/perception_chain/perceived_event_dispatch.py`
- Create: `backend/app/l6/replay_audit/debug_stream.py`
- Create: `backend/app/l6/replay_audit/event_trace.py`
- Create: `backend/app/l6/replay_audit/verification_audit.py`
- Create: `backend/app/adapters/__init__.py`
- Create: `backend/app/adapters/branch_merge/__init__.py`
- Create: `backend/app/adapters/branch_merge/esm_facade.py`
- Create: `backend/app/adapters/branch_merge/siming_facade.py`
- Create: `backend/app/adapters/branch_merge/bus_facade.py`
- Modify: `backend/tests/test_architecture_entrypoints.py`

- [ ] **Step 1: Add failing facade tests**

Append to `backend/tests/test_architecture_entrypoints.py`:

```python
def test_merge_ready_service_entrypoints_resolve_current_implementations() -> None:
    from app.l1.esm.service import ESMServiceEntry
    from app.l2.character_agent.service import CharacterServiceEntry
    from app.l2.siming.service import SimingServiceEntry
    from app.l6.authority_bus.router import handle_envelope_entry
    from app.l6.perception_chain.candidate_compiler import compile_candidate_percepts_entry
    from app.l6.perception_chain.per_character_filter import filter_candidate_for_actor_entry

    assert ESMServiceEntry.__name__ == "ESMService"
    assert CharacterServiceEntry.__name__ == "CharacterService"
    assert SimingServiceEntry.__name__ == "SimingService"
    assert callable(handle_envelope_entry)
    assert callable(compile_candidate_percepts_entry)
    assert callable(filter_candidate_for_actor_entry)
```

- [ ] **Step 2: Run the facade test to verify failure**

Run from `backend/`:

```bash
python -m pytest -v tests/test_architecture_entrypoints.py::test_merge_ready_service_entrypoints_resolve_current_implementations
```

Expected:

- FAIL with import errors because the façade modules do not exist yet.

- [ ] **Step 3: Create the façade modules**

Create `backend/app/l1/esm/service.py`:

```python
from app.services.esm_service import ESMService as ESMServiceEntry


__all__ = ["ESMServiceEntry"]
```

Create `backend/app/l2/character_agent/service.py`:

```python
from app.services.character_service import CharacterService as CharacterServiceEntry


__all__ = ["CharacterServiceEntry"]
```

Create `backend/app/l2/siming/service.py`:

```python
from app.services.siming_service import SimingService as SimingServiceEntry


__all__ = ["SimingServiceEntry"]
```

Create `backend/app/l6/authority_bus/router.py`:

```python
from app.main import _handle_envelope as handle_envelope_entry


__all__ = ["handle_envelope_entry"]
```

Create `backend/app/l6/authority_bus/ingress.py`:

```python
from app.ws_protocol import Envelope


EnvelopeEntry = Envelope


__all__ = ["EnvelopeEntry"]
```

Create `backend/app/l6/authority_bus/message_types.py`:

```python
KNOWN_MESSAGE_TYPES = (
    "player_input",
    "raw_fact_event",
    "visual_fact_event",
    "dialogue_response",
    "world_result",
    "siming_output",
)
```

Create `backend/app/l6/perception_chain/candidate_compiler.py`:

```python
from app.services.candidate_percept_service import compile_candidate_percepts as compile_candidate_percepts_entry


__all__ = ["compile_candidate_percepts_entry"]
```

Create `backend/app/l6/perception_chain/per_character_filter.py`:

```python
from app.services.per_character_percept_filter import filter_candidate_for_actor as filter_candidate_for_actor_entry


__all__ = ["filter_candidate_for_actor_entry"]
```

Create `backend/app/l6/perception_chain/perceived_event_dispatch.py`:

```python
from app.services.character_perceived_input_service import CharacterPerceivedInputService


CharacterPerceivedDispatchEntry = CharacterPerceivedInputService


__all__ = ["CharacterPerceivedDispatchEntry"]
```

Create `backend/app/l6/replay_audit/debug_stream.py`:

```python
from app.debug_stream import debug_stream as debug_stream_entry


__all__ = ["debug_stream_entry"]
```

Create `backend/app/l6/replay_audit/event_trace.py`:

```python
from app.services.event_trace_service import EventTraceService as EventTraceServiceEntry


__all__ = ["EventTraceServiceEntry"]
```

Create `backend/app/l6/replay_audit/verification_audit.py`:

```python
from app.verification_audit import evaluate_phase0_audit, evaluate_phase1_slice_audit


class VerificationAuditEntry:
    evaluate_phase0_audit = staticmethod(evaluate_phase0_audit)
    evaluate_phase1_slice_audit = staticmethod(evaluate_phase1_slice_audit)


__all__ = ["VerificationAuditEntry"]
```

Create `backend/app/adapters/branch_merge/esm_facade.py`:

```python
from app.l1.esm.service import ESMServiceEntry


__all__ = ["ESMServiceEntry"]
```

Create `backend/app/adapters/branch_merge/siming_facade.py`:

```python
from app.l2.siming.service import SimingServiceEntry


__all__ = ["SimingServiceEntry"]
```

Create `backend/app/adapters/branch_merge/bus_facade.py`:

```python
from app.l6.authority_bus.router import handle_envelope_entry


__all__ = ["handle_envelope_entry"]
```

Create `backend/app/adapters/__init__.py` and `backend/app/adapters/branch_merge/__init__.py` with minimal package docstrings.

- [ ] **Step 4: Re-run the façade test**

Run from `backend/`:

```bash
python -m pytest -v tests/test_architecture_entrypoints.py::test_merge_ready_service_entrypoints_resolve_current_implementations
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/l1/esm/service.py backend/app/l2/character_agent/service.py backend/app/l2/siming/service.py backend/app/l6 backend/app/adapters backend/tests/test_architecture_entrypoints.py
git commit -m "chore: add merge-ready service and bus facades"
```

### Task 4: Add Godot-Side Architecture Shell Scripts Without Rewiring Scenes

**Files:**
- Create: `scripts/l6/backend_bridge/BackendBridge.gd`
- Create: `scripts/l6/local_presentation_bus/LocalPresentationBus.gd`
- Create: `scripts/presentation/character/CharacterReplica.gd`
- Create: `scripts/presentation/object/InteractiveObject.gd`
- Create: `scripts/presentation/environment/EnvironmentStateController.gd`
- Create: `scripts/presentation/audio/SpatialVoiceController.gd`

- [ ] **Step 1: Add the shell scripts**

Create `scripts/l6/backend_bridge/BackendBridge.gd`:

```gdscript
extends "res://scripts/autoload/BackendBridge.gd"
```

Create `scripts/l6/local_presentation_bus/LocalPresentationBus.gd`:

```gdscript
extends "res://scripts/autoload/LocalPresentationBus.gd"
```

Create `scripts/presentation/character/CharacterReplica.gd`:

```gdscript
extends "res://scripts/character/CharacterReplica.gd"
```

Create `scripts/presentation/object/InteractiveObject.gd`:

```gdscript
extends "res://scripts/object/InteractiveObject.gd"
```

Create `scripts/presentation/environment/EnvironmentStateController.gd`:

```gdscript
extends "res://scripts/environment/EnvironmentStateController.gd"
```

Create `scripts/presentation/audio/SpatialVoiceController.gd`:

```gdscript
extends "res://scripts/audio/SpatialVoiceController.gd"
```

- [ ] **Step 2: Verify the files exist without touching scene paths**

Run from repo root:

```bash
rg -n "extends \"res://scripts/" scripts/l6 scripts/presentation
```

Expected:

- the new shell files exist
- each shell points to the current runtime implementation
- no `.tscn` paths changed yet

- [ ] **Step 3: Commit**

```bash
git add scripts/l6 scripts/presentation
git commit -m "chore: add Godot architecture shell paths"
```

### Task 5: Run No-Behavior-Change Verification

**Files:**
- Modify: `backend/tests/test_ws_protocol.py`
- Modify: `backend/tests/test_siming_service.py`
- Modify: `backend/tests/test_esm_service.py`

- [ ] **Step 1: Add one guardrail test that uses only new entrypoints**

Append to `backend/tests/test_ws_protocol.py`:

```python
def test_authority_bus_router_entrypoint_matches_legacy_behavior() -> None:
    from app.l6.authority_bus.router import handle_envelope_entry
    from app.ws_protocol import Envelope

    envelope = Envelope(
        message_type="player_input",
        payload={
            "player_id": "p1",
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "actor_id": "char_c",
            "intent_type": "move_intent",
            "producer_ts": 1,
            "move_mode": "locomotion",
            "target_point": [0.0, 0.5, 1.0],
        },
    )

    messages = handle_envelope_entry(envelope)

    assert messages[0]["message_type"] == "ack"
    assert messages[0]["payload"]["accepted"] is True
```

- [ ] **Step 2: Run the backend architecture and websocket guard tests**

Run from `backend/`:

```bash
python -m pytest -v tests/test_architecture_entrypoints.py tests/test_ws_protocol.py::test_authority_bus_router_entrypoint_matches_legacy_behavior
```

Expected:

- PASS

- [ ] **Step 3: Run focused backend suites to confirm no regression**

Run from `backend/`:

```bash
python -m pytest -v tests/test_esm_service.py tests/test_siming_service.py tests/test_ws_protocol.py
```

Expected:

- PASS

- [ ] **Step 4: Run full backend tests**

Run:

```bash
cd backend
python -m pytest -v
```

Expected:

- PASS

- [ ] **Step 5: Run existing verification scripts**

Run:

```bash
python scripts/verification/verify_phase0.py
python scripts/verification/verify_phase1_slice.py
python scripts/verification/verify_l1_runtime_edges.py
```

Expected:

- PASS

- [ ] **Step 6: Commit the guardrails**

```bash
git add backend/tests/test_ws_protocol.py backend/tests/test_esm_service.py backend/tests/test_siming_service.py
git commit -m "test: add no-regression guardrails for architecture seams"
```

### Task 6: Record Stage 1 Closeout And Freeze The Merge Handoff

**Files:**
- Modify: `docs/superpowers/specs/2026-06-08-architecture-realignment-and-downlink-prep-design.md`
- Modify: `docs/superpowers/plans/2026-06-08-stage1-architecture-realignment-implementation-plan.md`

- [ ] **Step 1: Confirm the repository now exposes the planned merge seams**

Run:

```bash
rg -n "ESMServiceEntry|SimingServiceEntry|handle_envelope_entry|compile_candidate_percepts_entry|filter_candidate_for_actor_entry" backend/app
```

Expected:

- the stable entrypoints appear only in the new architecture shell paths

- [ ] **Step 2: Add a short closeout note to the spec if needed**

If implementation exposed any constraint worth preserving, append a small section to `docs/superpowers/specs/2026-06-08-architecture-realignment-and-downlink-prep-design.md` like:

```markdown
## Stage 1 Closeout Notes

- Stage 1 introduced stable architecture entrypoints without relocating the legacy runtime files.
- Enhanced `ESM`, `Siming`, and authority-bus branches should merge into the new `app.l1.esm`, `app.l2.siming`, and `app.l6.authority_bus` seams instead of extending the legacy flat service bucket further.
```

- [ ] **Step 3: Commit the closeout**

```bash
git add docs/superpowers/specs/2026-06-08-architecture-realignment-and-downlink-prep-design.md docs/superpowers/plans/2026-06-08-stage1-architecture-realignment-implementation-plan.md
git commit -m "docs: record stage1 architecture realignment handoff"
```

- [ ] **Step 4: Prepare the next execution brief**

Write the closeout summary with:

- what Stage 1 completed,
- what remains blocked on branch merge,
- which entrypoints enhanced branches should target,
- and that downlink v0 should start only after the merged implementations are relocated cleanly.
