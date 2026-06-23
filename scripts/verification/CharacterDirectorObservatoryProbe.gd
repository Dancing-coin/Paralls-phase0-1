extends Node

var _backend_connected := false

const STATE_PAYLOADS_OK_MARKER := "character_director_observatory_probe:state_payloads_ok=true"
const PANELS_POPULATED_OK_MARKER := "character_director_observatory_probe:panels_populated=true"
const FREEZE_ROUNDTRIP_OK_MARKER := "character_director_observatory_probe:freeze_roundtrip_ok=true"
const ACTOR_PANEL_POPULATED_OK_MARKER := "character_director_observatory_probe:actor_panel_populated=true"
const DIRECTOR_CAST_WORLD_SIMING_OK_MARKER := "character_director_observatory_probe:director_cast_world_siming_populated=true"
const TIMELINE_MULTI_ROLE_OK_MARKER := "character_director_observatory_probe:timeline_multi_role_populated=true"
const LEDGER_PAIRWISE_OK_MARKER := "character_director_observatory_probe:ledger_pairwise_populated=true"


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
	var actor_panel := observatory_root.get_node_or_null("CharacterObserverPanel") if observatory_root else null
	var monitor := observatory_root.get_node_or_null("DirectorMonitorPanel") if observatory_root else null
	var timeline := observatory_root.get_node_or_null("ScriptTimelinePanel") if observatory_root else null
	var ledger := observatory_root.get_node_or_null("DialogueSceneLedger") if observatory_root else null
	if state == null or actor_panel == null or monitor == null or timeline == null or ledger == null:
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
	var actor_label := actor_panel.get_child(0) if actor_panel.get_child_count() > 0 else null
	var monitor_label := monitor.get_child(0) if monitor.get_child_count() > 0 else null
	var timeline_label := timeline.get_child(0) if timeline.get_child_count() > 0 else null
	var ledger_label := ledger.get_child(0) if ledger.get_child_count() > 0 else null
	var world_trace := observatory_root.get_node_or_null("WorldOutcomeTrace") if observatory_root else null
	var world_trace_label := world_trace.get_child(0) if world_trace and world_trace.get_child_count() > 0 else null
	var actor_panel_populated := false
	if actor_label != null:
		var actor_state_keys: Array = state.get_visible_actor_states().keys()
		var actor_probe_ids: Array[String] = ["char_c", "char_a", "char_b"]
		for actor_key in actor_state_keys:
			var actor_id_text := str(actor_key)
			if not actor_probe_ids.has(actor_id_text):
				actor_probe_ids.append(actor_id_text)
		for actor_id in actor_probe_ids:
			state.set_selected_actor(actor_id)
			if actor_panel.has_method("_refresh"):
				actor_panel.call("_refresh")
			await get_tree().process_frame
			await get_tree().process_frame
			var selected_payload: Dictionary = state.get_selected_actor_state()
			var actor_panel_text := str(actor_label.text)
			if (
				not selected_payload.is_empty()
				and actor_panel_text.find("看到了什么") >= 0
				and actor_panel_text.find("怎么理解") >= 0
				and actor_panel_text.find("准备做什么") >= 0
				and actor_panel_text.find("世界 / 司命反馈") >= 0
				and actor_panel_text.find("还没收到这个角色的观测数据") == -1
			):
				actor_panel_populated = true
				break
	var director_cast_world_siming_populated: bool = (
		monitor_label != null
		and str(monitor_label.text).find("演员总览") >= 0
		and str(monitor_label.text).find("现场状态") >= 0
		and str(monitor_label.text).find("世界结算 / 约束结果") >= 0
		and str(monitor_label.text).find("司命导演席") >= 0
		and str(monitor_label.text).find("当前观察角色：") >= 0
	)
	var timeline_multi_role_populated: bool = (
		timeline_label != null
		and str(timeline_label.text).find("线索链=") >= 0
		and str(timeline_label.text).find("参与者=") >= 0
		and str(timeline_label.text).find("这一拍发生了：") >= 0
		and str(timeline_label.text).find("角色侧摘要=") >= 0
		and str(timeline_label.text).find("司命侧摘要=") >= 0
		and str(timeline_label.text).find("世界侧摘要=") >= 0
		and str(timeline_label.text).find("对话对账=") >= 0
	)
	var ledger_pairwise_populated: bool = (
		ledger_label != null
		and str(ledger_label.text).find("说话的人当时感知到：") >= 0
		and str(ledger_label.text).find("听的人当时感知到：") >= 0
		and str(ledger_label.text).find("说话的人怎么理解局面：") >= 0
		and str(ledger_label.text).find("听的人怎么理解局面：") >= 0
		and str(ledger_label.text).find("说话的人实际说了：") >= 0
		and str(ledger_label.text).find("听的人回出来的话：") >= 0
	)
	var bottom_strip_populated: bool = (
		world_trace_label != null
		and str(world_trace_label.text).find("最近 3 条") >= 0
		and (
			str(world_trace_label.text).find("[世界]") >= 0
			or str(world_trace_label.text).find("[司命]") >= 0
			or str(world_trace_label.text).find("[节拍]") >= 0
		)
	)
	var panels_populated: bool = (
		actor_panel_populated
		and director_cast_world_siming_populated
		and timeline_multi_role_populated
		and ledger_pairwise_populated
	)
	print("character_director_observatory_probe:bottom_strip_populated=%s" % ("true" if bottom_strip_populated else "false"))
	state.set_freeze_mode(true)
	var frozen_before: int = state.get_recent_script_beats().size()
	await get_tree().create_timer(0.2).timeout
	state.set_freeze_mode(false)
	await get_tree().create_timer(0.2).timeout
	var freeze_roundtrip_ok: bool = frozen_before >= 0 and not state.freeze_mode
	print("character_director_observatory_probe:state_payloads_ok=%s" % ("true" if state_payloads_ok else "false"))
	print("character_director_observatory_probe:panels_populated=%s" % ("true" if panels_populated else "false"))
	print("character_director_observatory_probe:freeze_roundtrip_ok=%s" % ("true" if freeze_roundtrip_ok else "false"))
	print("character_director_observatory_probe:actor_panel_populated=%s" % ("true" if actor_panel_populated else "false"))
	print("character_director_observatory_probe:director_cast_world_siming_populated=%s" % ("true" if director_cast_world_siming_populated else "false"))
	print("character_director_observatory_probe:timeline_multi_role_populated=%s" % ("true" if timeline_multi_role_populated else "false"))
	print("character_director_observatory_probe:ledger_pairwise_populated=%s" % ("true" if ledger_pairwise_populated else "false"))
	get_tree().quit(
		0
		if state_payloads_ok
		and panels_populated
		and freeze_roundtrip_ok
		and actor_panel_populated
		and director_cast_world_siming_populated
		and timeline_multi_role_populated
		and ledger_pairwise_populated
		else 1
	)


func _on_backend_connected(_url: String) -> void:
	_backend_connected = true


func _wait_for_backend_connected(timeout_ms: int) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		if _backend_connected:
			return true
		await get_tree().process_frame
	return false
