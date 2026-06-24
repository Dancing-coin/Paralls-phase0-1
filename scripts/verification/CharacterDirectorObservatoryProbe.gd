extends Node

var _backend_connected := false

const STATE_PAYLOADS_OK_MARKER := "character_director_observatory_probe:state_payloads_ok=true"
const PANELS_POPULATED_OK_MARKER := "character_director_observatory_probe:panels_populated=true"
const FREEZE_ROUNDTRIP_OK_MARKER := "character_director_observatory_probe:freeze_roundtrip_ok=true"
const ACTOR_PANEL_POPULATED_OK_MARKER := "character_director_observatory_probe:actor_panel_populated=true"
const DIRECTOR_CAST_WORLD_SIMING_OK_MARKER := "character_director_observatory_probe:director_cast_world_siming_populated=true"
const TIMELINE_MULTI_ROLE_OK_MARKER := "character_director_observatory_probe:timeline_multi_role_populated=true"
const LEDGER_PAIRWISE_OK_MARKER := "character_director_observatory_probe:ledger_pairwise_populated=true"
const SELECTED_ACTOR_SIMING_SUMMARY_OK_MARKER := "character_director_observatory_probe:selected_actor_siming_summary_populated=true"
const BOTTOM_STRIP_SIMING_OK_MARKER := "character_director_observatory_probe:bottom_strip_siming_populated=true"
const TIMELINE_SIMING_OK_MARKER := "character_director_observatory_probe:timeline_siming_populated=true"
const LEDGER_SIMING_PRESSURE_OK_MARKER := "character_director_observatory_probe:ledger_siming_pressure_populated=true"


