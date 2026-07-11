# Phase 0 Correlated ACK and Backpressure Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Phase 0 failed-interaction proof deterministic by correlating player-input ACKs, pausing new autotest fact traffic, and waiting for the exact constraint result before reporting success.

**Architecture:** Add an optional `request_id` to the shared player-input model and have Godot populate a collision-safe value for every input. The backend echoes request identity in ACKs, while `MainDemoController` replaces route-only flags with request-ID and world-result-correlation tracking plus a bounded application-level quiet window. ESM settlement, websocket ordering, Siming, Heavenly Graph, and character memory remain unchanged.

**Tech Stack:** Python 3.13, FastAPI websocket handling, Pydantic, pytest, Godot 4.6 GDScript, repository Harness.

## Global Constraints

- Preserve compatibility: `PlayerInputBase.request_id` defaults to `""`.
- Godot request IDs use exactly `player_input:<actor_id>:<intent_type>:<producer_ts>:<sequence>`.
- Backend player-input ACKs echo exactly `request_id`, `intent_type`, and `producer_ts` in addition to existing fields.
- The Phase 0 autotest must never synchronize by route-only ACK flags.
- Interaction constraint matching uses the existing `interact:<producer_ts>` correlation ID; do not change ESM.
- Quiet-window duration is `500` ms and every bounded wait has a `10000` ms maximum.
- Timeout paths log `phase0_autotest_failure:<stage>:<request_id>` and never log `phase0_autotest_stage:failed_interaction_resolved` or `phase0_autotest_complete`.
- Do not modify websocket reader/writer architecture, Siming runtime, Heavenly Graph files, character memory, ESM settlement rules, or authority ownership.
- Every code-editing task follows red-green-refactor, ends with focused tests, and gets a task-level commit.

---

## File Structure

- `backend/app/models/player_input.py`: backward-compatible player-input request identity.
- `backend/app/main.py`: ACK identity echo for successfully parsed player inputs.
- `backend/tests/test_ws_protocol.py`: model compatibility and websocket ACK contract tests.
- `scripts/player/PlayerIntentMapper.gd`: collision-safe request-ID generation with one captured timestamp per input.
- `scripts/phase0/MainDemoController.gd`: exact-request ACK tracking, world-result correlation, quiescence, quiet-window waiting, and explicit failure shutdown.
- `scripts/verification/tests/test_phase0_correlated_ack_contract.py`: static Godot contract tests for mapper and controller synchronization behavior.
- `backend/tests/test_verification_audit.py`: replace the old route-only source contract with the correlated final-stage contract.

---

### Task 1: Add Backward-Compatible Player-Input ACK Correlation

**Files:**
- Modify: `backend/app/models/player_input.py:4-11`
- Modify: `backend/app/main.py:628-638`
- Modify: `backend/tests/test_ws_protocol.py:69-80,451-482`

**Interfaces:**
- Consumes: existing `PlayerInputBase`, `_parse_player_input`, and `_handle_envelope` player-input route.
- Produces: `PlayerInputBase.request_id: str`; successful ACK payload fields `request_id`, `intent_type`, and `producer_ts`.

- [ ] **Step 1: Write failing model and websocket ACK tests**

Update `test_player_input_dialogue_submit_shape` so it proves both compatibility and explicit identity preservation:

```python
def test_player_input_dialogue_submit_shape() -> None:
    legacy_event = DialogueSubmit(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="dialogue_submit",
        producer_ts=123,
        target_actor_id="char_a",
        content="Hello",
    )
    correlated_event = DialogueSubmit(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="dialogue_submit",
        producer_ts=124,
        request_id="player_input:char_c:dialogue_submit:124:1",
        target_actor_id="char_a",
        content="Hello again",
    )

    assert legacy_event.request_id == ""
    assert legacy_event.target_actor_id == "char_a"
    assert legacy_event.content == "Hello"
    assert correlated_event.request_id == "player_input:char_c:dialogue_submit:124:1"
```

Update `test_websocket_move_intent_emits_ack_and_runtime_snapshot` by adding this field to the sent payload:

```python
"request_id": "player_input:char_c:move_intent:333:7",
```

Add these ACK assertions:

```python
assert ack["payload"]["request_id"] == "player_input:char_c:move_intent:333:7"
assert ack["payload"]["intent_type"] == "move_intent"
assert ack["payload"]["producer_ts"] == 333
```

Add a legacy compatibility test immediately after the correlated move test:

