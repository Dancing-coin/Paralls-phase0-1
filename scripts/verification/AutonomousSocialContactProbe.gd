extends Node

const BACKEND_URL := "ws://127.0.0.1:8000/ws"
const NOTICE_MARKER := "autonomous_contact:notice=true"
const APPROACH_STARTED_MARKER := "autonomous_contact:approach_started=true"
const ARRIVAL_FACT_MARKER := "autonomous_contact:arrival_fact=true"
const GREETING_APPLIED_MARKER := "autonomous_contact:greeting_applied=true"
const ALL_CHECKS_COMPLETE_MARKER := "autonomous_social_contact_probe:all_checks_complete=true"

var _backend_connected := false
var _notice_seen := false
var _approach_started_seen := false
var _arrival_fact_seen := false
var _greeting_applied_seen := false


func _ready() -> void:
	call_deferred("_run_probe")


func _run_probe() -> void:
	var bus := get_node_or_null("/root/LocalPresentationBus")
	if bus == null:
		push_error("autonomous_social_contact_probe:missing_local_presentation_bus")
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
		push_error("autonomous_social_contact_probe:missing_main_demo_child")
		get_tree().quit(1)
		return

	var character_a := main_demo.get_node_or_null("CharacterA")
	var character_b := main_demo.get_node_or_null("CharacterB")
	if character_a == null or character_b == null:
		push_error("autonomous_social_contact_probe:missing_character_nodes")
		get_tree().quit(1)
		return
	character_a.global_position = Vector3.ZERO
	character_b.global_position = Vector3(0.0, 0.0, 0.25)
	character_a.set("actor_arrival_distance", 0.0)
	character_a.set("use_root_motion_patrol", false)

	var bridge := get_node_or_null("/root/BackendBridge")
	if bridge == null:
		push_error("autonomous_social_contact_probe:missing_backend_bridge")
		get_tree().quit(1)
		return
	var connect_err: int = bridge.connect_to_backend(BACKEND_URL)
	if connect_err != OK:
		push_error("autonomous_social_contact_probe:backend_connect_failed:%s" % connect_err)
		get_tree().quit(1)
		return

	if not await _wait_for_backend_connected(10000):
		push_error("autonomous_social_contact_probe:backend_connect_timeout")
		get_tree().quit(1)
		return

	if not await _wait_for_notice(10000):
		push_error("autonomous_social_contact_probe:notice_timeout")
		get_tree().quit(1)
		return

	bus.emit_signal("character_agent_execution_received", _execution_payload())

	if not await _wait_for_contact_markers(10000):
		push_error("autonomous_social_contact_probe:contact_marker_timeout")
		get_tree().quit(1)
		return

	print("autonomous_social_contact_probe:backend_connected=%s" % _backend_connected)
	print("autonomous_social_contact_probe:notice_seen=%s" % _notice_seen)
	print("autonomous_social_contact_probe:approach_started_seen=%s" % _approach_started_seen)
	print("autonomous_social_contact_probe:arrival_fact_seen=%s" % _arrival_fact_seen)
	print("autonomous_social_contact_probe:greeting_applied_seen=%s" % _greeting_applied_seen)
	print(ALL_CHECKS_COMPLETE_MARKER)
	get_tree().quit(0)


func _execution_payload() -> Dictionary:
	return {
		"actor_id": "char_a",
		"actor_control_frames": [
			{
				"actor_id": "char_a",
				"producer_ts": 1901,
				"causation_id": "character_agent:1901:char_a",
				"correlation_id": "character_agent:1901:char_a",
				"controller_source": "agent",
				"control_mode": "agent_controlled",
				"target_ref": "char_b",
				"action": "approach",
				"gait": "walk",
			}
		],
		"presentation_plan": {
			"actor_id": "char_a",
			"target_ref": "char_b",
			"motion_state": {
				"posture": "advancing",
				"gesture_hint": "reach_forward",
				"hesitation_hint": "steady_motion",
				"motion_emphasis": "forward_intent",
			},
			"focus_state": {
				"target_id": "char_b",
				"spacing_behavior": "close_distance",
				"orientation_mode": "close_distance",
				"focus_mode": "track_target",
			},
			"action_state": {
				"requested_action": "approach",
				"override_state": "",
			},
			"contact_phase": "greeting",
			"execution_semantics": {
				"movement_intent": "approach",
				"contact_phase": "greeting",
				"speech_mode": "none",
				"gesture_mode": "acknowledge",
			},
			"equipment_state": {},
			"expression_hint": "social_signal",
			"physiology_hint": "stable",
			"speech_state": {
				"active_command_type": "approach",
				"utterance_request": "",
			},
		},
		"action_request_bundle": {
			"requested_actions": [
				{
					"request_type": "approach",
					"actor_id": "char_a",
					"target_actor_id": "char_b",
				}
			]
		},
	}


func _on_backend_connected(_url: String) -> void:
	_backend_connected = true


func _on_debug_event_logged(message: String) -> void:
	if NOTICE_MARKER in message:
		_notice_seen = true
	if APPROACH_STARTED_MARKER in message:
		_approach_started_seen = true
	if ARRIVAL_FACT_MARKER in message:
		_arrival_fact_seen = true
	if GREETING_APPLIED_MARKER in message:
		_greeting_applied_seen = true


func _wait_for_backend_connected(timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		if _backend_connected:
			return true
		await get_tree().process_frame
	return false


func _wait_for_notice(timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		if _notice_seen:
			return true
		await get_tree().process_frame
	return false


func _wait_for_contact_markers(timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		if _approach_started_seen and _arrival_fact_seen and _greeting_applied_seen:
			return true
		await get_tree().process_frame
	return false
