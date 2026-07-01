extends Node

const BACKEND_URL := "ws://127.0.0.1:8000/ws"
const NOTICE_MARKER := "actor_local_perception:notice_emitted=true"
const FACT_ROUTED_MARKER := "actor_local_perception:fact_routed=true"
const CHARACTER_RUNTIME_MARKER := "actor_local_perception:character_runtime_seen=true"
const ALL_CHECKS_COMPLETE_MARKER := "actor_local_perception_probe:all_checks_complete=true"

var _backend_connected := false
var _notice_seen := false
var _fact_routed_seen := false
var _character_runtime_seen := false


func _ready() -> void:
	call_deferred("_run_probe")


func _run_probe() -> void:
	var bus := get_node_or_null("/root/LocalPresentationBus")
	if bus == null:
		push_error("actor_local_perception_probe:missing_local_presentation_bus")
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
		push_error("actor_local_perception_probe:missing_main_demo_child")
		get_tree().quit(1)
		return

	var character_a := main_demo.get_node_or_null("CharacterA")
	var character_b := main_demo.get_node_or_null("CharacterB")
	if character_a == null or character_b == null:
		push_error("actor_local_perception_probe:missing_character_nodes")
		get_tree().quit(1)
		return
	character_a.global_position = Vector3.ZERO
	character_b.global_position = Vector3(0.0, 0.0, 1.0)
	character_a.set("actor_arrival_distance", 0.0)

	var bridge := get_node_or_null("/root/BackendBridge")
	if bridge == null:
		push_error("actor_local_perception_probe:missing_backend_bridge")
		get_tree().quit(1)
		return
	var connect_err: int = bridge.connect_to_backend(BACKEND_URL)
	if connect_err != OK:
		push_error("actor_local_perception_probe:backend_connect_failed:%s" % connect_err)
		get_tree().quit(1)
		return

	if not await _wait_for_backend_connected(10000):
		push_error("actor_local_perception_probe:backend_connect_timeout")
		get_tree().quit(1)
		return

	if not await _wait_for_markers(10000):
		push_error("actor_local_perception_probe:marker_timeout")
		get_tree().quit(1)
		return

	print("actor_local_perception_probe:backend_connected=%s" % _backend_connected)
	print("actor_local_perception_probe:notice_seen=%s" % _notice_seen)
	print("actor_local_perception_probe:fact_routed_seen=%s" % _fact_routed_seen)
	print("actor_local_perception_probe:character_runtime_seen=%s" % _character_runtime_seen)
	print(ALL_CHECKS_COMPLETE_MARKER)
	get_tree().quit(0)


func _on_backend_connected(_url: String) -> void:
	_backend_connected = true


func _on_debug_event_logged(message: String) -> void:
	if NOTICE_MARKER in message:
		_notice_seen = true
	if FACT_ROUTED_MARKER in message:
		_fact_routed_seen = true
	if CHARACTER_RUNTIME_MARKER in message:
		_character_runtime_seen = true


func _wait_for_backend_connected(timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		if _backend_connected:
			return true
		await get_tree().process_frame
	return false


func _wait_for_markers(timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		if _notice_seen and _fact_routed_seen and _character_runtime_seen:
			return true
		await get_tree().process_frame
	return false