```python
def test_websocket_legacy_move_intent_echoes_empty_request_id() -> None:
    _reset_runtime_state_with_local_character_model()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
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
                    "producer_ts": 334,
                    "move_mode": "locomotion",
                    "target_point": [1.0, 0.5, 2.0],
                },
            }
        )

        ack = websocket.receive_json()
        runtime_snapshot = websocket.receive_json()

    assert ack["message_type"] == "ack"
    assert ack["payload"]["accepted"] is True
    assert ack["payload"]["route"] == "local_motion"
    assert ack["payload"]["request_id"] == ""
    assert ack["payload"]["intent_type"] == "move_intent"
    assert ack["payload"]["producer_ts"] == 334
    assert runtime_snapshot["message_type"] == "character_runtime_state_snapshot"
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
python -m pytest backend/tests/test_ws_protocol.py::test_player_input_dialogue_submit_shape backend/tests/test_ws_protocol.py::test_websocket_move_intent_emits_ack_and_runtime_snapshot backend/tests/test_ws_protocol.py::test_websocket_legacy_move_intent_echoes_empty_request_id -v
```

Expected: failures because `DialogueSubmit` has no `request_id` attribute and successful ACKs do not contain the three correlation fields.

- [ ] **Step 3: Add the optional player-input request identity**

Change `PlayerInputBase` to:

```python
class PlayerInputBase(BaseModel):
    player_id: str
    room_id: str
    scene_id: str = "scene_demo"
    zone_id: str = "zone_focus"
    actor_id: str
    intent_type: str
    producer_ts: int
    request_id: str = ""
```

- [ ] **Step 4: Echo correlation fields in valid player-input ACKs**

Replace the successful player-input ACK construction in `_handle_envelope` with:

```python
    messages: list[dict[str, object]] = [
        {
            "message_type": "ack",
            "payload": {
                "accepted": route["accepted"],
                "source_type": envelope.message_type,
                "route": route["route"],
                "request_id": event.request_id,
                "intent_type": event.intent_type,
                "producer_ts": event.producer_ts,
            },
        }
    ]
```

Do not change `_as_error_ack`; invalid payloads still lack a parsed request identity.

- [ ] **Step 5: Run focused and neighboring websocket tests and verify GREEN**

Run:

```powershell
python -m pytest backend/tests/test_ws_protocol.py::test_player_input_dialogue_submit_shape backend/tests/test_ws_protocol.py::test_websocket_move_intent_emits_ack_and_runtime_snapshot backend/tests/test_ws_protocol.py::test_websocket_legacy_move_intent_echoes_empty_request_id backend/tests/test_ws_protocol.py::test_websocket_dialogue_submit_emits_ack_and_dialogue_response backend/tests/test_ws_protocol.py::test_websocket_invalid_player_input_returns_negative_ack_without_dropping_connection -v
```

Expected: `5 passed`.

- [ ] **Step 6: Commit Task 1**

```powershell
git add backend/app/models/player_input.py backend/app/main.py backend/tests/test_ws_protocol.py
git commit -m "fix: correlate player input acknowledgements"
```

---

### Task 2: Generate Collision-Safe Request IDs in Godot

**Files:**
- Create: `scripts/verification/tests/test_phase0_correlated_ack_contract.py`
- Modify: `scripts/player/PlayerIntentMapper.gd`

**Interfaces:**
- Consumes: the Task 1 `PlayerInputBase.request_id` field and ACK echo contract.
- Produces: every `PlayerIntentMapper` envelope contains a unique request ID and a single captured `producer_ts`.

- [ ] **Step 1: Write the failing mapper source-contract test**

Create `scripts/verification/tests/test_phase0_correlated_ack_contract.py`:

```python
from pathlib import Path


SCRIPTS_ROOT = Path(__file__).resolve().parents[2]


def test_player_intent_mapper_generates_collision_safe_request_ids() -> None:
    source = (SCRIPTS_ROOT / "player" / "PlayerIntentMapper.gd").read_text(encoding="utf-8")
    player_input_source = source.split("func emit_visual_fact_event", 1)[0]

    assert "var request_sequence := 0" in player_input_source
    assert "request_sequence += 1" in source
    assert '"player_input:%s:%s:%s:%s"' in source
    assert "[player_actor_id, intent_type, producer_ts, request_sequence]" in source
    assert player_input_source.count('"request_id": request_id') == 4
    assert player_input_source.count('"producer_ts": producer_ts') == 4
    assert "\"producer_ts\": Time.get_ticks_msec()" not in player_input_source
```

- [ ] **Step 2: Run the mapper test and verify RED**

Run:

```powershell
python -m pytest scripts/verification/tests/test_phase0_correlated_ack_contract.py::test_player_intent_mapper_generates_collision_safe_request_ids -v
```

Expected: failure because the mapper has no sequence and directly calls `Time.get_ticks_msec()` in each payload.

- [ ] **Step 3: Replace `PlayerIntentMapper.gd` with the correlated implementation**

Use this complete file content:

```gdscript
extends Node

@export var player_actor_id := "char_c"
@export var player_id := "p1"
@export var room_id := "room_demo"
@export var scene_id := "scene_demo"
@export var zone_id := "zone_focus"

var request_sequence := 0

func emit_dialogue_submit(target_actor_id: String, content: String) -> Dictionary:
    var metadata := _next_request_metadata("dialogue_submit")
    var producer_ts: int = metadata["producer_ts"]
    var request_id: String = metadata["request_id"]
    return {
        "message_type": "player_input",
        "payload": {
            "player_id": player_id,
            "room_id": room_id,
            "scene_id": scene_id,
            "zone_id": zone_id,
            "actor_id": player_actor_id,
            "intent_type": "dialogue_submit",
            "producer_ts": producer_ts,
            "request_id": request_id,
            "target_actor_id": target_actor_id,
            "content": content,
        }
    }

func emit_interact_intent(target_object_id: String, interaction_type: String) -> Dictionary:
    var metadata := _next_request_metadata("interact_intent")
    var producer_ts: int = metadata["producer_ts"]
    var request_id: String = metadata["request_id"]
    return {
        "message_type": "player_input",
        "payload": {
            "player_id": player_id,
            "room_id": room_id,
            "scene_id": scene_id,
            "zone_id": zone_id,
            "actor_id": player_actor_id,
            "intent_type": "interact_intent",
            "producer_ts": producer_ts,
            "request_id": request_id,
            "target_object_id": target_object_id,
            "interaction_type": interaction_type,
        }
    }

func emit_focus_target_change(target_actor_id: String = "", target_object_id: String = "") -> Dictionary:
    var metadata := _next_request_metadata("focus_target_change")
    var producer_ts: int = metadata["producer_ts"]
    var request_id: String = metadata["request_id"]
    var payload := {
        "player_id": player_id,
        "room_id": room_id,
        "scene_id": scene_id,
        "zone_id": zone_id,
        "actor_id": player_actor_id,
        "intent_type": "focus_target_change",
        "producer_ts": producer_ts,
        "request_id": request_id,
    }
    if target_actor_id != "":
        payload["target_actor_id"] = target_actor_id
    if target_object_id != "":
        payload["target_object_id"] = target_object_id
    return {
        "message_type": "player_input",
        "payload": payload,
    }

func emit_move_intent(move_mode: String, target_point: Vector3) -> Dictionary:
    var metadata := _next_request_metadata("move_intent")
    var producer_ts: int = metadata["producer_ts"]
    var request_id: String = metadata["request_id"]
    return {
        "message_type": "player_input",
        "payload": {
            "player_id": player_id,
            "room_id": room_id,
            "scene_id": scene_id,
            "zone_id": zone_id,
            "actor_id": player_actor_id,
            "intent_type": "move_intent",
            "producer_ts": producer_ts,
            "request_id": request_id,
            "move_mode": move_mode,
            "target_point": [target_point.x, target_point.y, target_point.z],
        }
    }

func emit_visual_fact_event(fact_type: String, relation_type: String, target_actor_id: String = "", target_object_id: String = "") -> Dictionary:
    var payload := {
        "actor_id": player_actor_id,
        "room_id": room_id,
        "scene_id": scene_id,
        "zone_id": zone_id,
        "producer_ts": Time.get_ticks_msec(),
        "fact_type": fact_type,
        "relation_type": relation_type,
    }
    if target_actor_id != "":
        payload["target_actor_id"] = target_actor_id
    if target_object_id != "":
        payload["target_object_id"] = target_object_id
    return {
        "message_type": "visual_fact_event",
        "payload": payload,
    }

func _next_request_metadata(intent_type: String) -> Dictionary:
    request_sequence += 1
    var producer_ts := Time.get_ticks_msec()
    var request_id := "player_input:%s:%s:%s:%s" % [player_actor_id, intent_type, producer_ts, request_sequence]
    return {
        "producer_ts": producer_ts,
        "request_id": request_id,
    }
```

- [ ] **Step 4: Run the mapper test and verify GREEN**

Run:

```powershell
python -m pytest scripts/verification/tests/test_phase0_correlated_ack_contract.py::test_player_intent_mapper_generates_collision_safe_request_ids -v
```

