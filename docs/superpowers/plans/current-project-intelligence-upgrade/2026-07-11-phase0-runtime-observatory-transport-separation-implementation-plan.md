# Phase 0 Runtime and Observatory Transport Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent observatory fanout from starving Phase 0 control traffic by adding a backward-compatible runtime-only websocket projection and exact ordered transport barriers.

**Architecture:** Keep the existing single-reader/single-writer websocket loop, but filter observatory-only messages per connection after runtime processing has completed. Strict Phase 0 selects `stream_mode=runtime_only`, sends exact correlated transport barriers at both drain points, and retains the 500 ms quiet check after each barrier ACK.

**Tech Stack:** Python 3.13, FastAPI/Starlette WebSocket, Pydantic, pytest, Godot 4.6 GDScript, repository Harness.

## Global Constraints

- Missing, empty, or unknown `stream_mode` preserves backward-compatible `full` behavior.
- `runtime_only` filters exactly these seven message types: `character_agent_debug_event`, `character_agent_debug_snapshot`, `siming_debug_event`, `siming_debug_snapshot`, `world_outcome_trace`, `scheduling_round_trace`, and `script_beat_event`.
- Every other existing or future message type remains on the main websocket by default.
- Filtering occurs after `_handle_envelope` and `_finalize_outbound_messages`; it must not suppress runtime side effects or debug-stream publication.
- Barrier IDs use exactly `transport_barrier:<producer_ts>:<sequence>`.
- A barrier ACK echoes exactly `accepted`, `source_type`, `route`, `request_id`, and `producer_ts`; both `source_type` and `route` are `transport_barrier`.
- A barrier has no authority, ESM, Siming, Heavenly Graph, character-memory, or world-truth side effects.
- Strict main Phase 0 uses `runtime_only`; normal interactive and focus-autotest connections remain `full`.
- Both Phase 0 drain points wait for an exact barrier ACK for at most `10000` ms, followed by a `500` ms quiet interval bounded by `10000` ms.
- Do not increase timeouts or modify websocket reader/writer concurrency, ESM settlement, Siming runtime, Heavenly Graph implementation, character memory, fact emitters, or authority ownership.
- Every code-editing task follows red-green-refactor, ends with focused tests, and gets a task-level commit and task-level review.

---

## File Structure

- `backend/app/transport_projection.py`: connection stream-mode normalization and outbound projection filtering only.
- `backend/app/models/transport.py`: validated transport-barrier payload only.
- `backend/app/main.py`: connection-mode selection, unknown-mode debug record, filtered send loop, and barrier ACK routing.
- `backend/tests/test_transport_projection.py`: pure projection contract tests.
- `backend/tests/test_ws_protocol.py`: websocket connection-mode compatibility and barrier ordering tests.
- `scripts/autoload/BackendBridge.gd`: connection-local barrier ID generation and send descriptor.
- `scripts/phase0/MainDemoController.gd`: strict-autotest URL selection and the two exact barrier/quiet drain points.
- `scripts/verification/tests/test_phase0_correlated_ack_contract.py`: Godot source contracts for URL, barrier generation, and sequencing.

---

### Task 1: Add Connection-Scoped Runtime Projection

**Files:**
- Create: `backend/app/transport_projection.py`
- Create: `backend/tests/test_transport_projection.py`
- Modify: `backend/app/main.py:1-8,212-228`
- Modify: `backend/tests/test_ws_protocol.py`

**Interfaces:**
- Consumes: finalized outbound `list[dict[str, object]]` from `_handle_envelope`.
- Produces: `StreamMode`, `normalize_stream_mode(raw_mode)`, `is_known_stream_mode(raw_mode)`, and `project_outbound_messages(messages, stream_mode=...)`.

- [ ] **Step 1: Write failing pure projection tests**

Create `backend/tests/test_transport_projection.py`:

```python
from app.transport_projection import (
    OBSERVATORY_ONLY_MESSAGE_TYPES,
    is_known_stream_mode,
    normalize_stream_mode,
    project_outbound_messages,
)


OBSERVATORY_TYPES = {
    "character_agent_debug_event",
    "character_agent_debug_snapshot",
    "siming_debug_event",
    "siming_debug_snapshot",
    "world_outcome_trace",
    "scheduling_round_trace",
    "script_beat_event",
}


def _message(message_type: str) -> dict[str, object]:
    return {"message_type": message_type, "payload": {"marker": message_type}}


def test_runtime_only_filters_exact_observatory_families() -> None:
    messages = [_message("ack"), *[_message(name) for name in sorted(OBSERVATORY_TYPES)], _message("future_type")]

    projected = project_outbound_messages(messages, stream_mode="runtime_only")

    assert OBSERVATORY_ONLY_MESSAGE_TYPES == frozenset(OBSERVATORY_TYPES)
    assert [message["message_type"] for message in projected] == ["ack", "future_type"]


def test_full_mode_preserves_order_and_all_message_types() -> None:
    messages = [_message("ack"), _message("character_agent_debug_event"), _message("world_result")]

    projected = project_outbound_messages(messages, stream_mode="full")

    assert projected == messages
    assert projected is not messages


def test_missing_empty_and_unknown_stream_modes_normalize_to_full() -> None:
    assert normalize_stream_mode(None) == "full"
    assert normalize_stream_mode("") == "full"
    assert normalize_stream_mode("full") == "full"
    assert normalize_stream_mode("runtime_only") == "runtime_only"
    assert normalize_stream_mode("typo") == "full"
    assert is_known_stream_mode(None) is True
    assert is_known_stream_mode("") is True
    assert is_known_stream_mode("full") is True
    assert is_known_stream_mode("runtime_only") is True
    assert is_known_stream_mode("typo") is False
```

