# Complete Siming Godot Event Bus Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the first frontend-safe Siming event-bus return path from backend authority events to Godot local presentation.

**Architecture:** Add a backend projection layer that whitelists selected Siming `AuthorityEvent` families and converts them to existing WebSocket envelopes. Extend Godot `BackendBridge` and `LocalPresentationBus` to dispatch those projected events, then add a minimal visual-observability presenter that proves the loop without replacing the legacy `siming_output` path.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, pytest, Godot 4 GDScript, existing Paralls harness profiles.

---

## Source Context

- OpenSpec proposal: `openspec/changes/complete-siming-godot-event-bus-loop/proposal.md`
- OpenSpec design: `openspec/changes/complete-siming-godot-event-bus-loop/design.md`
- OpenSpec spec: `openspec/changes/complete-siming-godot-event-bus-loop/specs/siming-godot-event-bus-loop/spec.md`
- Existing backend bus: `backend/app/services/authority_event_bus.py`
- Existing Siming producer: `backend/app/services/siming_event_producer.py`
- Existing backend entrypoint: `backend/app/main.py`
- Existing Godot websocket bridge: `scripts/autoload/BackendBridge.gd`
- Existing Godot local bus: `scripts/autoload/LocalPresentationBus.gd`
- Existing runtime trace parser: `scripts/verification/runtime_trace.py`
- Existing audit evaluator: `backend/app/verification_audit.py`

## File Structure

Create these backend files:

- `backend/app/services/frontend_authority_event_projection.py`: whitelists frontend-safe authority events and converts them to websocket envelopes.
- `backend/tests/test_frontend_authority_event_projection.py`: unit tests for projected and non-projected authority events.
- `backend/tests/test_ws_authority_event_projection.py`: regression tests proving `_handle_envelope()` returns projected Siming events after backend bus publication.

Create these Godot files:

- `scripts/phase0/SimingVisualObservabilityPresenter.gd`: local presentation consumer for `siming.visual_observability_request`.

Modify these existing files:

- `backend/app/main.py`: initialize the frontend projector, subscribe it to whitelisted Siming event families, and append projected websocket messages to outbound responses.
- `scripts/autoload/BackendBridge.gd`: dispatch `authority_event` websocket messages and emit family-specific local bus signals.
- `scripts/autoload/LocalPresentationBus.gd`: define generic and visual-observability authority event signals.
- `scenes/phase0/MainDemo.tscn`: add the presenter node.
- `scripts/verification/runtime_trace.py`: detect the event-bus return path and Godot presenter trace.
- `backend/app/verification_audit.py`: add a proof result for the Siming event-bus return path.
- `backend/tests/test_verification_audit.py`: cover the new trace-driven audit result.
- `scripts/verification/tests/test_runtime_trace.py`: cover new trace extraction tokens.
- `scripts/verification/check_boundaries.py`: assert the bridge, local bus, and presenter exist and preserve the no-direct-truth boundary.
- `scripts/verification/tests/test_boundary_checks.py`: assert the new boundary result ID.

---

### Task 1: Backend Frontend Projection Service

**Files:**
- Create: `backend/app/services/frontend_authority_event_projection.py`
- Create: `backend/tests/test_frontend_authority_event_projection.py`

- [ ] **Step 1: Write failing projection unit tests**

Create `backend/tests/test_frontend_authority_event_projection.py`:

```python
import pytest

from app.models.authority_event import AuthorityEvent
from app.services.frontend_authority_event_projection import (
    FRONTEND_AUTHORITY_EVENT_TYPES,
    FrontendAuthorityEventProjector,
    project_authority_event_for_frontend,
)
from tests.test_authority_event import valid_event_dict


def make_event(event_type: str, payload: dict[str, object] | None = None) -> AuthorityEvent:
    data = valid_event_dict()
    data["event_id"] = f"evt_{event_type.replace('.', '_')}"
    data["event_type"] = event_type
    data["payload"] = payload or {
        "established_fact_id": "visual_fact:300:char_c:light_level_drop",
        "presentation_hint": "increase observability for established light change",
    }
    return AuthorityEvent.model_validate(data)


def test_projector_whitelists_visual_observability_request() -> None:
    envelope = project_authority_event_for_frontend(make_event("siming.visual_observability_request"))

    assert envelope is not None
    assert envelope["message_type"] == "authority_event"
    payload = envelope["payload"]
    assert payload["event_type"] == "siming.visual_observability_request"
    assert payload["event_id"] == "evt_siming_visual_observability_request"
    assert payload["causation_id"] == "visual_fact:100"
    assert payload["correlation_id"] == "visual_fact:100"
    assert payload["durability"] == "replayable"
    assert payload["payload"]["established_fact_id"] == "visual_fact:300:char_c:light_level_drop"


@pytest.mark.parametrize("event_type", ["siming.audit_recorded", "siming.fairness_snapshot", "visual_fact_event"])
def test_projector_rejects_non_frontend_event_families(event_type: str) -> None:
    assert project_authority_event_for_frontend(make_event(event_type)) is None


def test_projector_buffers_and_drains_projected_events() -> None:
    projector = FrontendAuthorityEventProjector()

    projector.handle_event(make_event("siming.visual_observability_request"))
    projector.handle_event(make_event("siming.audit_recorded"))

    drained = projector.drain()
    assert [message["payload"]["event_type"] for message in drained] == ["siming.visual_observability_request"]
    assert projector.drain() == []


def test_projector_can_clear_stale_pending_events() -> None:
    projector = FrontendAuthorityEventProjector()
    projector.handle_event(make_event("siming.visual_observability_request"))

    projector.clear()

    assert projector.drain() == []
    assert "siming.visual_observability_request" in FRONTEND_AUTHORITY_EVENT_TYPES
```

- [ ] **Step 2: Run the failing projection tests**

Run:

```powershell
python -m pytest -q backend/tests/test_frontend_authority_event_projection.py
```

Expected: fail because `app.services.frontend_authority_event_projection` does not exist.

- [ ] **Step 3: Implement the projection service**

Create `backend/app/services/frontend_authority_event_projection.py`:

```python
from typing import Any

from app.models.authority_event import AuthorityEvent


FRONTEND_AUTHORITY_EVENT_TYPES = {
    "siming.visual_observability_request",
}


def project_authority_event_for_frontend(event: AuthorityEvent) -> dict[str, object] | None:
    if event.event_type not in FRONTEND_AUTHORITY_EVENT_TYPES:
        return None
    return {
        "message_type": "authority_event",
        "payload": event.model_dump(exclude_none=True),
    }


class FrontendAuthorityEventProjector:
    def __init__(self) -> None:
        self._pending: list[dict[str, object]] = []

    def handle_event(self, event: AuthorityEvent) -> None:
        envelope = project_authority_event_for_frontend(event)
        if envelope is not None:
            self._pending.append(envelope)

    def drain(self) -> list[dict[str, object]]:
        pending = self._pending
        self._pending = []
        return pending

    def clear(self) -> None:
        self._pending = []
```

- [ ] **Step 4: Run projection tests to verify pass**

Run:

```powershell
python -m pytest -q backend/tests/test_frontend_authority_event_projection.py
```

Expected: `4 passed`.

---

### Task 2: Backend WebSocket Outbound Projection

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_ws_authority_event_projection.py`
- Modify: `backend/tests/test_ws_authority_event_dual_write.py`

- [ ] **Step 1: Write failing websocket projection tests**

Create `backend/tests/test_ws_authority_event_projection.py`:

```python
import app.main as main
from app.models.visual_fact import VisualFactEvent
from app.ws_protocol import Envelope


def test_visual_fact_light_drop_returns_projected_siming_authority_event() -> None:
    main.reset_runtime_state()

    outbound = main._handle_envelope(
        Envelope(
            message_type="visual_fact_event",
            payload=VisualFactEvent(
                actor_id="char_c",
                room_id="room_demo",
                scene_id="scene_demo",
                zone_id="zone_focus",
                producer_ts=300,
                fact_type="light_level_drop",
                relation_type="environment_light_drop",
                target_environment_id="env_lamp",
            ).model_dump(),
        )
    )

    projected = [
        message
        for message in outbound
        if message.get("message_type") == "authority_event"
        and message.get("payload", {}).get("event_type") == "siming.visual_observability_request"
    ]
    assert len(projected) == 1
    payload = projected[0]["payload"]
    assert payload["payload"]["established_fact_id"].startswith("visual_fact:300:char_c:light_level_drop")
    assert payload["payload"]["presentation_hint"] == "increase observability for established light change"


