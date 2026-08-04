extends Node

const MAIN_DEMO_SCENE := "res://scenes/phase0/MainDemo.tscn"
const LAUNCH_SCENE := "res://scenes/phase0/ObjArchiveDoorPhysicalEmbodimentProbe.tscn"
const OBJECT_ID := "obj_archive_door"
const INTERACTION_TYPE := "open"
const CONNECT_TIMEOUT_MS := 15000
const SCENARIO_TIMEOUT_MS := 45000

@onready var main_demo: Node3D = $MainDemo

var _scenario := ""
var _runtime_path := ""
var _screenshot_path := ""
var _stage_path := ""
var _backend_connected := false
var _bound_payload: Dictionary = {}
var _request_descriptor: Dictionary = {}
var _action_request_payload: Dictionary = {}
var _settlement_payload: Dictionary = {}
var _local_outcome_payload: Dictionary = {}
var _received_constraint: Dictionary = {}
var _received_world_result: Dictionary = {}
var _presentation_ack: Dictionary = {}
var _phase_names: Array[String] = []
var _phase_payloads: Array[Dictionary] = []
var _ack_payloads: Array[Dictionary] = []
var _debug_messages: Array[String] = []
var _contact_measurement: Dictionary = {}
var _contact_measurement_captured := false
var _player_start_position := Vector3.ZERO
var _player_end_position := Vector3.ZERO
var _pre_snapshot: Dictionary = {}
var _final_snapshot: Dictionary = {}
var _screenshot_source := ""
var _notes: Array[String] = []
var _stage_written := false
var _blocker_body: CharacterBody3D


func _ready() -> void:
	_scenario = OS.get_environment("PARALLS_OBJ_ARCHIVE_DOOR_SCENARIO")
	_runtime_path = OS.get_environment("PARALLS_OBJ_ARCHIVE_DOOR_RUNTIME_PATH")
	_screenshot_path = OS.get_environment("PARALLS_OBJ_ARCHIVE_DOOR_SCREENSHOT_PATH")
	_stage_path = OS.get_environment("PARALLS_OBJ_ARCHIVE_DOOR_STAGE_PATH")
	_connect_bus()
	await get_tree().process_frame
	await _run_probe()


func _process(_delta: float) -> void:
	if _contact_measurement_captured:
		return
	if not _phase_names.has("execute_contact"):
		return
	var replica := _character_replica()
	var contact_anchor := _contact_anchor()
	if replica == null or contact_anchor == null or not replica.has_method("measure_right_hand_to_anchor"):
		return
	var measurement: Variant = replica.call("measure_right_hand_to_anchor", contact_anchor.global_position)
	if measurement is Dictionary and bool((measurement as Dictionary).get("available", false)):
		_contact_measurement = (measurement as Dictionary).duplicate(true)
		_contact_measurement_captured = true


func _run_probe() -> void:
	var ok := false
	_pre_snapshot = _snapshot()
	if not await _wait_for_backend():
		await _finish(false)
		return
	if not await _wait_for_bound_controller():
		await _finish(false)
		return
	await get_tree().create_timer(0.2).timeout
	match _scenario:
		"success":
			ok = await _run_success()
		"distance_failure":
			ok = await _run_distance_failure()
		"revision_failure":
			ok = await _run_revision_failure()
		"stance_failure":
			ok = await _run_stance_failure()
		_:
			_notes.append("unknown_scenario")
			ok = false
	await _finish(ok)


func _connect_bus() -> void:
	var bus := _bus()
	if bus == null:
		return
	if bus.has_signal("backend_connected"):
		bus.backend_connected.connect(_on_backend_connected)
	if bus.has_signal("embodied_controller_bound_received"):
		bus.embodied_controller_bound_received.connect(_on_controller_bound)
	if bus.has_signal("embodied_action_request_received"):
		bus.embodied_action_request_received.connect(_on_action_request_received)
	if bus.has_signal("embodied_phase_event_emitted"):
		bus.embodied_phase_event_emitted.connect(_on_phase_event_emitted)
	if bus.has_signal("embodied_local_outcome_emitted"):
		bus.embodied_local_outcome_emitted.connect(_on_local_outcome_emitted)
	if bus.has_signal("embodied_settlement_result_received"):
		bus.embodied_settlement_result_received.connect(_on_settlement_received)
	if bus.has_signal("world_result_received"):
		bus.world_result_received.connect(_on_world_result_received)
	if bus.has_signal("backend_ack_received"):
		bus.backend_ack_received.connect(_on_backend_ack_received)
	if bus.has_signal("debug_event_logged"):
		bus.debug_event_logged.connect(_on_debug_event_logged)