- [ ] **Step 2: Run the pure tests and verify RED**

Run:

```powershell
python -m pytest backend/tests/test_transport_projection.py -v
```

Expected: collection error because `app.transport_projection` does not exist.

- [ ] **Step 3: Implement the projection module**

Create `backend/app/transport_projection.py`:

```python
from __future__ import annotations

from typing import Literal


StreamMode = Literal["full", "runtime_only"]

OBSERVATORY_ONLY_MESSAGE_TYPES = frozenset(
    {
        "character_agent_debug_event",
        "character_agent_debug_snapshot",
        "siming_debug_event",
        "siming_debug_snapshot",
        "world_outcome_trace",
        "scheduling_round_trace",
        "script_beat_event",
    }
)


def normalize_stream_mode(raw_mode: str | None) -> StreamMode:
    if raw_mode == "runtime_only":
        return "runtime_only"
    return "full"


def is_known_stream_mode(raw_mode: str | None) -> bool:
    return raw_mode in {None, "", "full", "runtime_only"}


def project_outbound_messages(
    messages: list[dict[str, object]],
    *,
    stream_mode: StreamMode,
) -> list[dict[str, object]]:
    if stream_mode == "full":
        return list(messages)
    return [
        message
        for message in messages
        if str(message.get("message_type", "") or "") not in OBSERVATORY_ONLY_MESSAGE_TYPES
    ]
```

- [ ] **Step 4: Run the pure tests and verify GREEN**

Run:

```powershell
python -m pytest backend/tests/test_transport_projection.py -v
```

Expected: `3 passed`.

- [ ] **Step 5: Write failing websocket projection tests**

Append to `backend/tests/test_ws_protocol.py`:

```python
def _stub_projection_messages() -> list[dict[str, object]]:
    return [
        {"message_type": "ack", "payload": {"accepted": True}},
        {"message_type": "character_agent_debug_event", "payload": {"stage": "debug"}},
        {"message_type": "world_result", "payload": {"result_type": "object_state_result"}},
    ]


def test_websocket_runtime_only_filters_observatory_projection(monkeypatch) -> None:
    main.debug_stream.clear()

    def handle_with_debug_projection(_envelope) -> list[dict[str, object]]:
        messages = _stub_projection_messages()
        main._emit_debug_from_messages(messages)
        return messages

    monkeypatch.setattr(main, "_handle_envelope", handle_with_debug_projection)
    client = TestClient(app)
    with client.websocket_connect("/ws?stream_mode=runtime_only") as websocket:
        websocket.send_json({"message_type": "projection_probe", "payload": {}})
        first = websocket.receive_json()
        second = websocket.receive_json()

    assert [first["message_type"], second["message_type"]] == ["ack", "world_result"]
    assert any(
        event.get("stage") == "debug"
        and event.get("detail", {}).get("stage") == "debug"
        for event in main.debug_stream.history()
    )


def test_websocket_missing_mode_preserves_full_projection(monkeypatch) -> None:
    monkeypatch.setattr(main, "_handle_envelope", lambda _envelope: _stub_projection_messages())
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json({"message_type": "projection_probe", "payload": {}})
        messages = [websocket.receive_json() for _ in range(3)]

    assert [message["message_type"] for message in messages] == [
        "ack",
        "character_agent_debug_event",
        "world_result",
    ]


def test_websocket_unknown_mode_preserves_full_projection_and_records_debug(monkeypatch) -> None:
    main.debug_stream.clear()
    monkeypatch.setattr(main, "_handle_envelope", lambda _envelope: _stub_projection_messages())
    client = TestClient(app)
    with client.websocket_connect("/ws?stream_mode=typo") as websocket:
        websocket.send_json({"message_type": "projection_probe", "payload": {}})
        messages = [websocket.receive_json() for _ in range(3)]

    assert [message["message_type"] for message in messages] == [
        "ack",
        "character_agent_debug_event",
        "world_result",
    ]
    assert any(
        event.get("stage") == "unknown_stream_mode"
        and event.get("detail", {}).get("raw_stream_mode") == "typo"
        for event in main.debug_stream.history()
    )
```