func _string_or_empty(value: Variant) -> String:
	if value == null:
		return ""
	if value is String:
		return value
	return str(value)


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
	var early_bottom_strip_siming_populated: bool = await _wait_for_bottom_strip_siming(state, observatory_root, 1500)
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
	var timeline_beats: Array[Dictionary] = state.call("get_recent_script_beats")
	var actor_panel_populated := false
	var selected_actor_siming_summary_populated := false
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
			var actor_panel_text := _string_or_empty(actor_label.text)
			var selected_actor_siming_summary := _string_or_empty(
				state.call("get_selected_actor_latest_siming_summary")
			)
			var actor_panel_has_structure := (
				not selected_payload.is_empty()
				and actor_panel_text.find("看到了什么") >= 0
				and actor_panel_text.find("怎么理解") >= 0
				and actor_panel_text.find("准备做什么") >= 0
				and actor_panel_text.find("世界 / 司命反馈") >= 0
				and actor_panel_text.find("还没收到这个角色的观测数据") == -1
			)
			if actor_panel_has_structure:
				actor_panel_populated = true
			var rendered_feedback_summary := selected_actor_siming_summary
			if actor_panel.has_method("_resolve_feedback_summary") and not selected_payload.is_empty():
				rendered_feedback_summary = _string_or_empty(
					actor_panel.call("_resolve_feedback_summary", selected_payload)
				)
			if (
				not selected_payload.is_empty()
				and not selected_actor_siming_summary.is_empty()
				and not rendered_feedback_summary.is_empty()
				and rendered_feedback_summary.find(selected_actor_siming_summary) >= 0
			):
				selected_actor_siming_summary_populated = true
			if actor_panel_populated and selected_actor_siming_summary_populated:
				break
	var director_cast_world_siming_populated: bool = (
		monitor_label != null
		and str(monitor_label.text).find("演员总览") >= 0
		and str(monitor_label.text).find("现场状态") >= 0
		and str(monitor_label.text).find("世界结算 / 约束结果") >= 0
		and str(monitor_label.text).find("司命导演席") >= 0
		and str(monitor_label.text).find("当前观察角色：") >= 0
		and str(monitor_label.text).find("司命影响=") >= 0
		and str(monitor_label.text).find("司命为什么这么做") >= 0
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
	var rich_timeline_beat := _find_latest_timeline_beat_with_siming(timeline_beats)
	var rich_timeline_beat_id := _string_or_empty(rich_timeline_beat.get("beat_id", ""))
	if not rich_timeline_beat_id.is_empty():
		timeline.set("expanded_beat_id", rich_timeline_beat_id)
		if timeline.has_method("_refresh"):
			timeline.call("_refresh")
		await get_tree().process_frame
		await get_tree().process_frame
	var timeline_siming_populated: bool = (
		timeline_label != null
		and str(timeline_label.text).find("司命侧摘要=") >= 0
		and str(timeline_label.text).find("司命侧摘要=[]") == -1
	)
	if not timeline_siming_populated and not rich_timeline_beat.is_empty() and timeline.has_method("_build_expanded_payload_lines"):
		timeline_siming_populated = _timeline_lines_include_siming(
			timeline.call("_build_expanded_payload_lines", rich_timeline_beat)
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
	var dialogue_pairs: Array[Dictionary] = state.call("get_dialogue_pair_entries")
	var rich_dialogue_pair := _find_dialogue_pair_with_siming(dialogue_pairs)
	var rich_dialogue_pair_key := _string_or_empty(rich_dialogue_pair.get("pair_key", ""))
	if not rich_dialogue_pair_key.is_empty():
		ledger.set("selected_pair_key", rich_dialogue_pair_key)
		if ledger.has_method("_refresh"):
			ledger.call("_refresh")
		await get_tree().process_frame
		await get_tree().process_frame
	var ledger_siming_pressure_populated: bool = (
		ledger_label != null
		and str(ledger_label.text).find("司命压力上下文：") >= 0
		and str(ledger_label.text).find("司命压力上下文：暂无") == -1
	)
	if not ledger_siming_pressure_populated and ledger.has_method("_resolve_siming_pressure_context") and not rich_dialogue_pair.is_empty():
		var resolved_context := _string_or_empty(
			ledger.call("_resolve_siming_pressure_context", rich_dialogue_pair)
		)
		ledger_siming_pressure_populated = not resolved_context.is_empty() and resolved_context != "暂无"
	var current_timeline_beats: Array[Dictionary] = state.call("get_recent_script_beats")
	var current_siming_events: Array[Dictionary] = state.call("get_recent_siming_events")
	var current_runtime_siming_summary := _find_latest_runtime_siming_summary(current_timeline_beats, current_siming_events)
	var current_bottom_strip_entries: Array[Dictionary] = state.call("get_latest_bottom_strip_entries")
	var state_bottom_strip_siming_populated := _bottom_strip_entries_include_siming(current_bottom_strip_entries)
	var live_bottom_strip_siming_populated := false
	var world_trace_has_formatter := world_trace != null and world_trace.has_method("_format_bottom_strip_row")
	var formatter_diagnostic_row := ""
	if world_trace != null and world_trace.has_method("_refresh"):
		world_trace.call("_refresh")
		await get_tree().process_frame
		await get_tree().process_frame
		live_bottom_strip_siming_populated = (
			world_trace_label != null
			and str(world_trace_label.text).find("[司命]") >= 0
		)
		if world_trace_has_formatter:
			formatter_diagnostic_row = _format_latest_bottom_strip_siming_entry(world_trace, current_bottom_strip_entries)
	var bottom_strip_populated: bool = (
		world_trace_label != null
		and str(world_trace_label.text).find("最近 3 条") >= 0
		and (
			str(world_trace_label.text).find("[世界]") >= 0
			or str(world_trace_label.text).find("[司命]") >= 0
			or str(world_trace_label.text).find("[节拍]") >= 0
		)
	)
	var bottom_strip_siming_populated: bool = (
		early_bottom_strip_siming_populated
		or live_bottom_strip_siming_populated
		or state_bottom_strip_siming_populated
		or (
			world_trace_label != null
			and str(world_trace_label.text).find("[司命]") >= 0
		)
	)
	var panels_populated: bool = (
		actor_panel_populated
		and director_cast_world_siming_populated
		and timeline_multi_role_populated
		and ledger_pairwise_populated
	)
	print("character_director_observatory_probe:bottom_strip_populated=%s" % ("true" if bottom_strip_populated else "false"))
	print("character_director_observatory_probe:diag_runtime_siming_summary_nonempty=%s" % ("true" if not current_runtime_siming_summary.is_empty() else "false"))
	print("character_director_observatory_probe:diag_world_trace_exists=%s" % ("true" if world_trace != null else "false"))
	print("character_director_observatory_probe:diag_world_trace_has_formatter=%s" % ("true" if world_trace_has_formatter else "false"))
	print("character_director_observatory_probe:diag_formatter_row_contains_siming=%s" % ("true" if formatter_diagnostic_row.find("[司命]") >= 0 else "false"))
	if not formatter_diagnostic_row.is_empty():
		print("character_director_observatory_probe:diag_bottom_strip_formatter_row=%s" % formatter_diagnostic_row)
	print("character_director_observatory_probe:diag_state_bottom_strip_siming=%s" % ("true" if state_bottom_strip_siming_populated else "false"))
	state.set_freeze_mode(true)
	var frozen_before: int = state.get_recent_script_beats().size()
	await get_tree().create_timer(0.2).timeout
	state.set_freeze_mode(false)
	await get_tree().create_timer(0.2).timeout
	var freeze_roundtrip_ok: bool = frozen_before >= 0 and not state.freeze_mode
	_print_bool_marker(STATE_PAYLOADS_OK_MARKER, state_payloads_ok)
	_print_bool_marker(PANELS_POPULATED_OK_MARKER, panels_populated)
	_print_bool_marker(FREEZE_ROUNDTRIP_OK_MARKER, freeze_roundtrip_ok)
	_print_bool_marker(ACTOR_PANEL_POPULATED_OK_MARKER, actor_panel_populated)
	_print_bool_marker(DIRECTOR_CAST_WORLD_SIMING_OK_MARKER, director_cast_world_siming_populated)
	_print_bool_marker(TIMELINE_MULTI_ROLE_OK_MARKER, timeline_multi_role_populated)
	_print_bool_marker(LEDGER_PAIRWISE_OK_MARKER, ledger_pairwise_populated)
	_print_bool_marker(SELECTED_ACTOR_SIMING_SUMMARY_OK_MARKER, selected_actor_siming_summary_populated)
	_print_bool_marker(BOTTOM_STRIP_SIMING_OK_MARKER, bottom_strip_siming_populated)
	_print_bool_marker(TIMELINE_SIMING_OK_MARKER, timeline_siming_populated)
	_print_bool_marker(LEDGER_SIMING_PRESSURE_OK_MARKER, ledger_siming_pressure_populated)
	get_tree().quit(
		0
		if state_payloads_ok
		and panels_populated
		and freeze_roundtrip_ok
		and actor_panel_populated
		and director_cast_world_siming_populated
		and timeline_multi_role_populated
		and ledger_pairwise_populated
		and selected_actor_siming_summary_populated
		and bottom_strip_siming_populated
		and timeline_siming_populated
		and ledger_siming_pressure_populated
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


func _wait_for_bottom_strip_siming(state: Node, observatory_root: Node, timeout_ms: int) -> bool:
	var world_trace := observatory_root.get_node_or_null("WorldOutcomeTrace") if observatory_root else null
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		if world_trace != null and world_trace.has_method("_refresh"):
			world_trace.call("_refresh")
		await get_tree().process_frame
		await get_tree().process_frame
		var world_trace_label := world_trace.get_child(0) if world_trace and world_trace.get_child_count() > 0 else null
		if world_trace_label != null and str(world_trace_label.text).find("[司命]") >= 0:
			return true
		var bottom_strip_entries: Array[Dictionary] = state.call("get_latest_bottom_strip_entries")
		if _bottom_strip_entries_include_siming(bottom_strip_entries):
			return true
		if world_trace != null and world_trace.has_method("_format_bottom_strip_row"):
			var formatted_siming_row := _format_latest_bottom_strip_siming_entry(world_trace, bottom_strip_entries)
			if not formatted_siming_row.is_empty():
				print("character_director_observatory_probe:diag_bottom_strip_formatter_row=%s" % formatted_siming_row)
		await get_tree().create_timer(0.1).timeout
	return false


func _print_bool_marker(marker: String, value: bool) -> void:
	if value:
		print(marker)
		return
	if marker.ends_with("=true"):
		print("%s=false" % marker.left(marker.length() - 5))
		return
	print("%s=false" % marker)


func _find_latest_timeline_beat_with_siming(beats: Array[Dictionary]) -> Dictionary:
	var latest_beat := {}
	for beat in beats:
		var siming_rows: Array = beat.get("siming_summaries", [])
		if siming_rows is Array and not siming_rows.is_empty():
			latest_beat = beat
	return latest_beat


func _find_latest_runtime_siming_summary(beats: Array[Dictionary], events: Array[Dictionary]) -> String:
	var summary := ""
	var latest_beat := _find_latest_timeline_beat_with_siming(beats)
	if not latest_beat.is_empty():
		var siming_rows: Array = latest_beat.get("siming_summaries", [])
		for row in siming_rows:
			if row is Dictionary:
				var row_summary := _string_or_empty((row as Dictionary).get("summary", ""))
				if not row_summary.is_empty():
					summary = row_summary
	if not summary.is_empty():
		return summary
	for event in events:
		var event_summary := _string_or_empty(event.get("summary", ""))
		if not event_summary.is_empty():
			summary = event_summary
	return summary


func _timeline_lines_include_siming(lines_value: Variant) -> bool:
	if not (lines_value is Array):
		return false
	for line_value in lines_value:
		var line := str(line_value)
		if line.find("司命侧摘要=") >= 0 and line != "司命侧摘要=[]":
			return true
	return false


func _find_dialogue_pair_with_siming(rows: Array[Dictionary]) -> Dictionary:
	for row in rows:
		var siming_context := _string_or_empty(row.get("siming_pressure_context", ""))
		if siming_context.is_empty():
			siming_context = _string_or_empty(row.get("siming_context", ""))
		if siming_context.is_empty():
			siming_context = _string_or_empty(row.get("siming_summary", ""))
		if not siming_context.is_empty():
			return row
	return {}


func _bottom_strip_entries_include_siming(rows: Array[Dictionary]) -> bool:
	for row in rows:
		if _string_or_empty(row.get("type", "")) != "司命":
			continue
		if not _string_or_empty(row.get("summary", "")).is_empty():
			return true
	return false


func _format_latest_bottom_strip_siming_entry(world_trace: Node, rows: Array[Dictionary]) -> String:
	if not world_trace.has_method("_format_bottom_strip_row"):
		return ""
	for row in rows:
		if _string_or_empty(row.get("type", "")) != "司命":
			continue
		if _string_or_empty(row.get("summary", "")).is_empty():
			continue
		return _string_or_empty(world_trace.call("_format_bottom_strip_row", row))
	return ""