Expected: `1 passed`.

- [ ] **Step 5: Commit Task 2**

```powershell
git add scripts/player/PlayerIntentMapper.gd scripts/verification/tests/test_phase0_correlated_ack_contract.py
git commit -m "fix: identify Godot player input requests"
```

---

### Task 3: Replace Route-Only Autotest Synchronization

**Files:**
- Modify: `scripts/phase0/MainDemoController.gd:18-26,68-80,247-259,297-420,885-943`
- Modify: `scripts/verification/tests/test_phase0_correlated_ack_contract.py`
- Modify: `backend/tests/test_verification_audit.py:134-153`

**Interfaces:**
- Consumes: Task 2 descriptors containing `request_id` and `producer_ts`; Task 1 ACK identity fields; existing world-result `correlation_id`.
- Produces: exact-request ACK waits, correlation-scoped success and constraint waits, transport quiescence, quiet-window barrier, and explicit failure evidence.

- [ ] **Step 1: Add failing controller source-contract tests**

Append these tests to `scripts/verification/tests/test_phase0_correlated_ack_contract.py`:

```python
def test_main_demo_tracks_acknowledgements_by_request_id() -> None:
    source = (SCRIPTS_ROOT / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")

    assert "var acknowledged_request_ids: Dictionary = {}" in source
    assert 'var request_id := str(payload.get("request_id", ""))' in source
    assert "acknowledged_request_ids[request_id] = payload.duplicate(true)" in source
    assert "func _wait_for_request_ack(request_id: String, timeout_ms: int) -> bool:" in source
    assert "acknowledged_request_ids.has(request_id)" in source
    assert "pending_failed_move_ack_seen" not in source
    assert "pending_failed_interaction_ack_seen" not in source
    assert 'if str(payload.get("route", "")) == "local_motion":' not in source
    assert 'if str(payload.get("route", "")) == "esm_service":' not in source


def test_main_demo_final_interaction_uses_quiescence_and_correlation_scoped_result() -> None:
    source = (SCRIPTS_ROOT / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")

    assert "@export var autotest_request_timeout_ms := 10000" in source
    assert "@export var autotest_transport_quiet_window_ms := 500" in source
    assert "@export var autotest_transport_quiet_timeout_ms := 10000" in source
    assert "var autotest_transport_quiescent := false" in source
    assert "matched_success_object_result" in source
    assert "matched_success_environment_result" in source
    assert "func _wait_for_backend_quiet(quiet_window_ms: int, timeout_ms: int) -> bool:" in source
    assert 'pending_failed_interaction_correlation_id = "interact:%s" % failed_interaction_request.get("producer_ts", 0)' in source
    assert 'str(payload.get("correlation_id", "")) == pending_failed_interaction_correlation_id' in source
    assert 'await _fail_autotest("far_move_ack_timeout", far_move_request)' in source
    assert 'await _fail_autotest("failed_interaction_ack_timeout", failed_interaction_request)' in source
    assert 'await _fail_autotest("failed_interaction_result_timeout", failed_interaction_request)' in source
    assert '_emit_move_intent_request(autotest_final_position, "locomotion")' not in source


def test_main_demo_timeout_path_cannot_log_failed_interaction_success() -> None:
    source = (SCRIPTS_ROOT / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    run_section = source.split("func _run_autotest_inputs() -> void:", 1)[1].split(
        "func _wait_for_request_ack", 1
    )[0]

    failure_index = run_section.index('await _fail_autotest("failed_interaction_result_timeout", failed_interaction_request)')
    success_index = run_section.index('_bus_log("phase0_autotest_stage:failed_interaction_resolved")')
    assert "return" in run_section[failure_index:success_index]
    assert 'await _begin_autotest_shutdown("phase0_autotest_complete")' in run_section[success_index:]
```

Replace `test_phase0_main_demo_failed_interaction_attempt_waits_for_constraint_result` in `backend/tests/test_verification_audit.py` with:

```python
def test_phase0_main_demo_failed_interaction_attempt_waits_for_correlated_constraint_result() -> None:
    project_root = Path(__file__).resolve().parents[2]
    controller_source = (
        project_root / "scripts" / "phase0" / "MainDemoController.gd"
    ).read_text(encoding="utf-8")

    assert "var acknowledged_request_ids: Dictionary = {}" in controller_source
    assert "pending_failed_move_ack_seen" not in controller_source
    assert "pending_failed_interaction_ack_seen" not in controller_source
    assert "pending_failed_interaction_result_seen" not in controller_source
    assert "await _wait_for_request_ack(" in controller_source
    assert "pending_failed_interaction_correlation_id" in controller_source
    assert "matched_failed_interaction_result" in controller_source
    assert "await _wait_for_failed_interaction_result(autotest_request_timeout_ms)" in controller_source
```