- [ ] **Step 6: Run the websocket projection tests and verify RED**

Run:

```powershell
python -m pytest backend/tests/test_ws_protocol.py::test_websocket_runtime_only_filters_observatory_projection backend/tests/test_ws_protocol.py::test_websocket_missing_mode_preserves_full_projection backend/tests/test_ws_protocol.py::test_websocket_unknown_mode_preserves_full_projection_and_records_debug -v
```

Expected: the runtime-only test receives the unfiltered debug message, and the unknown-mode test has no `unknown_stream_mode` debug event.

- [ ] **Step 7: Wire stream mode into the websocket endpoint**

Add this import to `backend/app/main.py`:

```python
from app.transport_projection import (
    is_known_stream_mode,
    normalize_stream_mode,
    project_outbound_messages,
)
```

Replace `websocket_endpoint` with:

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    raw_stream_mode = websocket.query_params.get("stream_mode")
    stream_mode = normalize_stream_mode(raw_stream_mode)
    if not is_known_stream_mode(raw_stream_mode):
        _publish_debug_event(
            build_debug_event(
                producer_ts=0,
                domain="transport",
                stage="unknown_stream_mode",
                actor_id=None,
                summary=f"unknown stream mode {raw_stream_mode!r}; using full",
                detail={"raw_stream_mode": raw_stream_mode, "resolved_stream_mode": stream_mode},
            )
        )
    try:
        while True:
            try:
                raw = await websocket.receive_json()
                envelope = Envelope(**raw)
                outbound = _handle_envelope(envelope)
            except (ValidationError, ValueError, TypeError) as exc:
                source_type = "unknown"
                if isinstance(raw, dict):
                    source_type = str(raw.get("message_type", "unknown"))
                outbound = [_as_error_ack(source_type=source_type, route="invalid_payload", error=exc)]
            projected = project_outbound_messages(outbound, stream_mode=stream_mode)
            for message in projected:
                await websocket.send_json(message)
    except WebSocketDisconnect:
        return
```

- [ ] **Step 8: Run focused and neighboring websocket tests**

Run:

```powershell
python -m pytest backend/tests/test_transport_projection.py backend/tests/test_ws_protocol.py -v
```

Expected: all tests pass; existing `/ws` tests confirm default `full` compatibility.

- [ ] **Step 9: Commit Task 1**

```powershell
git add backend/app/transport_projection.py backend/app/main.py backend/tests/test_transport_projection.py backend/tests/test_ws_protocol.py
git commit -m "feat: separate runtime websocket projection"
```

---

### Task 2: Add a Correlated No-Side-Effect Transport Barrier

**Files:**
- Create: `backend/app/models/transport.py`
- Modify: `backend/app/main.py:20-35,261-270`
- Modify: `backend/tests/test_ws_protocol.py`

**Interfaces:**
- Consumes: `Envelope(message_type="transport_barrier", payload=...)`.
- Produces: `TransportBarrier(request_id: str, producer_ts: int)` and one exact barrier ACK.

- [ ] **Step 1: Write failing model, side-effect, ordering, and invalid-payload tests**

Add this import to `backend/tests/test_ws_protocol.py`:

```python
from app.models.transport import TransportBarrier
```

Append:

```python
def test_transport_barrier_requires_nonempty_request_identity() -> None:
    barrier = TransportBarrier(request_id="transport_barrier:500:1", producer_ts=500)

    assert barrier.request_id == "transport_barrier:500:1"
    assert barrier.producer_ts == 500


def test_transport_barrier_ack_has_no_runtime_side_effects() -> None:
    _reset_runtime_state_with_local_character_model()
    before = main.event_trace.summary()

    messages = main._handle_envelope(
        Envelope(
            message_type="transport_barrier",
            payload={"request_id": "transport_barrier:501:2", "producer_ts": 501},
        )
    )

    assert messages == [
        {
            "message_type": "ack",
            "payload": {
                "accepted": True,
                "source_type": "transport_barrier",
                "route": "transport_barrier",
                "request_id": "transport_barrier:501:2",
                "producer_ts": 501,
            },
        }
    ]
    assert main.event_trace.summary() == before


