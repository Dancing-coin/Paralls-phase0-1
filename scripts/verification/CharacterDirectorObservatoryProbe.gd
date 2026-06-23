extends Node

var _backend_connected := false

const STATE_PAYLOADS_OK_MARKER := "character_director_observatory_probe:state_payloads_ok=true"
const PANELS_POPULATED_OK_MARKER := "character_director_observatory_probe:panels_populated=true"
const FREEZE_ROUNDTRIP_OK_MARKER := "character_director_observatory_probe:freeze_roundtrip_ok=true"


func _ready() -> void:
	call_deferred("_run_probe")


func _run_probe() -> void:
	var bus := get_node_or_null("/root/LocalPresentationBus")
	if bus == null:
		push_error("character_director_observatory_probe:missing_bus")
		get_tree().quit(1)
		return
	if bus.has_method("set_debug_logging_enabled"):
		bus.set_debug_logging_enabled(true)
	if bus.has_signal("backend_connected"):
		bus.backend_connected.connect(_on_backend_connected)
	var main_demo := get_node_or_null("MainDemo")
	if main_demo == null:
		push_error("character_director_observatory_probe:missing_main_demo")
		get_tree().quit(1)
		return
	var observatory_root := main_demo.get_node_or_null("ObservatoryRoot")
	var state := observatory_root.get_node_or_null("CharacterDirectorState") if observatory_root else null
	var monitor := observatory_root.get_node_or_null("DirectorMonitorPanel") if observatory_root else null
	var timeline := observatory_root.get_node_or_null("ScriptTimelinePanel") if observatory_root else null
	var ledger := observatory_root.get_node_or_null("DialogueSceneLedger") if observatory_root else null
	if state == null or monitor == null or timeline == null or ledger == null:
		push_error("character_director_observatory_probe:missing_observatory_nodes")
		get_tree().quit(1)
		return
	var connected_ok := await _wait_for_backend_connected(10000)
	if not connected_ok:
		push_error("character_director_observatory_probe:backend_connect_timeout")
		get_tree().quit(1)
		return
	state.set_observatory_enabled(true)
	state.set_director_mode(true)
	state.set_script_mode(true)
	var main_controller := main_demo.get_node_or_null(".")
	var actor_node := main_demo.get_node_or_null("CharacterA")
	var object_node := main_demo.get_node_or_null("InteractiveObject")
	if main_controller != null and main_controller.has_method("_force_focus_target") and actor_node != null:
		main_controller.call("_force_focus_target", actor_node)
	await get_tree().create_timer(0.2).timeout
	main_demo.call("submit_dialogue", "what did you see near the letter?")
	await get_tree().create_timer(0.8).timeout
	if main_controller != null and main_controller.has_method("_force_focus_target") and object_node != null:
		main_controller.call("_force_focus_target", object_node)
	await get_tree().create_timer(0.2).timeout
	if main_controller != null and main_controller.has_method("_emit_interaction_request"):
		main_controller.call("_emit_interaction_request", "obj_letter", "inspect")
	await get_tree().create_timer(1.2).timeout
	var state_payloads_ok: bool = (
		state.get_visible_actor_states().size() > 0
		and not state.get_latest_siming_state().is_empty()
		and state.get_recent_world_outcomes().size() > 0
		and state.get_recent_script_beats().size() > 0
	)
	var monitor_label := monitor.get_child(0) if monitor.get_child_count() > 0 else null
	var timeline_label := timeline.get_child(0) if timeline.get_child_count() > 0 else null
	var ledger_label := ledger.get_child(0) if ledger.get_child_count() > 0 else null
	var panels_populated: bool = (
		monitor_label != null and str(monitor_label.text).find("Cast Board") >= 0
		and timeline_label != null and str(timeline_label.text).find("|") >= 0
		and ledger_label != null and str(ledger_label.text).find("pair=") >= 0
	)
	state.set_freeze_mode(true)
	var frozen_before: int = state.get_recent_script_beats().size()
	await get_tree().create_timer(0.2).timeout
	state.set_freeze_mode(false)
	await get_tree().create_timer(0.2).timeout
	var freeze_roundtrip_ok: bool = frozen_before >= 0 and not state.freeze_mode
	print("character_director_observatory_probe:state_payloads_ok=%s" % ("true" if state_payloads_ok else "false"))
	print("character_director_observatory_probe:panels_populated=%s" % ("true" if panels_populated else "false"))
	print("character_director_observatory_probe:freeze_roundtrip_ok=%s" % ("true" if freeze_roundtrip_ok else "false"))
	get_tree().quit(0 if state_payloads_ok and panels_populated and freeze_roundtrip_ok else 1)


func _on_backend_connected(_url: String) -> void:
	_backend_connected = true


func _wait_for_backend_connected(timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		if _backend_connected:
			return true
		await get_tree().process_frame
	return false