- [ ] **Step 2: Run the controller source-contract tests and verify RED**

Run:

```powershell
python -m pytest scripts/verification/tests/test_phase0_correlated_ack_contract.py backend/tests/test_verification_audit.py::test_phase0_main_demo_failed_interaction_attempt_waits_for_correlated_constraint_result -v
```

Expected: four failures because the controller still uses route-only flags, fixed delays, and uncorrelated constraint matching. The Task 2 mapper test remains green.

- [ ] **Step 3: Replace controller configuration and request-tracking state**

Replace the old failed-interaction timeout export with:

```gdscript
@export var autotest_request_timeout_ms := 10000
@export var autotest_transport_quiet_window_ms := 500
@export var autotest_transport_quiet_timeout_ms := 10000
```

Replace the three route-only pending flags with:

```gdscript
var acknowledged_request_ids: Dictionary = {}
var pending_success_interaction_correlation_id := ""
var matched_success_interaction_result := false
var matched_success_object_result := false
var matched_success_environment_result := false
var pending_failed_interaction_correlation_id := ""
var matched_failed_interaction_result := false
var last_backend_activity_ms := 0
var autotest_transport_quiescent := false
```

- [ ] **Step 4: Replace ACK, world-result, activity, and sampling handlers**

Replace `_on_backend_ack_received`, `_on_world_result_received`, `_on_debug_event_logged`, and `_process` with:

```gdscript
func _on_backend_ack_received(payload: Dictionary) -> void:
	last_backend_activity_ms = Time.get_ticks_msec()
	var request_id := str(payload.get("request_id", ""))
	if request_id != "":
		acknowledged_request_ids[request_id] = payload.duplicate(true)
	_bus_log("phase0_ack:%s" % JSON.stringify(payload))

func _on_world_result_received(payload: Dictionary) -> void:
	last_backend_activity_ms = Time.get_ticks_msec()
	var result_type := str(payload.get("result_type", ""))
	var result_id := str(payload.get("result_id", ""))
	var correlation_id := str(payload.get("correlation_id", ""))
	if (
		result_type == "action_resolution_result"
		and correlation_id == pending_success_interaction_correlation_id
		and str(payload.get("settlement_status", "")) == "accepted"
	):
		matched_success_interaction_result = true
	if (
		result_type == "object_state_result"
		and correlation_id == pending_success_interaction_correlation_id
		and str(payload.get("target_object_id", "")) == "obj_letter"
		and str(payload.get("current_state", "")) == "visible"
	):
		matched_success_object_result = true
	if (
		result_type == "environment_state_result"
		and correlation_id == pending_success_interaction_correlation_id
		and str(payload.get("target_environment_id", "")) == "env_lamp"
		and str(payload.get("current_state", "")) == "alerted"
	):
		matched_success_environment_result = true
	if result_type == "constraint_state_result" and correlation_id == pending_failed_interaction_correlation_id:
		matched_failed_interaction_result = true
	if not autotest_transport_quiescent:
		if result_type == "object_state_result" and str(payload.get("target_object_id", "")) == "obj_letter":
			if str(payload.get("current_state", "")) == "visible":
				if evidence_projection_emitter and evidence_projection_emitter.has_method("emit_visual_evidence_projection"):
					evidence_projection_emitter.emit_visual_evidence_projection("obj_letter")
				if tactile_fact_emitter and tactile_fact_emitter.has_method("emit_contact_fact"):
					tactile_fact_emitter.emit_contact_fact("", "obj_letter", "light")
		elif result_type == "environment_state_result" and str(payload.get("target_environment_id", "")) == "env_lamp":
			if str(payload.get("current_state", "")) == "alerted":
				if thermal_fact_emitter and thermal_fact_emitter.has_method("emit_thermal_proximity_fact"):
					thermal_fact_emitter.emit_thermal_proximity_fact("env_lamp", "warm")
				if olfactory_fact_emitter and olfactory_fact_emitter.has_method("emit_odor_state_fact"):
					olfactory_fact_emitter.emit_odor_state_fact("env_lamp", "noticeable")
	if result_id != "":
		_bus_log("phase0_world_result_seen:%s:%s" % [result_type, result_id])

func _on_debug_event_logged(message: String) -> void:
	if message.begins_with("backend_message_"):
		last_backend_activity_ms = Time.get_ticks_msec()
	if message.contains("focus_state_applied:char_a") or message.contains("focus_attention:char_a"):
		focus_response_seen = true

func _process(_delta: float) -> void:
	if autotest_shutdown_in_progress or autotest_transport_quiescent:
		return
	if focus_override_active:
		if not suspend_spatial_access_fact:
			_sample_spatial_access_facts()
		return
	_update_focus_target()
	if not suspend_near_object_visual_fact:
		_sample_near_object_visual_fact()
	if not suspend_spatial_access_fact:
		_sample_spatial_access_facts()
```