def test_non_visual_siming_events_are_not_returned_to_websocket() -> None:
    main.reset_runtime_state()

    outbound = main._handle_envelope(
        Envelope(
            message_type="visual_fact_event",
            payload=VisualFactEvent(
                actor_id="char_c",
                room_id="room_demo",
                scene_id="scene_demo",
                zone_id="zone_focus",
                producer_ts=301,
                fact_type="actor_looks_at_object",
                relation_type="fixed_gaze_on_target",
                target_object_id="obj_letter",
            ).model_dump(),
        )
    )

    assert all(message.get("message_type") != "authority_event" for message in outbound)
```

- [ ] **Step 2: Run failing websocket projection tests**

Run:

```powershell
python -m pytest -q backend/tests/test_ws_authority_event_projection.py
```

Expected: fail because `_handle_envelope()` does not append projected authority events to outbound messages.

- [ ] **Step 3: Wire projector initialization and subscriptions**

Modify `backend/app/main.py` imports:

```python
from app.services.frontend_authority_event_projection import (
    FRONTEND_AUTHORITY_EVENT_TYPES,
    FrontendAuthorityEventProjector,
)
```

In `reset_runtime_state()`, add the global and subscribe projector after `siming_event_pipeline` subscriptions:

```python
    global frontend_authority_event_projector
```

```python
    frontend_authority_event_projector = FrontendAuthorityEventProjector()
    for event_type in FRONTEND_AUTHORITY_EVENT_TYPES:
        authority_event_bus.subscribe(event_type, frontend_authority_event_projector.handle_event)
```

- [ ] **Step 4: Add outbound finalizer**

Add this helper near `_publish_authority_event()`:

```python
def _with_frontend_authority_events(messages: list[dict[str, object]]) -> list[dict[str, object]]:
    messages.extend(frontend_authority_event_projector.drain())
    return messages
```

At the top of `_handle_envelope()`, clear stale projected messages:

```python
    frontend_authority_event_projector.clear()
```

Replace every `return messages` in `_handle_envelope()` with:

```python
    return _with_frontend_authority_events(messages)
```

Replace direct list returns in `_handle_envelope()` with:

```python
    return _with_frontend_authority_events(
        [
            {
                "message_type": "ack",
                "payload": {
                    "source_type": envelope.message_type,
                    "route": "ignored",
                },
            }
        ]
    )
```

Use the existing payload fields for each direct return; only wrap the returned list.

- [ ] **Step 5: Preserve existing dual-write test expectations**

Modify `backend/tests/test_ws_authority_event_dual_write.py` only if it assumes exact outbound length. Keep these assertions valid:

```python
assert outbound[0]["message_type"] == "ack"
event_types = [event.event_type for event in main.authority_event_bus.list_events()]
assert "visual_fact_event" in event_types
assert "siming.visual_observability_request" in event_types
```

- [ ] **Step 6: Run backend projection and dual-write tests**

Run:

```powershell
python -m pytest -q backend/tests/test_frontend_authority_event_projection.py backend/tests/test_ws_authority_event_projection.py backend/tests/test_ws_authority_event_dual_write.py
```

Expected: all selected tests pass.

---

### Task 3: Godot Bridge And Local Bus Dispatch

**Files:**
- Modify: `scripts/autoload/LocalPresentationBus.gd`
- Modify: `scripts/autoload/BackendBridge.gd`
- Modify: `scripts/verification/check_boundaries.py`
- Modify: `scripts/verification/tests/test_boundary_checks.py`

- [ ] **Step 1: Add failing static boundary assertions**

In `scripts/verification/check_boundaries.py`, add a result named `siming_projected_event_reaches_godot_bus` that checks:

```python
backend_bridge = project_root / "scripts" / "autoload" / "BackendBridge.gd"
local_bus = project_root / "scripts" / "autoload" / "LocalPresentationBus.gd"
presenter = project_root / "scripts" / "phase0" / "SimingVisualObservabilityPresenter.gd"
```

The result should require:

```python
_contains(backend_bridge, ['"authority_event"', 'siming.visual_observability_request', 'siming_visual_observability_requested'])
and _contains(local_bus, ["signal authority_event_received", "signal siming_visual_observability_requested"])
and _contains(presenter, ["siming_visual_observability_requested.connect", "siming_visual_observability_applied"])
```

In `scripts/verification/tests/test_boundary_checks.py`, assert:

```python
assert statuses["siming_projected_event_reaches_godot_bus"] == "proved"
```

- [ ] **Step 2: Run failing boundary test**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_boundary_checks.py
```

