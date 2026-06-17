extends Node

const MAIN_DEMO_SCENE := preload("res://scenes/phase0/MainDemo.tscn")

var _zone_entry_count := 0
var _disconnect_count := 0
var _environment_alert_count := 0
var _privacy_local_count := 0
var _backend_connected := false


func _ready() -> void:
	call_deferred("_run_probe")


func _run_probe() -> void:
	var bus := get_node_or_null("/root/LocalPresentationBus")
	if bus == null:
		push_error("l1_runtime_probe:missing_local_presentation_bus")
		get_tree().quit(1)
		return
	if bus.has_method("set_debug_logging_enabled"):
		bus.set_debug_logging_enabled(true)
	if bus.has_signal("debug_event_logged"):
		bus.debug_event_logged.connect(_on_debug_event_logged)
	if bus.has_signal("backend_connected"):
		bus.backend_connected.connect(_on_backend_connected)
	if bus.has_signal("backend_disconnected"):
		bus.backend_disconnected.connect(_on_backend_disconnected)

	var main_demo := MAIN_DEMO_SCENE.instantiate()
	add_child(main_demo)
	if bus.has_method("set_debug_logging_enabled"):
		bus.set_debug_logging_enabled(true)

	var backend_connected_ok := await _wait_for_backend_connected(10000)
	if not backend_connected_ok:
		push_error("l1_runtime_probe:backend_connect_timeout")
		get_tree().quit(1)
		return
	main_demo.call("_emit_spatial_access_zone_entry")
	main_demo.call("_sample_privacy_boundary_fact")

	var initial_zone_ok := await _wait_for_zone_entries(1, 10000)
	if not initial_zone_ok:
		print("l1_runtime_probe:zone_entry_count_before_timeout=%s" % _zone_entry_count)
		print("l1_runtime_probe:privacy_local_count_before_timeout=%s" % _privacy_local_count)
		push_error("l1_runtime_probe:initial_zone_entry_timeout")
		get_tree().quit(1)
		return

	var initial_privacy_ok := await _wait_for_privacy_local(1, 10000)
	if not initial_privacy_ok:
		print("l1_runtime_probe:zone_entry_count_before_timeout=%s" % _zone_entry_count)
		print("l1_runtime_probe:privacy_local_count_before_timeout=%s" % _privacy_local_count)
		push_error("l1_runtime_probe:initial_privacy_local_timeout")
		get_tree().quit(1)
		return

	var bridge := get_node_or_null("/root/BackendBridge")
	if bridge == null:
		push_error("l1_runtime_probe:missing_backend_bridge")
		get_tree().quit(1)
		return

	bridge.ws.close()

	var disconnect_ok := await _wait_for_disconnect(1, 5000)
	if not disconnect_ok:
		print("l1_runtime_probe:disconnect_count_before_timeout=%s" % _disconnect_count)
		push_error("l1_runtime_probe:disconnect_signal_timeout")
		get_tree().quit(1)
		return

	var reconnect_err: int = bridge.connect_to_backend(main_demo.backend_url)
	if reconnect_err != OK:
		push_error("l1_runtime_probe:reconnect_failed:%s" % reconnect_err)
		get_tree().quit(1)
		return
	main_demo.call("_emit_spatial_access_zone_entry")
	main_demo.call("_sample_privacy_boundary_fact")

	var reseed_ok := await _wait_for_zone_entries(2, 10000)
	if not reseed_ok:
		print("l1_runtime_probe:zone_entry_count_before_timeout=%s" % _zone_entry_count)
		push_error("l1_runtime_probe:zone_reseed_timeout")
		get_tree().quit(1)
		return

	var privacy_reseed_ok := await _wait_for_privacy_local(2, 10000)
	if not privacy_reseed_ok:
		print("l1_runtime_probe:privacy_local_count_before_timeout=%s" % _privacy_local_count)
		push_error("l1_runtime_probe:privacy_reseed_timeout")
		get_tree().quit(1)
		return

	var environment_node := main_demo.get_node_or_null("EnvironmentStateNode")
	if environment_node == null or not environment_node.has_method("apply_environment_shift"):
		push_error("l1_runtime_probe:missing_environment_state_node")
		get_tree().quit(1)
		return

	environment_node.apply_environment_shift("alerted")
	await get_tree().process_frame
	await get_tree().process_frame
	environment_node.apply_environment_shift("stable")
	await get_tree().process_frame
	await get_tree().process_frame
	environment_node.apply_environment_shift("alerted")

	var environment_cycle_ok := await _wait_for_environment_alerts(2, 5000)
	if not environment_cycle_ok:
		print("l1_runtime_probe:environment_alert_count_before_timeout=%s" % _environment_alert_count)
		push_error("l1_runtime_probe:environment_cycle_timeout")
		get_tree().quit(1)
		return

	print("l1_runtime_probe:disconnect_count=%s" % _disconnect_count)
	print("l1_runtime_probe:zone_entry_count=%s" % _zone_entry_count)
	print("l1_runtime_probe:environment_alert_count=%s" % _environment_alert_count)
	print("l1_runtime_probe:privacy_local_count=%s" % _privacy_local_count)
	get_tree().quit(0)


func _on_debug_event_logged(message: String) -> void:
	if message == "phase0_spatial_access_fact:actor_entered_zone:zone_focus":
		_zone_entry_count += 1
	if message == "phase0_spatial_access_fact:privacy_boundary_changed:local":
		_privacy_local_count += 1
	if message == "phase0_visual_fact:light_level_drop:env_lamp":
		_environment_alert_count += 1


func _on_backend_connected(_url: String) -> void:
	_backend_connected = true


func _on_backend_disconnected(_code: int) -> void:
	_disconnect_count += 1


func _wait_for_zone_entries(target_count: int, timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		if _zone_entry_count >= target_count:
			return true
		await get_tree().process_frame
	return false


func _wait_for_backend_connected(timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		if _backend_connected:
			return true
		await get_tree().process_frame
	return false


func _wait_for_disconnect(target_count: int, timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		if _disconnect_count >= target_count:
			return true
		await get_tree().process_frame
	return false


func _wait_for_environment_alerts(target_count: int, timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		if _environment_alert_count >= target_count:
			return true
		await get_tree().process_frame
	return false


func _wait_for_privacy_local(target_count: int, timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		if _privacy_local_count >= target_count:
			return true
		await get_tree().process_frame
	return false