- [ ] **Step 5: Make interaction and move emitters return request descriptors**

Change the three relevant emitter signatures and bodies to:

```gdscript
func _emit_interaction_request(target_object_id: String, interaction_type: String) -> Dictionary:
	var bridge := _get_bridge()
	if bridge == null or intent_mapper == null:
		return {}
	if not intent_mapper.has_method("emit_interact_intent"):
		return {}
	_bus_log("phase0_interact_target:%s" % target_object_id)
	_emit_near_object_visual_fact(target_object_id)
	if bridge.has_method("is_backend_open") and not bridge.is_backend_open():
		pending_interaction_request = {"target_object_id": target_object_id, "interaction_type": interaction_type}
		_request_backend_reconnect()
		return {}
	return _send_player_input_envelope(bridge, intent_mapper.emit_interact_intent(target_object_id, interaction_type))

func _emit_interaction_request_without_near_object_fact(target_object_id: String, interaction_type: String) -> Dictionary:
	var bridge := _get_bridge()
	if bridge == null or intent_mapper == null:
		return {}
	if not intent_mapper.has_method("emit_interact_intent"):
		return {}
	_bus_log("phase0_interact_target:%s" % target_object_id)
	if bridge.has_method("is_backend_open") and not bridge.is_backend_open():
		pending_interaction_request = {"target_object_id": target_object_id, "interaction_type": interaction_type}
		_request_backend_reconnect()
		return {}
	return _send_player_input_envelope(bridge, intent_mapper.emit_interact_intent(target_object_id, interaction_type))

func _emit_move_intent_request(target_point: Vector3, move_mode: String) -> Dictionary:
	var bridge := _get_bridge()
	if bridge == null or intent_mapper == null:
		return {}
	if not intent_mapper.has_method("emit_move_intent"):
		return {}
	_bus_log(
		"phase0_move_target:%s:[%.3f,%.3f,%.3f]" % [
			move_mode,
			target_point.x,
			target_point.y,
			target_point.z,
		]
	)
	if bridge.has_method("is_backend_open") and not bridge.is_backend_open():
		pending_move_request = {"target_point": target_point, "move_mode": move_mode}
		_request_backend_reconnect()
		return {}
	return _send_player_input_envelope(bridge, intent_mapper.emit_move_intent(move_mode, target_point))

func _send_player_input_envelope(bridge: Node, envelope: Dictionary) -> Dictionary:
	var payload_value: Variant = envelope.get("payload", {})
	if not (payload_value is Dictionary):
		return {}
	var payload := payload_value as Dictionary
	var descriptor := {
		"request_id": str(payload.get("request_id", "")),
		"producer_ts": int(payload.get("producer_ts", 0)),
	}
	var err: int = bridge.send_envelope(envelope)
	if err != OK:
		return {}
	return descriptor
```

Existing callers may ignore the returned dictionary. Keep reconnect buffering behavior unchanged.

- [ ] **Step 6: Replace the final autotest sequence and wait helpers**

In `_run_autotest_inputs`, keep the probe and dialogue prefix through `_force_focus_target(interactive_object)`, then replace the remaining interaction sequence with:

```gdscript
	var near_move_request := _emit_move_intent_request(autotest_interact_position, "locomotion")
	if not (await _wait_for_request_ack(str(near_move_request.get("request_id", "")), autotest_request_timeout_ms)):
		await _fail_autotest("near_move_ack_timeout", near_move_request)
		return
	var success_interaction_request := _emit_interaction_request("obj_letter", "inspect")
	pending_success_interaction_correlation_id = "interact:%s" % success_interaction_request.get("producer_ts", 0)
	_bus_log("phase0_autotest_stage:success_interaction_submitted")
	if not (await _wait_for_request_ack(str(success_interaction_request.get("request_id", "")), autotest_request_timeout_ms)):
		await _fail_autotest("success_interaction_ack_timeout", success_interaction_request)
		return
	if not (await _wait_for_successful_interaction_result(autotest_request_timeout_ms)):
		await _fail_autotest("success_interaction_result_timeout", success_interaction_request)
		return
	_move_player_to_demo_vantage()
	autotest_transport_quiescent = true
	suspend_near_object_visual_fact = true
	suspend_spatial_access_fact = true
	last_backend_activity_ms = Time.get_ticks_msec()
	if not (await _wait_for_backend_quiet(autotest_transport_quiet_window_ms, autotest_transport_quiet_timeout_ms)):
		await _fail_autotest("transport_not_quiet", {})
		return
	var far_move_request := _emit_move_intent_request(autotest_failed_interact_position, "locomotion")
	if not (await _wait_for_request_ack(str(far_move_request.get("request_id", "")), autotest_request_timeout_ms)):
		await _fail_autotest("far_move_ack_timeout", far_move_request)
		return
	_orient_player_toward(interactive_object.global_position)
	_bus_log("phase0_autotest_failed_interaction_attempt")
	var failed_interaction_request := _emit_interaction_request_without_near_object_fact("obj_letter", "inspect")
	pending_failed_interaction_correlation_id = "interact:%s" % failed_interaction_request.get("producer_ts", 0)
	if not (await _wait_for_request_ack(str(failed_interaction_request.get("request_id", "")), autotest_request_timeout_ms)):
		await _fail_autotest("failed_interaction_ack_timeout", failed_interaction_request)
		return
	if not (await _wait_for_failed_interaction_result(autotest_request_timeout_ms)):
		await _fail_autotest("failed_interaction_result_timeout", failed_interaction_request)
		return
	_bus_log("phase0_autotest_stage:failed_interaction_resolved")
	await _capture_autotest_screenshot()
	await _begin_autotest_shutdown("phase0_autotest_complete")
```

Add these helper functions immediately after `_run_autotest_inputs`:

```gdscript
func _wait_for_request_ack(request_id: String, timeout_ms: int) -> bool:
	if request_id == "":
		return false
	var deadline := Time.get_ticks_msec() + max(timeout_ms, 1)
	while Time.get_ticks_msec() < deadline:
		if acknowledged_request_ids.has(request_id):
			return true
		await get_tree().process_frame
	return false

func _wait_for_successful_interaction_result(timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + max(timeout_ms, 1)
	while Time.get_ticks_msec() < deadline:
		if matched_success_interaction_result and matched_success_object_result and matched_success_environment_result:
			return true
		await get_tree().process_frame
	return false

func _wait_for_failed_interaction_result(timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + max(timeout_ms, 1)
	while Time.get_ticks_msec() < deadline:
		if matched_failed_interaction_result:
			return true
		await get_tree().process_frame
	return false

func _wait_for_backend_quiet(quiet_window_ms: int, timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + max(timeout_ms, 1)
	while Time.get_ticks_msec() < deadline:
		if Time.get_ticks_msec() - last_backend_activity_ms >= max(quiet_window_ms, 1):
			return true
		await get_tree().process_frame
	return false

func _fail_autotest(stage: String, request: Dictionary) -> void:
	var request_id := str(request.get("request_id", ""))
	_bus_log("phase0_autotest_failure:%s:%s" % [stage, request_id])
	await _capture_autotest_screenshot()
	await _begin_autotest_shutdown("phase0_autotest_failed")
```

Delete `_wait_for_failed_interaction_ack` and `_wait_for_failed_move_ack`. Change the existing `_wait_for_failed_interaction_result` rather than leaving two definitions.

- [ ] **Step 7: Run focused tests and verify GREEN**

Run:

```powershell
python -m pytest scripts/verification/tests/test_phase0_correlated_ack_contract.py backend/tests/test_verification_audit.py backend/tests/test_ws_protocol.py -v
```

Expected: all tests in the three files pass. The suite count increases by five tests relative to the pre-repair branch.

- [ ] **Step 8: Run static Godot parse/import verification**

Run:

```powershell
python scripts/verification/harness.py --profile godot-project
```

Expected: `overall_godot_project_passed=True`; no GDScript parse error from changed return types, typed dictionaries, or await expressions.

- [ ] **Step 9: Commit Task 3**

```powershell
git add scripts/phase0/MainDemoController.gd scripts/verification/tests/test_phase0_correlated_ack_contract.py backend/tests/test_verification_audit.py
git commit -m "fix: synchronize phase0 interaction proof by request"
```

---

### Task 4: Run the Completion Verification Ladder

**Files:**
- No planned tracked source edits.
- Update ignored execution records under `.superpowers/sdd/` with final evidence.
- Generated Harness evidence remains under `.harness/verification/`.