func _run_success() -> bool:
	_write_stage("success_before_move", {})
	if not await _register_backend_position(_approach_start_position()):
		return false
	_write_stage("success_move_acknowledged", {})
	if not _emit_door_interaction():
		return false
	_write_stage("success_interaction_emitted", _request_descriptor)
	if not await _wait_for_settlement_applied():
		return false
	_write_stage("success_settlement_applied", _settlement_payload)
	await get_tree().create_timer(0.25).timeout
	return true


func _run_distance_failure() -> bool:
	if not await _register_backend_position(Vector3(0.0, 0.5, 25.0)):
		return false
	if not _emit_door_interaction():
		return false
	if not await _wait_for_distance_constraint():
		return false
	await get_tree().create_timer(0.15).timeout
	return true


func _run_revision_failure() -> bool:
	if not await _register_backend_position(_approach_start_position()):
		return false
	if not _emit_door_interaction():
		return false
	if not await _wait_for_rejected_settlement(["binding_revision_mismatch", "revision_conflict", "door_state_stale"]):
		return false
	await get_tree().create_timer(0.25).timeout
	return true


func _run_stance_failure() -> bool:
	_spawn_stance_blocker()
	if not await _register_backend_position(_approach_start_position()):
		return false
	if not _emit_door_interaction():
		return false
	if not await _wait_for_rejected_settlement(["stance_occupied"]):
		return false
	await get_tree().create_timer(0.15).timeout
	return true


func _wait_for_backend() -> bool:
	var deadline := Time.get_ticks_msec() + CONNECT_TIMEOUT_MS
	while Time.get_ticks_msec() < deadline:
		if _backend_connected:
			return true
		await get_tree().process_frame
	_notes.append("backend_connect_timeout")
	return false


func _wait_for_bound_controller() -> bool:
	var deadline := Time.get_ticks_msec() + CONNECT_TIMEOUT_MS
	while Time.get_ticks_msec() < deadline:
		if str(_bound_payload.get("state", "")) == "bound":
			return true
		await get_tree().process_frame
	_notes.append("controller_bind_timeout")
	return false


func _register_backend_position(target_position: Vector3) -> bool:
	var player := _player()
	if player == null:
		_notes.append("missing_player")
		return false
	_player_start_position = player.global_position
	var controller := _controller()
	if controller == null or not controller.has_method("_emit_move_intent_request"):
		_notes.append("missing_main_demo_controller")
		return false
	var descriptor: Variant = controller.call("_emit_move_intent_request", target_position, "locomotion")
	if not (descriptor is Dictionary):
		_notes.append("move_request_missing_descriptor")
		return false
	var request_id := str((descriptor as Dictionary).get("request_id", ""))
	if request_id.is_empty():
		_notes.append("move_request_missing_request_id")
		return false
	var deadline := Time.get_ticks_msec() + CONNECT_TIMEOUT_MS
	while Time.get_ticks_msec() < deadline:
		for payload: Dictionary in _ack_payloads:
			if str(payload.get("request_id", "")) == request_id:
				return true
		await get_tree().process_frame
	_notes.append("move_request_ack_timeout")
	return false


func _emit_door_interaction() -> bool:
	var controller := _controller()
	if controller == null or not controller.has_method("_emit_interaction_request_without_near_object_fact"):
		_notes.append("missing_interaction_emitter")
		return false
	var descriptor: Variant = controller.call(
		"_emit_interaction_request_without_near_object_fact",
		OBJECT_ID,
		INTERACTION_TYPE
	)
	if not (descriptor is Dictionary):
		_notes.append("interaction_request_missing_descriptor")
		return false
	_request_descriptor = (descriptor as Dictionary).duplicate(true)
	return not _request_descriptor.is_empty()


func _wait_for_settlement_applied() -> bool:
	var deadline := Time.get_ticks_msec() + SCENARIO_TIMEOUT_MS
	while Time.get_ticks_msec() < deadline:
		if str(_settlement_payload.get("settlement_status", "")) == "applied" and str(_received_world_result.get("current_state", "")) == "open":
			return true
		if str(_settlement_payload.get("settlement_status", "")) == "rejected":
			_notes.append("success_settlement_rejected")
			return false
		if not _local_outcome_payload.is_empty():
			_notes.append("success_terminal_local_failure")
			return false
		await get_tree().process_frame
	_notes.append("success_settlement_timeout")
	return false


func _wait_for_distance_constraint() -> bool:
	var deadline := Time.get_ticks_msec() + SCENARIO_TIMEOUT_MS
	while Time.get_ticks_msec() < deadline:
		if str(_received_constraint.get("constraint_code", "")) == "out_of_range":
			return true
		await get_tree().process_frame
	_notes.append("distance_constraint_timeout")
	return false


func _wait_for_rejected_settlement(accepted_error_codes: Array[String]) -> bool:
	var deadline := Time.get_ticks_msec() + SCENARIO_TIMEOUT_MS
	while Time.get_ticks_msec() < deadline:
		if accepted_error_codes.has(str(_settlement_payload.get("error_code", ""))):
			return true
		await get_tree().process_frame
	_notes.append("rejected_settlement_timeout")
	return false


