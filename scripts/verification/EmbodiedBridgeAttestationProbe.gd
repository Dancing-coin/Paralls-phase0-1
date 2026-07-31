extends Node


func _ready() -> void:
	call_deferred("_run_probe")


func _run_probe() -> void:
	var bus := get_node_or_null("/root/LocalPresentationBus")
	var bridge := get_node_or_null("/root/BackendBridge")
	var required_bus_signals := [
		"embodied_controller_bound_received",
		"embodied_action_request_received",
		"embodied_settlement_result_received",
		"embodied_cancel_directive_received",
		"embodied_resync_projection_received",
		"embodied_phase_event_emitted",
		"embodied_local_outcome_emitted",
		"embodied_resync_request_emitted",
	]
	var signal_status := {}
	for signal_name: String in required_bus_signals:
		signal_status[signal_name] = bus != null and bus.has_signal(signal_name)
	var bridge_ok := bridge != null and bridge.has_method("send_envelope") and bridge.has_method("is_backend_open")
	var source := FileAccess.get_file_as_string("res://scripts/autoload/BackendBridge.gd")
	var embodied_routes := (
		source.contains("\"embodied_phase_event\"")
		and source.contains("\"embodied_local_outcome\"")
		and source.contains("\"embodied_action_request\"")
		and source.contains("func _on_embodied_phase_event_emitted")
	)
	var embodied_section := source.substr(source.find("func _on_embodied_phase_event_emitted"))
	var legacy_status_reused := embodied_section.contains("character_actor_status")
	var ok: bool = bridge_ok and embodied_routes and not legacy_status_reused
	for value: Variant in signal_status.values():
		ok = ok and bool(value)
	var report := {
		"status": "godot-runtime-embodied-bridge-attestation-verified" if ok else "godot-runtime-embodied-bridge-attestation-failed",
		"bridge_autoload_loaded": bridge != null,
		"bus_autoload_loaded": bus != null,
		"bus_signals": signal_status,
		"bridge_has_runtime_methods": bridge_ok,
		"bridge_embodied_routes": embodied_routes,
		"legacy_character_actor_status_reused": legacy_status_reused,
	}
	var report_path := _write_json(".harness/verification/embodied-bridge-attestation-godot-runtime.json", report)
	print("embodied_bridge_attestation_probe:artifact=%s" % report_path)
	print("embodied_bridge_attestation_probe:verified=%s" % str(ok).to_lower())
	get_tree().quit(0 if ok else 1)


func _write_json(relative_path: String, payload: Dictionary) -> String:
	var path := ProjectSettings.globalize_path("res://" + relative_path)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return ""
	file.store_string(JSON.stringify(payload, "\t"))
	file.close()
	return path