def test_websocket_transport_barrier_ack_follows_prior_request_responses() -> None:
    _reset_runtime_state_with_local_character_model()
    client = TestClient(app)
    with client.websocket_connect("/ws?stream_mode=runtime_only") as websocket:
        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": {
                    "player_id": "p1",
                    "room_id": "room_demo",
                    "scene_id": "scene_demo",
                    "zone_id": "zone_focus",
                    "actor_id": "char_c",
                    "intent_type": "move_intent",
                    "producer_ts": 502,
                    "request_id": "player_input:char_c:move_intent:502:1",
                    "move_mode": "locomotion",
                    "target_point": [1.0, 0.5, 2.0],
                },
            }
        )
        websocket.send_json(
            {
                "message_type": "transport_barrier",
                "payload": {"request_id": "transport_barrier:503:2", "producer_ts": 503},
            }
        )

        move_ack = websocket.receive_json()
        runtime_snapshot = websocket.receive_json()
        barrier_ack = websocket.receive_json()

    assert move_ack["payload"]["request_id"] == "player_input:char_c:move_intent:502:1"
    assert runtime_snapshot["message_type"] == "character_runtime_state_snapshot"
    assert barrier_ack == {
        "message_type": "ack",
        "payload": {
            "accepted": True,
            "source_type": "transport_barrier",
            "route": "transport_barrier",
            "request_id": "transport_barrier:503:2",
            "producer_ts": 503,
        },
    }


def test_websocket_invalid_transport_barrier_returns_negative_ack_and_stays_open() -> None:
    client = TestClient(app)
    with client.websocket_connect("/ws?stream_mode=runtime_only") as websocket:
        websocket.send_json(
            {
                "message_type": "transport_barrier",
                "payload": {"request_id": "", "producer_ts": 504},
            }
        )
        error_ack = websocket.receive_json()
        websocket.send_json(
            {
                "message_type": "transport_barrier",
                "payload": {"request_id": "transport_barrier:505:3", "producer_ts": 505},
            }
        )
        success_ack = websocket.receive_json()

    assert error_ack["message_type"] == "ack"
    assert error_ack["payload"]["accepted"] is False
    assert error_ack["payload"]["source_type"] == "transport_barrier"
    assert error_ack["payload"]["route"] == "invalid_payload"
    assert error_ack["payload"]["error_type"] == "ValidationError"
    assert success_ack["payload"]["request_id"] == "transport_barrier:505:3"
```

- [ ] **Step 2: Run the barrier tests and verify RED**

Run:

```powershell
python -m pytest backend/tests/test_ws_protocol.py::test_transport_barrier_requires_nonempty_request_identity backend/tests/test_ws_protocol.py::test_transport_barrier_ack_has_no_runtime_side_effects backend/tests/test_ws_protocol.py::test_websocket_transport_barrier_ack_follows_prior_request_responses backend/tests/test_ws_protocol.py::test_websocket_invalid_transport_barrier_returns_negative_ack_and_stays_open -v
```

Expected: collection error because `app.models.transport` does not exist.

- [ ] **Step 3: Add the validated barrier model**

Create `backend/app/models/transport.py`:

```python
from pydantic import BaseModel, Field


class TransportBarrier(BaseModel):
    request_id: str = Field(min_length=1)
    producer_ts: int
```

- [ ] **Step 4: Add barrier handling before domain routes**

Add this import to `backend/app/main.py`:

```python
from app.models.transport import TransportBarrier
```

Insert at the start of `_handle_envelope`:

```python
def _handle_envelope(envelope: Envelope) -> list[dict[str, object]]:
    if envelope.message_type == "transport_barrier":
        barrier = TransportBarrier(**envelope.payload)
        return [
            {
                "message_type": "ack",
                "payload": {
                    "accepted": True,
                    "source_type": "transport_barrier",
                    "route": "transport_barrier",
                    "request_id": barrier.request_id,
                    "producer_ts": barrier.producer_ts,
                },
            }
        ]

    # Existing visual_fact_event branch follows unchanged.
```

Do not call `_finalize_outbound_messages`, `event_trace.record`, an authority publisher, Siming, or character runtime from this branch.

- [ ] **Step 5: Run focused and neighboring protocol tests**

Run:

```powershell
python -m pytest backend/tests/test_transport_projection.py backend/tests/test_ws_protocol.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 2**

```powershell
git add backend/app/models/transport.py backend/app/main.py backend/tests/test_ws_protocol.py
git commit -m "feat: add ordered websocket transport barrier"
```

---

### Task 3: Select Runtime-Only Mode and Generate Godot Barriers

**Files:**
- Modify: `scripts/autoload/BackendBridge.gd:3-42`
- Modify: `scripts/phase0/MainDemoController.gd:95-125,243-253`
- Modify: `scripts/verification/tests/test_phase0_correlated_ack_contract.py`

**Interfaces:**
- Consumes: backend `stream_mode=runtime_only` and `transport_barrier` contracts from Tasks 1-2.
- Produces: `BackendBridge.send_transport_barrier() -> Dictionary` and `MainDemoController._resolve_backend_url() -> String`.

- [ ] **Step 1: Write failing Godot source-contract tests**

Append to `scripts/verification/tests/test_phase0_correlated_ack_contract.py`:

```python
def test_backend_bridge_generates_connection_local_transport_barriers() -> None:
    source = (SCRIPTS_ROOT / "autoload" / "BackendBridge.gd").read_text(encoding="utf-8")
    connect_section = source.split("func connect_to_backend(url: String) -> int:", 1)[1].split(
        "func send_envelope", 1
    )[0]
    barrier_section = source.split("func send_transport_barrier() -> Dictionary:", 1)[1].split(
        "func close_backend_connection", 1
    )[0]

    assert "var transport_barrier_sequence := 0" in source
    assert "transport_barrier_sequence = 0" in connect_section
    assert "transport_barrier_sequence += 1" in barrier_section
    assert '"transport_barrier:%s:%s"' in barrier_section
    assert "[producer_ts, transport_barrier_sequence]" in barrier_section
    assert '"message_type": "transport_barrier"' in barrier_section
    assert '"request_id": request_id' in barrier_section
    assert '"producer_ts": producer_ts' in barrier_section
    assert "return {}" in barrier_section
    assert 'return {"request_id": request_id, "producer_ts": producer_ts}' in barrier_section


def test_strict_phase0_selects_runtime_only_without_changing_normal_or_focus_urls() -> None:
    source = (SCRIPTS_ROOT / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    connect_section = source.split("func _connect_backend() -> void:", 1)[1].split(
        "func submit_dialogue", 1
    )[0]
    resolver_section = source.split("func _resolve_backend_url() -> String:", 1)[1].split(
        "func submit_dialogue", 1
    )[0]

    assert "var connection_url := _resolve_backend_url()" in connect_section
    assert "bridge.connect_to_backend(connection_url)" in connect_section
    assert "if not autotest_enabled or focus_autotest_enabled:" in resolver_section
    assert "return backend_url" in resolver_section
    assert 'var separator: String = "&" if backend_url.contains("?") else "?"' in resolver_section
    assert 'return "%s%sstream_mode=runtime_only" % [backend_url, separator]' in resolver_section
```

- [ ] **Step 2: Run the Godot source-contract tests and verify RED**

Run:

```powershell
python -m pytest scripts/verification/tests/test_phase0_correlated_ack_contract.py::test_backend_bridge_generates_connection_local_transport_barriers scripts/verification/tests/test_phase0_correlated_ack_contract.py::test_strict_phase0_selects_runtime_only_without_changing_normal_or_focus_urls -v
```

Expected: two failures because the methods and barrier state do not exist.

- [ ] **Step 3: Add connection-local barrier generation to BackendBridge**

Add this state after `last_requested_url` in `scripts/autoload/BackendBridge.gd`:

```gdscript
var transport_barrier_sequence := 0
```

Reset it at the beginning of `connect_to_backend`:

```gdscript
func connect_to_backend(url: String) -> int:
    last_requested_url = url
    transport_barrier_sequence = 0
```

Add after `send_envelope`:

```gdscript
func send_transport_barrier() -> Dictionary:
    if ws.get_ready_state() != WebSocketPeer.STATE_OPEN:
        return {}
    transport_barrier_sequence += 1
    var producer_ts: int = Time.get_ticks_msec()
    var request_id: String = "transport_barrier:%s:%s" % [producer_ts, transport_barrier_sequence]
    var err: int = send_envelope(
        {
            "message_type": "transport_barrier",
            "payload": {
                "request_id": request_id,
                "producer_ts": producer_ts,
            },
        }
    )
    if err != OK:
        return {}
    return {"request_id": request_id, "producer_ts": producer_ts}
```

- [ ] **Step 4: Resolve the strict-autotest websocket URL**

Change `_connect_backend` in `scripts/phase0/MainDemoController.gd` to:

```gdscript
func _connect_backend() -> void:
    await get_tree().process_frame
    await get_tree().process_frame
    var bridge := _get_bridge()
    if bridge == null:
        _bus_log("phase0_backend_bridge_missing")
        return
    var connection_url := _resolve_backend_url()
    var err: int = bridge.connect_to_backend(connection_url)
    _bus_log("phase0_backend_connect_err:%s" % err)

func _resolve_backend_url() -> String:
    if not autotest_enabled or focus_autotest_enabled:
        return backend_url
    var separator: String = "&" if backend_url.contains("?") else "?"
    return "%s%sstream_mode=runtime_only" % [backend_url, separator]
```

- [ ] **Step 5: Run Godot contracts and marker-aware parsing**

Run:

```powershell
python -m pytest scripts/verification/tests/test_phase0_correlated_ack_contract.py -v
python scripts/verification/harness.py --profile godot-project
```

Run the marker-aware direct import and fail on either a non-zero exit or a parse/load marker:

```powershell
$godotOutput = (& 'D:\godot\Godot_v4.6.3-stable_win64_console.exe' --headless --path . --import --quit --verbose --render-thread safe 2>&1 | Out-String)
$godotExitCode = $LASTEXITCODE
$godotOutput
if ($godotExitCode -ne 0) {
    throw "Godot import exited with code $godotExitCode"
}
$parseMarkers = $godotOutput | Select-String -Pattern 'SCRIPT ERROR|Parse Error|Failed to load script'
if ($parseMarkers) {
    $parseMarkers
    throw 'Godot import emitted parse/load markers'
}
Write-Output 'godot_parse_markers=none'
```