func _finish(ok: bool) -> void:
	if _blocker_body != null:
		_blocker_body.queue_free()
	_blocker_body = null
	_player_end_position = _player().global_position if _player() != null else Vector3.ZERO
	_final_snapshot = _snapshot()
	await get_tree().process_frame
	var screenshot_result := _capture_screenshot()
	var payload := {
		"status": "scenario-verified" if ok and screenshot_result else "scenario-failed",
		"scenario": _scenario,
		"scene": MAIN_DEMO_SCENE,
		"launch_scene": LAUNCH_SCENE,
		"request_id": str(_request_descriptor.get("request_id", "")),
		"correlation_id": "interact:%s" % str(_request_descriptor.get("producer_ts", 0)) if not _request_descriptor.is_empty() else "",
		"attempt_id": str(_action_request_payload.get("request", {}).get("interaction_attempt_id", "")),
		"grant_id": str(_action_request_payload.get("grant", {}).get("grant_id", "")) if not _action_request_payload.is_empty() else null,
		"settlement_id": str(_settlement_payload.get("settlement_id", "")) if not _settlement_payload.is_empty() else null,
		"pinned_revisions": {
			"binding_revision": _action_request_payload.get("request", {}).get("binding_revision", null),
			"scene_revision": _action_request_payload.get("request", {}).get("scene_revision", null),
			"policy_revision": _action_request_payload.get("request", {}).get("policy_revision", null),
		},
		"player_start_position": _vec3_to_dict(_player_start_position),
		"player_end_position": _vec3_to_dict(_player_end_position),
		"actual_movement_delta": _player_start_position.distance_to(_player_end_position),
		"facing_error_rad": _current_facing_error_rad(),
		"ik_runtime_kind": str(_contact_measurement.get("runtime_kind", "")),
		"ik_chain_bones": _contact_measurement.get("chain_bones", []),
		"ik_error_code": str(_contact_measurement.get("error_code", "")),
		"ordered_phases": _phase_names,
		"phase_payloads": _phase_payloads,
		"requested_atoms": _action_request_payload.get("request", {}).get("realization_metadata", {}).get("primitive_action_tags", []),
		"motor_owner": "PlayerShell",
		"host_runtime_state": _host_runtime_state(),
		"live_backend": {
			"transport": "websocket",
			"connected": _backend_connected,
			"controller_bound": str(_bound_payload.get("state", "")) == "bound",
		},
		"received_constraint": _received_constraint,
		"received_settlement": _settlement_payload,
		"received_world_result": _received_world_result,
		"local_outcome": _local_outcome_payload,
		"presentation_ack": _presentation_ack,
		"pre_snapshot": _pre_snapshot,
		"final_snapshot": _final_snapshot,
		"replay_join": {
			"attempt_id": str(_action_request_payload.get("request", {}).get("interaction_attempt_id", "")),
			"settlement_id": str(_settlement_payload.get("settlement_id", "")),
		},
		"screenshot": _screenshot_path if screenshot_result else "",
		"screenshot_source": _screenshot_source,
		"notes": _notes,
	}
	_write_json(_runtime_path, payload)
	_write_stage("complete", payload)
	get_tree().quit(0 if str(payload.get("status", "")) == "scenario-verified" else 1)


func _capture_screenshot() -> bool:
	if _screenshot_path.is_empty():
		_notes.append("missing_screenshot_path")
		return false
	var texture := get_viewport().get_texture()
	if texture == null:
		_notes.append("viewport_texture_unavailable")
		return false
	var image := get_viewport().get_texture().get_image()
	if image == null or image.is_empty():
		_notes.append("viewport_image_unavailable")
		return false
	_screenshot_source = "viewport_texture"
	DirAccess.make_dir_recursive_absolute(_screenshot_path.get_base_dir())
	return image.save_png(_screenshot_path) == OK


func _spawn_stance_blocker() -> void:
	var stance := _approach_stance()
	if stance == null or main_demo == null:
		return
	var blocker := CharacterBody3D.new()
	blocker.name = "ProbeStanceBlocker"
	var collision := CollisionShape3D.new()
	var shape := CapsuleShape3D.new()
	shape.radius = 0.35
	shape.height = 1.2
	collision.shape = shape
	blocker.add_child(collision)
	main_demo.add_child(blocker)
	blocker.global_position = stance.global_position
	_blocker_body = blocker


func _approach_start_position() -> Vector3:
	var stance := _approach_stance()
	if stance == null:
		return Vector3(0.0, 0.5, -1.8)
	return Vector3(stance.global_position.x, 0.5, stance.global_position.z + 1.6)