Expected: fail because the bridge/local bus/presenter tokens are missing.

- [ ] **Step 3: Add LocalPresentationBus signals**

Modify `scripts/autoload/LocalPresentationBus.gd`:

```gdscript
signal authority_event_received(payload)
signal siming_visual_observability_requested(payload)
signal authority_event_unhandled(payload)
```

- [ ] **Step 4: Dispatch authority events in BackendBridge**

Modify `scripts/autoload/BackendBridge.gd` in `_dispatch_message()`:

```gdscript
        "authority_event":
            _dispatch_authority_event(payload)
```

Add this function below `_dispatch_message()`:

```gdscript
func _dispatch_authority_event(payload: Dictionary) -> void:
    _bus_emit("authority_event_received", [payload])
    var event_type := str(payload.get("event_type", ""))
    match event_type:
        "siming.visual_observability_request":
            _bus_log("siming_visual_observability_request:%s" % JSON.stringify(payload))
            _bus_emit("siming_visual_observability_requested", [payload])
        _:
            _bus_log("authority_event_unhandled:%s" % event_type)
            _bus_emit("authority_event_unhandled", [payload])
```

- [ ] **Step 5: Run static boundary tests**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_boundary_checks.py
```

Expected: still fail until the presenter exists, then pass after Task 4.

---

### Task 4: Godot Visual Observability Presenter

**Files:**
- Create: `scripts/phase0/SimingVisualObservabilityPresenter.gd`
- Modify: `scenes/phase0/MainDemo.tscn`
- Modify: `scripts/verification/tests/test_phase0_player_scene.py`

- [ ] **Step 1: Add failing scene/static test**

Modify `scripts/verification/tests/test_phase0_player_scene.py` with:

```python
from pathlib import Path


def test_main_demo_wires_siming_visual_observability_presenter() -> None:
    root = Path(__file__).resolve().parents[3]
    scene_text = (root / "scenes" / "phase0" / "MainDemo.tscn").read_text(encoding="utf-8")
    script_text = (root / "scripts" / "phase0" / "SimingVisualObservabilityPresenter.gd").read_text(encoding="utf-8")

    assert "SimingVisualObservabilityPresenter" in scene_text
    assert "siming_visual_observability_requested.connect" in script_text
    assert "siming_visual_observability_applied" in script_text
    assert "siming_visual_observability_rejected" in script_text
```

- [ ] **Step 2: Run failing scene/static test**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_phase0_player_scene.py::test_main_demo_wires_siming_visual_observability_presenter
```

Expected: fail because `SimingVisualObservabilityPresenter.gd` does not exist.

- [ ] **Step 3: Create the presenter script**

Create `scripts/phase0/SimingVisualObservabilityPresenter.gd`:

```gdscript
extends Node

var applied_fact_ids: Array[String] = []

func _ready() -> void:
    var bus := _get_bus()
    if bus and bus.has_signal("siming_visual_observability_requested"):
        bus.siming_visual_observability_requested.connect(_on_siming_visual_observability_requested)

func _on_siming_visual_observability_requested(event: Dictionary) -> void:
    var payload: Dictionary = event.get("payload", {})
    var established_fact_id := str(payload.get("established_fact_id", ""))
    if established_fact_id.is_empty():
        _bus_log("siming_visual_observability_rejected:missing_established_fact_id")
        return

    applied_fact_ids.append(established_fact_id)
    var presentation_hint := str(payload.get("presentation_hint", ""))
    _bus_log("siming_visual_observability_applied:%s:%s" % [established_fact_id, presentation_hint])

func _get_bus() -> Node:
    return get_node_or_null("/root/LocalPresentationBus")

func _bus_log(message: String) -> void:
    var bus := _get_bus()
    if bus and bus.has_method("log_debug"):
        bus.log_debug(message)
```

- [ ] **Step 4: Wire the presenter into MainDemo scene**