Expected: all source contracts pass, `overall_godot_project_passed=True`, and none of the three parse markers appears.

- [ ] **Step 6: Commit Task 3**

```powershell
git add scripts/autoload/BackendBridge.gd scripts/phase0/MainDemoController.gd scripts/verification/tests/test_phase0_correlated_ack_contract.py
git commit -m "feat: select bounded phase0 runtime transport"
```

---

### Task 4: Gate Both Phase 0 Drains With Exact Barrier ACKs

**Files:**
- Modify: `scripts/phase0/MainDemoController.gd:392-505`
- Modify: `scripts/verification/tests/test_phase0_correlated_ack_contract.py`

**Interfaces:**
- Consumes: `BackendBridge.send_transport_barrier() -> Dictionary` and existing `_wait_for_request_ack`/`_wait_for_backend_quiet`.
- Produces: `_emit_transport_barrier_request() -> Dictionary` and `_drain_backend_transport(barrier_failure_stage: String) -> bool`.

- [ ] **Step 1: Replace the old drain source contract with failing barrier contracts**

Replace `test_main_demo_drains_periodic_sampling_before_near_move` in `scripts/verification/tests/test_phase0_correlated_ack_contract.py` with:

```python
def test_main_demo_uses_exact_barriers_before_near_and_far_moves() -> None:
    source = (SCRIPTS_ROOT / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    run_section = source.split("func _run_autotest_inputs() -> void:", 1)[1].split(
        "func _set_autotest_actor_local_perception_enabled", 1
    )[0]

    focus_index = run_section.index("_force_focus_target(interactive_object)")
    pre_barrier_index = run_section.index(
        'await _drain_backend_transport("pre_interaction_barrier_ack_timeout")'
    )
    near_move_index = run_section.index(
        'var near_move_request := _emit_move_intent_request(autotest_interact_position, "locomotion")'
    )
    success_wait_index = run_section.index(
        "await _wait_for_successful_interaction_result(autotest_request_timeout_ms)"
    )
    quiescence_index = run_section.index("autotest_transport_quiescent = true")
    post_barrier_index = run_section.index(
        'await _drain_backend_transport("post_success_barrier_ack_timeout")'
    )
    far_move_index = run_section.index(
        'var far_move_request := _emit_move_intent_request(autotest_failed_interact_position, "locomotion")'
    )

    assert focus_index < pre_barrier_index < near_move_index
    assert near_move_index < success_wait_index < quiescence_index < post_barrier_index < far_move_index
    assert "return" in run_section[pre_barrier_index:near_move_index]
    assert "return" in run_section[post_barrier_index:far_move_index]
    assert "await _wait_for_backend_quiet" not in run_section


def test_main_demo_transport_drain_waits_for_exact_ack_then_quiet_window() -> None:
    source = (SCRIPTS_ROOT / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    emit_section = source.split("func _emit_transport_barrier_request() -> Dictionary:", 1)[1].split(
        "func _drain_backend_transport", 1
    )[0]
    drain_section = source.split(
        "func _drain_backend_transport(barrier_failure_stage: String) -> bool:", 1
    )[1].split("func _wait_for_request_ack", 1)[0]

    assert 'bridge.has_method("send_transport_barrier")' in emit_section
    assert "return bridge.send_transport_barrier()" in emit_section
    assert "var barrier_request := _emit_transport_barrier_request()" in drain_section
    assert (
        'await _wait_for_request_ack(str(barrier_request.get("request_id", "")), autotest_request_timeout_ms)'
        in drain_section
    )
    assert 'await _fail_autotest(barrier_failure_stage, barrier_request)' in drain_section
    assert "last_backend_activity_ms = Time.get_ticks_msec()" in drain_section
    assert (
        "await _wait_for_backend_quiet(autotest_transport_quiet_window_ms, autotest_transport_quiet_timeout_ms)"
        in drain_section
    )
    assert 'await _fail_autotest("transport_not_quiet", barrier_request)' in drain_section
```

- [ ] **Step 2: Run the two barrier-flow tests and verify RED**

Run:

```powershell
python -m pytest scripts/verification/tests/test_phase0_correlated_ack_contract.py::test_main_demo_uses_exact_barriers_before_near_and_far_moves scripts/verification/tests/test_phase0_correlated_ack_contract.py::test_main_demo_transport_drain_waits_for_exact_ack_then_quiet_window -v
```

Expected: failures because `_drain_backend_transport` and `_emit_transport_barrier_request` do not exist.

- [ ] **Step 3: Add the transport-drain helpers**

