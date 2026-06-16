extends Node

@export var backend_url := "ws://127.0.0.1:8000/ws"

var _mode := "main"
var _run_id := ""
var _room_id := ""
var _scene_id := ""
var _zone_id := ""
var _ack_counts_by_route: Dictionary = {}
var _expected_ack_counts_by_route: Dictionary = {}
var _runtime_delta_count := 0
var _candidate_count := 0
var _siming_count := 0


func _ready() -> void:
	var env_mode := OS.get_environment("PHASE1_SLICE_PROBE_MODE")
	if env_mode == "focus":
		_mode = "focus"
	_run_id = OS.get_environment("PHASE1_SLICE_PROBE_RUN_ID")
	if _run_id == "":
		_run_id = "phase1-slice-%s-%s" % [_mode, Time.get_ticks_msec()]
	_room_id = "room_%s" % _run_id
	_scene_id = "scene_%s" % _run_id
	_zone_id = "zone_%s" % _run_id
	call_deferred("_run_probe")


func _run_probe() -> void:
	var bus := get_node_or_null("/root/LocalPresentationBus")
	if bus == null:
		push_error("phase1_slice_runtime_probe:missing_local_presentation_bus")
		get_tree().quit(1)
		return

	if bus.has_signal("backend_ack_received"):
		bus.backend_ack_received.connect(_on_backend_ack_received)
	if bus.has_signal("character_runtime_state_delta_received"):
		bus.character_runtime_state_delta_received.connect(_on_character_runtime_state_delta_received)
	if bus.has_signal("conversation_candidate_received"):
		bus.conversation_candidate_received.connect(_on_conversation_candidate_received)
	if bus.has_signal("siming_output_received"):
		bus.siming_output_received.connect(_on_siming_output_received)

	var bridge := get_node_or_null("/root/BackendBridge")
	if bridge == null or not bridge.has_method("connect_to_backend"):
		push_error("phase1_slice_runtime_probe:missing_backend_bridge")
		get_tree().quit(1)
		return

	var err: int = bridge.connect_to_backend(backend_url)
	if err != OK:
		push_error("phase1_slice_runtime_probe:connect_failed:%s" % err)
		get_tree().quit(1)
		return

	if not await _wait_for_backend_open(5000):
		push_error("phase1_slice_runtime_probe:backend_connect_timeout")
		get_tree().quit(1)
		return

	_configure_fact_context()

	if _mode == "focus":
		_expected_ack_counts_by_route = {"authority_visual_fact": 1}
		if not _emit_focus_facts():
			push_error("phase1_slice_runtime_probe:focus_emit_failed")
			get_tree().quit(1)
			return
	else:
		_expected_ack_counts_by_route = {
			"authority_visual_fact": 4,
			"authority_auditory_fact": 3,
			"authority_role_state_fact": 1,
			"authority_physiology_fact": 1,
			"authority_tactile_fact": 1,
			"authority_thermal_fact": 1,
			"authority_olfactory_fact": 1,
		}
		if not _emit_main_facts():
			push_error("phase1_slice_runtime_probe:main_emit_failed")
			get_tree().quit(1)
			return

	if not await _wait_for_backend_observations(10000):
		push_error(
			"phase1_slice_runtime_probe:observation_timeout:acks=%s deltas=%s candidates=%s siming=%s run=%s" % [
				JSON.stringify(_ack_counts_by_route),
				_runtime_delta_count,
				_candidate_count,
				_siming_count,
				_run_id,
			]
		)
		get_tree().quit(1)
		return

	print(
		"phase1_slice_runtime_probe:%s:acks=%s deltas=%s candidates=%s siming=%s run=%s" % [
			_mode,
			JSON.stringify(_ack_counts_by_route),
			_runtime_delta_count,
			_candidate_count,
			_siming_count,
			_run_id,
		]
	)
	get_tree().quit(0)


func _configure_fact_context() -> void:
	$VisualFactEmitter.actor_id = "char_c"
	$VisualFactEmitter.room_id = _room_id
	$VisualFactEmitter.scene_id = _scene_id
	$VisualFactEmitter.zone_id = _zone_id

	for emitter in [
		$VisualFactEmitter/AuditoryFactEmitter,
		$VisualFactEmitter/RoleStateFactEmitter,
		$VisualFactEmitter/PhysiologyStateFactEmitter,
		$VisualFactEmitter/TactileFactEmitter,
		$VisualFactEmitter/ThermalFactEmitter,
		$VisualFactEmitter/OlfactoryFactEmitter,
	]:
		emitter.room_id = _room_id
		emitter.scene_id = _scene_id
		emitter.zone_id = _zone_id

	for emitter in [
		$VisualFactEmitter/RoleStateFactEmitter,
		$VisualFactEmitter/PhysiologyStateFactEmitter,
		$VisualFactEmitter/TactileFactEmitter,
		$VisualFactEmitter/ThermalFactEmitter,
		$VisualFactEmitter/OlfactoryFactEmitter,
	]:
		emitter.actor_id = "char_c"