**Interfaces:**
- Consumes: Tasks 1-3 and the existing Heavenly Graph Foundation implementation.
- Produces: fresh proof that both the supplemental Phase 0 repair and original Heavenly Graph change are complete.

- [ ] **Step 1: Check patch hygiene**

Run:

```powershell
git diff --check facec59..HEAD
```

Expected: no output and exit code `0`.

- [ ] **Step 2: Run correlated-ACK focused tests**

Run:

```powershell
python -m pytest backend/tests/test_ws_protocol.py scripts/verification/tests/test_phase0_correlated_ack_contract.py backend/tests/test_verification_audit.py -v
```

Expected: all tests pass.

- [ ] **Step 3: Re-run Heavenly Graph focused tests**

Run:

```powershell
python -m pytest backend/tests/test_siming_heavenly_graph_models.py backend/tests/test_siming_heavenly_graph_contract.py -v
```

Expected: `27 passed`.

- [ ] **Step 4: Run the full pytest suite**

Run:

```powershell
python -m pytest -v
```

Expected: at least `1337 passed`; the existing Pydantic warnings may remain, but no test fails.

- [ ] **Step 5: Run the repaired Phase 0 profile**

Run:

```powershell
python scripts/verification/harness.py --profile phase0
```

Expected:

```text
overall_strict_phase0_passed=True
```

The report must show `failed_interaction` as `proved` with real `constraint_state_result` evidence. No `phase0_autotest_failure:` marker may appear in the main log.

- [ ] **Step 6: Re-run the dedicated Heavenly Graph profile**

Run:

```powershell
python scripts/verification/harness.py --profile siming-heavenly-graph-foundation
```

Expected: `overall_siming_heavenly_graph_foundation_passed=True`.

- [ ] **Step 7: Run broad repository verification**

Run:

```powershell
python scripts/verification/harness.py --profile all
```

Expected: `overall_harness_passed=True`.

- [ ] **Step 8: Confirm scope**

Run:

```powershell
git status --short
git diff --name-only facec59..HEAD
```

Expected tracked scope is the original eleven Heavenly Graph files plus:

```text
backend/app/models/player_input.py
backend/app/main.py
backend/tests/test_ws_protocol.py
backend/tests/test_verification_audit.py
scripts/player/PlayerIntentMapper.gd
scripts/phase0/MainDemoController.gd
scripts/verification/tests/test_phase0_correlated_ack_contract.py
docs/superpowers/specs/current-project-intelligence-upgrade/2026-07-11-phase0-correlated-ack-and-backpressure-design.md
docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-11-phase0-correlated-ack-and-backpressure-implementation-plan.md
```

No ESM, Siming runtime, Heavenly Graph implementation, character-memory, or websocket-loop file beyond the listed backend ACK site may be added by the supplemental repair.

- [ ] **Step 9: Update ignored execution records**

Write the fresh commands, exit codes, pass counts, Phase 0 run ID, broad Harness run ID, and final scope into:

```text
.superpowers/sdd/heavenly-task-7-report.md
.superpowers/sdd/progress.md
```

Mark Task 7 complete only if the broad `all` Harness exits `0`.

- [ ] **Step 10: Request whole-branch review**

Use `superpowers:requesting-code-review` with base `facec59`, current `HEAD`, both approved design/plan files, the Task 4 minor coverage note from the original ledger, and the final verification report.

- [ ] **Step 11: Finish the branch**

Use `superpowers:finishing-a-development-branch` only after the whole-branch review has no open Critical or Important findings and all completion verification remains green.

---

## Self-Review Notes

**Spec coverage:** The plan covers request identity, ACK echo, legacy compatibility, route-only flag removal, world-result correlation, 500 ms quiescence, 10 second bounds, explicit failure markers, focused tests, Godot parse verification, Phase 0 runtime proof, Heavenly Graph regression proof, and broad Harness proof.

**Scope:** The repair is three implementation tasks plus a verification task. It does not change ESM rules or websocket architecture.

**Type consistency:** `request_id`, `producer_ts`, `acknowledged_request_ids`, `pending_success_interaction_correlation_id`, `pending_failed_interaction_correlation_id`, `matched_success_interaction_result`, `matched_success_object_result`, `matched_success_environment_result`, and `matched_failed_interaction_result` use the same names in model, ACK payload, mapper, controller, and tests.

**Test count:** Task 1 adds one test, Task 2 adds one test, and Task 3 adds three tests while replacing one old source-contract test in place, for five additional collected tests and at least 1337 full-suite passes.
