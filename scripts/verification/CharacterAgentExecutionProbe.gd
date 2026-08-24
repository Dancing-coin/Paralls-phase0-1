extends Node

const BACKEND_URL := "ws://127.0.0.1:8000/ws?stream_mode=runtime_only"
const EXECUTION_PAYLOAD_DIRECT_MARKER := "character_agent_execution_probe:execution_payload_direct=true"
const CONSUMER_SEEN_MARKER := "character_agent_execution_probe:consumer_seen=true"
const ALL_CHECKS_COMPLETE_MARKER := "character_agent_execution_probe:all_checks_complete=true"

var _execution_seen := false
var _legacy_output_seen := false
var _contract_seen := false
var _execution_payload_direct := false
var _backend_connected := false
var _raw_fact_sent := false
var _consumer_seen := false
var _consumer_node_is_character_replica := false
var _observed_execution_actor_id := ""
var _execution_applied_actor_id := ""


func _ready() -> void:
	call_deferred("_run_probe")


func _run_probe() -> void:
	var bus := get_node_or_null("/root/LocalPresentationBus")
	if bus == null:
		push_error("character_agent_execution_probe:missing_local_presentation_bus")
		get_tree().quit(1)
		return
	if bus.has_method("set_debug_logging_enabled"):
		bus.set_debug_logging_enabled(true)
	if bus.has_signal("debug_event_logged"):
		bus.debug_event_logged.connect(_on_debug_event_logged)
	if bus.has_signal("backend_connected"):
		bus.backend_connected.connect(_on_backend_connected)

	var main_demo := get_node_or_null("MainDemo")
	if main_demo == null:
		push_error("character_agent_execution_probe:missing_main_demo_child")
		get_tree().quit(1)
		return

	var bridge := get_node_or_null("/root/BackendBridge")
	if bridge == null:
		push_error("character_agent_execution_probe:missing_backend_bridge")
		get_tree().quit(1)
		return
	var connect_err: int = bridge.connect_to_backend(BACKEND_URL)
	if connect_err != OK:
		push_error("character_agent_execution_probe:backend_connect_failed:%s" % connect_err)
		get_tree().quit(1)
		return

	var connected_ok := await _wait_for_backend_connected(10000)
	if not connected_ok:
		push_error("character_agent_execution_probe:backend_connect_timeout")
		get_tree().quit(1)
		return

	var character_a := main_demo.get_node_or_null("CharacterA")
	var character_b := main_demo.get_node_or_null("CharacterB")
	if character_a == null and character_b == null:
		push_error("character_agent_execution_probe:missing_character_consumers")
		get_tree().quit(1)
		return

	var envelope := {
		"message_type": "raw_fact_event",
		"payload": {
			"event_type": "raw_fact_event",
			"fact_family": "visual_fact",
			"fact_type": "fixed_gaze_on_target",
			"relation_type": "actor_looks_at_actor",
			"producer_ts": 901,
			"room_id": "room_demo",
			"scene_id": "scene_demo",
			"zone_id": "zone_focus",
			"source": {
				"layer": "L1",
				"system": "godot.raw_fact_emitter",
				"actor_id": "char_c",
				"object_id": "",
				"environment_id": "",
			},
			"targets": {
				"actor_id": "char_a",
				"object_id": "",
				"environment_id": "",
			},
			"world": {},
			"observability": {
				"visual": true,
				"auditory": false,
				"occluded": false,
			},
			"acoustics": {},
			"effect_kind": "pulse",
			"subject_key": "",
			"causation_id": "vf:901",
			"correlation_id": "vf:901",
		},
	}
	var err: int = bridge.send_envelope(envelope)
	if err != OK:
		push_error("character_agent_execution_probe:send_failed:%s" % err)
		get_tree().quit(1)
		return
	_raw_fact_sent = true

	# The raw-fact websocket sends its authority ack first and computes the
	# character follow-up on a worker; allow the structured execution envelope
	# its full backend budget before declaring the probe failed.
	var execution_ok := await _wait_for_execution_contract(30000)
	if not execution_ok:
		push_error("character_agent_execution_probe:execution_contract_timeout")
		get_tree().quit(1)
		return

	if _legacy_output_seen:
		push_error("character_agent_execution_probe:legacy_runtime_output_seen")
		get_tree().quit(1)
		return

	var consumer_node := _resolve_consumer_node(main_demo)
	_consumer_node_is_character_replica = (
		consumer_node != null
		and consumer_node.name == "CharacterReplica"
	)
	var target_actor_id := _execution_applied_actor_id
	if target_actor_id.is_empty():
		target_actor_id = _observed_execution_actor_id
	_consumer_seen = (
		consumer_node != null
		and not target_actor_id.is_empty()
		and _execution_applied_actor_id == target_actor_id
	)
	if not _consumer_seen:
		push_error("character_agent_execution_probe:character_replica_consumer_not_observed")
		get_tree().quit(1)
		return

	print("character_agent_execution_probe:backend_connected=%s" % _backend_connected)
	print("character_agent_execution_probe:raw_fact_sent=%s" % _raw_fact_sent)
	print("character_agent_execution_probe:execution_seen=%s" % _execution_seen)
	print("character_agent_execution_probe:contract_seen=%s" % _contract_seen)
	print(EXECUTION_PAYLOAD_DIRECT_MARKER if _execution_payload_direct else "character_agent_execution_probe:execution_payload_direct=false")
	print("character_agent_execution_probe:legacy_output_seen=%s" % _legacy_output_seen)
	print(CONSUMER_SEEN_MARKER if _consumer_seen else "character_agent_execution_probe:consumer_seen=false")
	print("character_agent_execution_probe:consumer_node_is_character_replica=%s" % _consumer_node_is_character_replica)
	print("character_agent_execution_probe:observed_execution_actor_id=%s" % _observed_execution_actor_id)
	print("character_agent_execution_probe:execution_applied_actor_id=%s" % _execution_applied_actor_id)
	_capture_autotest_screenshot()
	print(ALL_CHECKS_COMPLETE_MARKER)
	get_tree().quit(0)