Add immediately after `_set_autotest_actor_local_perception_enabled`:

```gdscript
func _emit_transport_barrier_request() -> Dictionary:
    var bridge := _get_bridge()
    if bridge == null or not bridge.has_method("send_transport_barrier"):
        return {}
    return bridge.send_transport_barrier()

func _drain_backend_transport(barrier_failure_stage: String) -> bool:
    var barrier_request := _emit_transport_barrier_request()
    if not (await _wait_for_request_ack(str(barrier_request.get("request_id", "")), autotest_request_timeout_ms)):
        await _fail_autotest(barrier_failure_stage, barrier_request)
        return false
    last_backend_activity_ms = Time.get_ticks_msec()
    if not (await _wait_for_backend_quiet(autotest_transport_quiet_window_ms, autotest_transport_quiet_timeout_ms)):
        await _fail_autotest("transport_not_quiet", barrier_request)
        return false
    return true
```

- [ ] **Step 4: Replace both direct quiet waits in the autotest**

Replace the pre-interaction block:

```gdscript
    last_backend_activity_ms = Time.get_ticks_msec()
    if not (await _wait_for_backend_quiet(autotest_transport_quiet_window_ms, autotest_transport_quiet_timeout_ms)):
        await _fail_autotest("transport_not_quiet", {})
        return
```

with:

```gdscript
    if not (await _drain_backend_transport("pre_interaction_barrier_ack_timeout")):
        return
```

Replace the post-success block after `autotest_transport_quiescent = true` and the sampling flags with:

```gdscript
    if not (await _drain_backend_transport("post_success_barrier_ack_timeout")):
        return
```

Do not change the near move, successful interaction, far move, failed interaction, or world-result correlation code.

- [ ] **Step 5: Run the full correlated-flow contracts and Godot parsing**

Run:

```powershell
python -m pytest scripts/verification/tests/test_phase0_correlated_ack_contract.py backend/tests/test_verification_audit.py -v
python scripts/verification/harness.py --profile godot-project
```

Run the marker-aware direct import and fail on either a non-zero exit or a parse/load marker:

```powershell
$godotOutput = (& 'D:\godot\Godot_v4.6.3-stable_win64_console.exe' --headless --path . --import --quit --verbose --render-thread safe 2>&1 | Out-String)
$godotExitCode = $LASTEXITCODE
$godotOutput
if ($godotExitCode -ne 0) {
    throw "Godot import exited with code $godotExitCode"
}
$parseMarkers = $godotOutput | Select-String -Pattern 'SCRIPT ERROR|Parse Error|Failed to load script'
if ($parseMarkers) {
    $parseMarkers
    throw 'Godot import emitted parse/load markers'
}
Write-Output 'godot_parse_markers=none'
```

Expected: all tests pass, `overall_godot_project_passed=True`, and no `SCRIPT ERROR`, `Parse Error`, or `Failed to load script` marker appears.

- [ ] **Step 6: Commit Task 4**

```powershell
git add scripts/phase0/MainDemoController.gd scripts/verification/tests/test_phase0_correlated_ack_contract.py
git commit -m "fix: fence phase0 transport before interaction proofs"
```

---

### Task 5: Run the Completion Verification and Review Ladder

**Files:**
- No planned tracked implementation edits.
- Update ignored execution records under `.superpowers/sdd/` with fresh evidence.
- Generated Harness evidence remains under `.harness/verification/`.

**Interfaces:**
- Consumes: Tasks 1-4 plus the existing correlated ACK and Heavenly Graph Foundation commits.
- Produces: fresh whole-branch evidence and a final review package from `facec59` to `HEAD`.

- [ ] **Step 1: Check patch hygiene and tracked scope**

Run:

```powershell
git diff --check facec59..HEAD
git status --short
git diff --name-only facec59..HEAD
```

Expected: no whitespace errors, a clean tracked worktree, and no new ESM, Siming runtime, Heavenly Graph implementation, character-memory, fact-emitter, or authority-ownership file from this supplemental repair.

- [ ] **Step 2: Run transport and correlated-ACK focused tests**

Run:

```powershell
python -m pytest backend/tests/test_transport_projection.py backend/tests/test_ws_protocol.py scripts/verification/tests/test_phase0_correlated_ack_contract.py backend/tests/test_verification_audit.py -v
```

Expected: all tests pass.

- [ ] **Step 3: Run neighboring Godot bridge and observatory contracts**

Run:

```powershell
python -m pytest backend/tests/test_character_actor_bridge_static.py backend/tests/test_observatory_message_delivery_static.py backend/tests/test_character_actor_reacquisition_runtime.py backend/tests/test_character_controller_boundary_static.py backend/tests/test_focus_visualization_static.py backend/tests/test_phase0_player_command_relay_static.py -v
```

Expected: all tests pass; normal full-stream observatory signal chains remain intact.

- [ ] **Step 4: Re-run Heavenly Graph focused tests**