Modify `scenes/phase0/MainDemo.tscn` to add an external resource:

```ini
[ext_resource type="Script" path="res://scripts/phase0/SimingVisualObservabilityPresenter.gd" id="siming_visual_observability_presenter"]
```

Add a node under the scene root:

```ini
[node name="SimingVisualObservabilityPresenter" type="Node" parent="."]
script = ExtResource("siming_visual_observability_presenter")
```

Use a unique ext_resource ID that does not conflict with existing IDs in the file.

- [ ] **Step 5: Run scene/static and boundary tests**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_phase0_player_scene.py::test_main_demo_wires_siming_visual_observability_presenter scripts/verification/tests/test_boundary_checks.py
```

Expected: pass.

---

### Task 5: Runtime Trace And Audit Proof

**Files:**
- Modify: `scripts/verification/runtime_trace.py`
- Modify: `backend/app/verification_audit.py`
- Modify: `backend/tests/test_verification_audit.py`
- Modify: `scripts/verification/tests/test_runtime_trace.py`

- [ ] **Step 1: Write failing runtime trace tests**

Modify `scripts/verification/tests/test_runtime_trace.py` with:

```python
def test_runtime_trace_detects_siming_event_bus_return_path() -> None:
    events = extract_runtime_trace(
        {
            "main": "\n".join(
                [
                    "[LocalPresentationBus] backend_message_type:authority_event",
                    "[LocalPresentationBus] siming_visual_observability_request:{\"event_type\":\"siming.visual_observability_request\"}",
                    "[LocalPresentationBus] siming_visual_observability_applied:visual_fact:300:char_c:light_level_drop:increase observability for established light change",
                ]
            )
        }
    )

    event_types = [event["event_type"] for event in events]
    assert "siming_authority_event_observed" in event_types
    assert "siming_visual_observability_requested" in event_types
    assert "siming_visual_observability_applied" in event_types
```

Modify `backend/tests/test_verification_audit.py` with:

```python
def test_phase1_slice_audit_requires_siming_event_bus_return_path_when_trace_available() -> None:
    report = evaluate_phase1_slice_audit(
        main_log="",
        focus_log="",
        direct_send_scan="",
        scene_text='[node name="VisualFactEmitter" type="Node" parent="."]',
        candidate_policy_source='AUDITORY_CANDIDATE_POLICY = "l1_only"',
        trace_events=[
            {"event_type": "visual_fact_emitted", "result_id": "visual_fact_pipeline", "raw": "actor_looks_at_object"},
            {"event_type": "visual_fact_emitted", "result_id": "visual_fact_pipeline", "raw": "actor_looks_at_actor"},
            {"event_type": "visual_fact_emitted", "result_id": "visual_fact_pipeline", "raw": "actor_near_object"},
            {"event_type": "visual_fact_emitted", "result_id": "visual_fact_pipeline", "raw": "environment_light_drop"},
            {"event_type": "visual_fact_emitted", "result_id": "evidence_projection_visual_fact_observed", "raw": "evidence_projection"},
            {"event_type": "auditory_fact_observed", "result_id": "auditory_fact_observed"},
            {"event_type": "role_state_fact_observed", "result_id": "role_state_fact_observed"},
            {"event_type": "physiology_fact_observed", "result_id": "physiology_fact_observed"},
            {"event_type": "tactile_fact_observed", "result_id": "tactile_fact_observed"},
            {"event_type": "thermal_fact_observed", "result_id": "thermal_fact_observed"},
            {"event_type": "olfactory_fact_observed", "result_id": "olfactory_fact_observed"},
            {"event_type": "authority_visual_fact_ack", "result_id": "authority_ack_observed"},
            {"event_type": "runtime_projection_observed", "result_id": "runtime_projection_observed", "raw": "visual_fact"},
            {"event_type": "conversation_candidate_observed", "result_id": "candidate_and_siming_observed"},
            {"event_type": "siming_attention_applied", "result_id": "candidate_and_siming_observed"},
            {"event_type": "siming_authority_event_observed", "result_id": "siming_event_bus_return_path"},
            {"event_type": "siming_visual_observability_requested", "result_id": "siming_event_bus_return_path"},
            {"event_type": "siming_visual_observability_applied", "result_id": "siming_event_bus_return_path"},
        ],
    )

    results = _index_by_id(report["results"])
    assert results["siming_event_bus_return_path"]["status"] == "proved"