func _current_facing_error_rad() -> float:
	var player := _player()
	var contact_anchor := _contact_anchor()
	if player == null or contact_anchor == null:
		return INF
	var facing := contact_anchor.global_position - player.global_position
	facing.y = 0.0
	if facing.length() <= 0.001:
		return 0.0
	var desired_yaw := atan2(-facing.x, -facing.z)
	return absf(wrapf(player.rotation.y - desired_yaw, -PI, PI))


func _snapshot() -> Dictionary:
	var presentation := _presentation()
	if presentation == null or not presentation.has_method("snapshot"):
		return {}
	var value: Variant = presentation.call("snapshot")
	return value if value is Dictionary else {}


func _on_backend_connected(_payload: Variant) -> void:
	_backend_connected = true


func _on_controller_bound(payload: Dictionary) -> void:
	_bound_payload = payload.duplicate(true)
	_write_stage("controller_bound", payload)


func _on_action_request_received(payload: Dictionary) -> void:
	var request: Variant = payload.get("request", {})
	if not (request is Dictionary):
		return
	if str((request as Dictionary).get("target_ref", "")) != OBJECT_ID:
		return
	_action_request_payload = payload.duplicate(true)
	if _scenario == "revision_failure" and not _stage_written:
		_write_stage(
			"preflight_accepted",
			{
				"grant_id": str(payload.get("grant", {}).get("grant_id", "")),
				"attempt_id": str((request as Dictionary).get("interaction_attempt_id", "")),
			}
		)
		_stage_written = true


func _on_phase_event_emitted(payload: Dictionary) -> void:
	_phase_payloads.append(payload.duplicate(true))
	var digest := str(payload.get("payload_digest", ""))
	if digest.begins_with("sha256:archive-door:"):
		var parts := digest.split(":")
		if parts.size() >= 4:
			_phase_names.append(parts[parts.size() - 1])


func _on_local_outcome_emitted(payload: Dictionary) -> void:
	_local_outcome_payload = payload.duplicate(true)


func _on_settlement_received(payload: Dictionary) -> void:
	_settlement_payload = payload.duplicate(true)


func _on_world_result_received(payload: Dictionary) -> void:
	if str(payload.get("target_object_id", "")) != OBJECT_ID:
		return
	var result_type := str(payload.get("result_type", ""))
	if result_type == "constraint_state_result":
		_received_constraint = payload.duplicate(true)
	if result_type == "object_state_result":
		_received_world_result = payload.duplicate(true)


func _on_backend_ack_received(payload: Dictionary) -> void:
	_ack_payloads.append(payload.duplicate(true))
	if str(payload.get("route", "")) == "default_scene_archive_door_presentation_evidence":
		_presentation_ack = payload.duplicate(true)


func _on_debug_event_logged(message: String) -> void:
	_debug_messages.append(message)


func _write_stage(stage: String, payload: Dictionary) -> void:
	if _stage_path.is_empty():
		return
	_write_json(
		_stage_path,
		{
			"scenario": _scenario,
			"stage": stage,
			"payload": payload,
		}
	)


func _write_json(path: String, payload: Dictionary) -> void:
	if path.is_empty():
		return
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return
	file.store_string(JSON.stringify(payload, "\t"))
	file.close()


func _vec3_to_dict(value: Vector3) -> Dictionary:
	return {"x": value.x, "y": value.y, "z": value.z}


func _bus() -> Node:
	return get_node_or_null("/root/LocalPresentationBus")


func _controller() -> Node:
	return main_demo


func _player() -> CharacterBody3D:
	return main_demo.get_node_or_null("PlayerCharacter") as CharacterBody3D if main_demo != null else null


func _presentation() -> Node:
	return main_demo.get_node_or_null("ArchiveDoorPhysical/ArchiveDoorPhysicalPresentation") if main_demo != null else null


func _approach_stance() -> Marker3D:
	return main_demo.get_node_or_null("ArchiveDoorPhysical/ApproachStance") as Marker3D if main_demo != null else null


func _contact_anchor() -> Marker3D:
	return main_demo.get_node_or_null("ArchiveDoorPhysical/ContactAnchor") as Marker3D if main_demo != null else null


func _character_replica() -> Node:
	return main_demo.get_node_or_null("PlayerCharacter/CharacterReplica") if main_demo != null else null


func _host_runtime_state() -> Dictionary:
	var host := main_demo.get_node_or_null("PlayerCharacter/ArchiveDoorEmbodiedActionHost") if main_demo != null else null
	if host == null:
		return {"present": false}
	if not host.has_method("runtime_status"):
		return {"present": true, "status_available": false}
	var status: Variant = host.call("runtime_status")
	if not (status is Dictionary):
		return {"present": true, "status_available": false}
	var result := (status as Dictionary).duplicate(true)
	result["present"] = true
	result["status_available"] = true
	return result