func _on_backend_connected(_url: String) -> void:
	_backend_connected = true


func _on_debug_event_logged(message: String) -> void:
	if "character_agent_output:" in message:
		_legacy_output_seen = true
	if "backend_message_type:character_agent_execution" in message:
		_execution_seen = true
	if "backend_message_raw:" in message and '"message_type":"character_agent_execution"' in message:
		var raw_prefix := "backend_message_raw:"
		var raw_index := message.find(raw_prefix)
		if raw_index >= 0:
			var raw_json := message.substr(raw_index + raw_prefix.length())
			var parsed: Variant = JSON.parse_string(raw_json)
			if parsed is Dictionary:
				var payload: Variant = parsed.get("payload", {})
				if payload is Dictionary:
					var payload_dict: Dictionary = payload as Dictionary
					var actor_id_value := str(payload_dict.get("actor_id", ""))
					if not actor_id_value.is_empty():
						_observed_execution_actor_id = actor_id_value
					if payload_dict.has("actor_control_frames") and payload_dict.has("presentation_plan") and payload_dict.has("action_request_bundle"):
						_execution_payload_direct = true
	if "character_agent_execution_applied:" in message:
		var applied_prefix := "character_agent_execution_applied:"
		var applied_index := message.find(applied_prefix)
		if applied_index >= 0:
			_execution_applied_actor_id = message.substr(applied_index + applied_prefix.length()).strip_edges()
	if (
		'"controller_source":"agent"' in message
		and '"control_mode":"agent_controlled"' in message
		and '"focus_state":{' in message
		and '"action_state":{' in message
		and '"speech_state":{' in message
	):
		_contract_seen = true


func _wait_for_backend_connected(timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		if _backend_connected:
			return true
		await get_tree().process_frame
	return false


func _wait_for_execution_contract(timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		if _execution_seen and (not _execution_applied_actor_id.is_empty() or _contract_seen):
			return true
		await get_tree().process_frame
	return false


func _resolve_consumer_node(main_demo: Node) -> Node:
	var target_actor_id := _execution_applied_actor_id
	if target_actor_id.is_empty():
		target_actor_id = _observed_execution_actor_id
	if target_actor_id.is_empty():
		return null
	match target_actor_id:
		"char_a":
			return main_demo.get_node_or_null("CharacterA")
		"char_b":
			return main_demo.get_node_or_null("CharacterB")
		"char_c":
			var player_character := main_demo.get_node_or_null("PlayerCharacter")
			if player_character != null:
				return player_character.get_node_or_null("CharacterReplica")
	return null


func _capture_autotest_screenshot() -> void:
	var screenshot_path := OS.get_environment("PHASE0_AUTOTEST_SCREENSHOT")
	if screenshot_path == "":
		return
	var image := get_viewport().get_texture().get_image()
	var err := image.save_png(screenshot_path)
	print("character_agent_execution_probe:screenshot_saved=%s:%s" % [screenshot_path, err])