Run:

```powershell
python -m pytest backend/tests/test_siming_heavenly_graph_models.py backend/tests/test_siming_heavenly_graph_contract.py -v
```

Expected: `27 passed`.

- [ ] **Step 5: Run the full pytest suite**

Run:

```powershell
python -m pytest -v
```

Expected: zero failures; existing Pydantic and Starlette warnings may remain.

- [ ] **Step 6: Run marker-aware Godot verification**

Run:

```powershell
python scripts/verification/harness.py --profile godot-project
```

Also run the marker-aware direct import:

```powershell
$godotOutput = (& 'D:\godot\Godot_v4.6.3-stable_win64_console.exe' --headless --path . --import --quit --verbose --render-thread safe 2>&1 | Out-String)
$godotExitCode = $LASTEXITCODE
$godotOutput
if ($godotExitCode -ne 0) {
    throw "Godot import exited with code $godotExitCode"
}
$parseMarkers = $godotOutput | Select-String -Pattern 'SCRIPT ERROR|Parse Error|Failed to load script'
if ($parseMarkers) {
    $parseMarkers
    throw 'Godot import emitted parse/load markers'
}
Write-Output 'godot_parse_markers=none'
```

- [ ] **Step 7: Run strict Phase 0**

Run exactly once after all preceding gates are green:

```powershell
python scripts/verification/harness.py --profile phase0
```

Expected:

```text
overall_strict_phase0_passed=True
```

The persisted report must show:

- `successful_interaction=proved`;
- `visible_world_state_change=proved`;
- `failed_interaction=proved` from a real correlated `constraint_state_result`;
- no `phase0_autotest_failure:` marker;
- both exact barrier ACKs occur before their corresponding near/far move stages.

- [ ] **Step 8: Run the dedicated Heavenly Graph profile**

Run:

```powershell
python scripts/verification/harness.py --profile siming-heavenly-graph-foundation
```

Expected: `overall_siming_heavenly_graph_foundation_passed=True`.

- [ ] **Step 9: Run broad repository verification**

Only after strict Phase 0 is green, run:

```powershell
python scripts/verification/harness.py --profile all
```

Expected: `overall_harness_passed=True`.

- [ ] **Step 10: Update durable ignored execution records**

Record exact commands, exit codes, pytest counts, marker-aware Godot result, Phase 0 run ID, Heavenly Graph run ID, broad Harness run ID, and final scope in:

```text
.superpowers/sdd/phase0-transport-separation-task-5-report.md
.superpowers/sdd/heavenly-task-7-report.md
.superpowers/sdd/progress.md
```

Mark original Task 7, correlated-ACK Task 4, and this Task 5 complete only when broad `all` exits `0`.

- [ ] **Step 11: Request whole-branch review**

Use `superpowers:requesting-code-review` with:

```text
base: facec59
head: current HEAD
designs:
  docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-11-phase0-correlated-ack-and-backpressure-design.md
  docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-11-phase0-runtime-observatory-transport-separation-design.md
plans:
  docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-11-phase0-correlated-ack-and-backpressure-implementation-plan.md
  docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-11-phase0-runtime-observatory-transport-separation-implementation-plan.md
minor note:
  failed validation does not directly retry reuse of the same Heavenly Graph idempotency key
verification report:
  .superpowers/sdd/phase0-transport-separation-task-5-report.md
```

Generate and pass a full review package for `facec59..HEAD`. Fix every Critical or Important finding with focused tests and re-review before proceeding.

- [ ] **Step 12: Finish the branch**

Use `superpowers:finishing-a-development-branch` only after:

- full pytest is green;
- strict Phase 0 is green;
- dedicated Heavenly Graph Harness is green;
- broad `all` Harness is green;
- final review has no open Critical or Important findings.

---

## Self-Review Notes

**Spec coverage:** Tasks 1-4 cover exact stream modes, the seven-message filter, unknown-mode compatibility, debug-stream preservation, barrier validation and ordering, Godot runtime-only selection, connection-local barrier IDs, both barrier/quiet drain points, and failure stages. Task 5 covers every required verification and review gate.

**Scope:** The plan changes transport projection and Phase 0 synchronization only. It does not change websocket concurrency, ESM, Siming runtime, Heavenly Graph implementation, character memory, fact emitters, or authority ownership.

**Type consistency:** `StreamMode`, `TransportBarrier`, `request_id`, `producer_ts`, `send_transport_barrier`, `_resolve_backend_url`, `_emit_transport_barrier_request`, and `_drain_backend_transport` use the same names and shapes across backend, Godot, and tests.

**Failure consistency:** `pre_interaction_barrier_ack_timeout`, `post_success_barrier_ack_timeout`, and `transport_not_quiet` all flow through `_fail_autotest(stage, barrier_request)` and therefore retain the exact request ID when one was generated.