func _emit_main_facts() -> bool:
	return (
		$VisualFactEmitter/CharacterVisualFactEmitter.emit_fixed_gaze_on_target("", "obj_letter")
		and $VisualFactEmitter/CharacterVisualFactEmitter.emit_actor_near_object("obj_letter")
		and $VisualFactEmitter/EnvironmentVisualFactEmitter.emit_environment_state_transition("env_lamp", "stable", "alerted")
		and $VisualFactEmitter/EvidenceProjectionEmitter.emit_visual_evidence_projection("obj_letter", "")
		and $VisualFactEmitter/AuditoryFactEmitter.emit_speaker_active("char_a", "char_c")
		and $VisualFactEmitter/AuditoryFactEmitter.emit_auditory_reachability_changed("char_a", "char_c", "clear")
		and $VisualFactEmitter/AuditoryFactEmitter.emit_ambient_noise_changed("char_a", "quiet")
		and $VisualFactEmitter/RoleStateFactEmitter.emit_role_state_transition("observing")
		and $VisualFactEmitter/PhysiologyStateFactEmitter.emit_breathing_strain_fact("elevated")
		and $VisualFactEmitter/TactileFactEmitter.emit_contact_fact("", "obj_letter", "light")
		and $VisualFactEmitter/ThermalFactEmitter.emit_thermal_proximity_fact("env_lamp", "warm")
		and $VisualFactEmitter/OlfactoryFactEmitter.emit_odor_state_fact("env_lamp", "noticeable")
	)


func _emit_focus_facts() -> bool:
	return $VisualFactEmitter/CharacterVisualFactEmitter.emit_fixed_gaze_on_target("char_b", "")


func _on_backend_ack_received(payload: Dictionary) -> void:
	var route := str(payload.get("route", ""))
	if route != "":
		_ack_counts_by_route[route] = int(_ack_counts_by_route.get(route, 0)) + 1
	_bus_log("phase0_ack:%s" % JSON.stringify(payload))


func _on_character_runtime_state_delta_received(payload: Dictionary) -> void:
	if (
		str(payload.get("current_attention_source", "")) == "visual_fact"
		and _payload_matches_run(payload)
		and _matches_mode_target(payload, "current_focus_target")
	):
		_runtime_delta_count += 1


func _on_conversation_candidate_received(payload: Dictionary) -> void:
	if _payload_matches_run(payload) and _candidate_matches_mode(payload):
		_candidate_count += 1


func _on_siming_output_received(payload: Dictionary) -> void:
	if str(payload.get("room_id", "")) == _room_id and _siming_output_matches_mode(payload):
		_siming_count += 1


func _payload_matches_run(payload: Dictionary) -> bool:
	return (
		str(payload.get("room_id", "")) == _room_id
		and str(payload.get("scene_id", "")) == _scene_id
		and str(payload.get("zone_id", "")) == _zone_id
	)


func _matches_mode_target(payload: Dictionary, key: String) -> bool:
	var value := str(payload.get(key, ""))
	if _mode == "focus":
		return value == "char_b"
	return value == "obj_letter" or value == "env_lamp"


func _candidate_matches_mode(payload: Dictionary) -> bool:
	if _mode == "focus":
		return _string_array_contains(payload.get("candidate_actor_ids", []), "char_b")
	return (
		_string_array_contains(payload.get("candidate_object_ids", []), "obj_letter")
		or _string_array_contains(payload.get("candidate_environment_ids", []), "env_lamp")
	)


func _siming_output_matches_mode(payload: Dictionary) -> bool:
	if _mode == "focus":
		return str(payload.get("target_actor_id", "")) == "char_b"
	return (
		str(payload.get("target_object_id", "")) == "obj_letter"
		or str(payload.get("target_environment_id", "")) == "env_lamp"
	)


func _string_array_contains(value: Variant, expected: String) -> bool:
	if not (value is Array):
		return false
	for entry in value:
		if str(entry) == expected:
			return true
	return false


func _wait_for_backend_open(timeout_ms: int) -> bool:
	var bridge := get_node_or_null("/root/BackendBridge")
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		if bridge != null and bridge.has_method("is_backend_open") and bridge.is_backend_open():
			return true
		await get_tree().process_frame
	return false


func _ack_routes_observed() -> bool:
	for route in _expected_ack_counts_by_route:
		if int(_ack_counts_by_route.get(route, 0)) < int(_expected_ack_counts_by_route[route]):
			return false
	return true


func _wait_for_backend_observations(timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		if (
			_ack_routes_observed()
			and _runtime_delta_count >= 1
			and _candidate_count >= 1
			and _siming_count >= 1
		):
			return true
		await get_tree().process_frame
	return false


func _bus_log(message: String) -> void:
	var bus := get_node_or_null("/root/LocalPresentationBus")
	if bus and bus.has_method("log_debug"):
		bus.log_debug(message)