```

- [ ] **Step 2: Run failing trace and audit tests**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_runtime_trace.py backend/tests/test_verification_audit.py
```

Expected: fail because new event types and audit result are missing.

- [ ] **Step 3: Extend runtime trace tokens**

Modify `scripts/verification/runtime_trace.py` by adding tokens:

```python
("backend_message_type:authority_event", "siming_authority_event_observed", "siming_event_bus_return_path"),
("siming_visual_observability_request:", "siming_visual_observability_requested", "siming_event_bus_return_path"),
("siming_visual_observability_applied:", "siming_visual_observability_applied", "siming_event_bus_return_path"),
```

- [ ] **Step 4: Add audit result**

Modify `backend/app/verification_audit.py` inside `evaluate_phase1_slice_audit()`:

```python
    siming_event_bus_return_path_ok = (
        _trace_has(trace_events, event_type="siming_authority_event_observed")
        and _trace_has(trace_events, event_type="siming_visual_observability_requested")
        and _trace_has(trace_events, event_type="siming_visual_observability_applied")
    )
    results.append(
        _result(
            "siming_event_bus_return_path",
            "Siming authority event family returns through WebSocket and Godot local presentation bus",
            "proved" if siming_event_bus_return_path_ok else "missing",
            ["authority_event", "siming.visual_observability_request", "siming_visual_observability_applied"]
            if siming_event_bus_return_path_ok
            else [],
        )
    )
```

Place it after `candidate_and_siming_observed` so the report keeps L1-to-L2 evidence grouped.

- [ ] **Step 5: Run trace and audit tests**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_runtime_trace.py backend/tests/test_verification_audit.py
```

Expected: pass.

---

### Task 6: Full Verification And OpenSpec Task Sync

**Files:**
- Modify: `openspec/changes/complete-siming-godot-event-bus-loop/tasks.md`
- Modify only if verification exposes a real gap.

- [ ] **Step 1: Run focused backend and static tests**

Run:

```powershell
python -m pytest -q backend/tests/test_frontend_authority_event_projection.py backend/tests/test_ws_authority_event_projection.py scripts/verification/tests/test_runtime_trace.py scripts/verification/tests/test_boundary_checks.py scripts/verification/tests/test_phase0_player_scene.py
```

Expected: all selected tests pass.

- [ ] **Step 2: Run full backend tests**

Run:

```powershell
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Run runtime harness profiles**

Run:

```powershell
python scripts/verification/harness.py --profile phase0
python scripts/verification/harness.py --profile phase1-slice
```

Expected:

```text
overall_strict_phase0_passed=True
overall_phase1_slice_passed=True
siming_event_bus_return_path=proved
```

- [ ] **Step 4: Sync OpenSpec task checkboxes**

After implementation and verification, update `openspec/changes/complete-siming-godot-event-bus-loop/tasks.md` to mark completed tasks with `[x]`.

- [ ] **Step 5: Commit implementation**

Use a Lore-style commit message:

```text
Prove Siming event bus reaches Godot presentation

The backend authority event bus already generated Siming event families, but
those outputs stopped inside the backend. This change projects the first
frontend-safe event family through the existing websocket envelope and proves
Godot consumes it as local presentation only.

Constraint: Preserve legacy Phase 0 siming_output and world_result paths until equivalent coverage exists
Rejected: Stream every authority event to Godot | leaks audit and orchestration internals
Confidence: high
Scope-risk: moderate
Directive: Do not claim full event-bus mainline completion until all selected Siming output families have downstream consumers
Tested: python -m pytest -q
Tested: python scripts/verification/harness.py --profile phase0
Tested: python scripts/verification/harness.py --profile phase1-slice
```

## Self-Review

- Spec coverage: backend projection, Godot bridge, local presentation, and harness proof are covered by Tasks 1 through 6.
- Placeholder scan: no implementation task uses unspecified placeholders; each code step includes concrete names and snippets.
- Type consistency: projected websocket messages use `message_type="authority_event"` and `payload.event_type="siming.visual_observability_request"` consistently across backend, Godot, and runtime trace steps.
- Scope check: this plan proves one downstream Siming event family and explicitly does not claim full event-bus mainline completion.
