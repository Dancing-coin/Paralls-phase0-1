extends CanvasLayer

@onready var label: RichTextLabel = RichTextLabel.new()


func _ready() -> void:
	add_child(label)
	label.position = Vector2(760, 48)
	label.size = Vector2(560, 280)
	var state := _get_state()
	if state and state.has_signal("observatory_state_changed"):
		state.observatory_state_changed.connect(_refresh)
	_refresh()


func _refresh() -> void:
	var state := _get_state()
	if state == null:
		return
	var observatory_enabled: Variant = state.get("observatory_enabled")
	var director_mode: Variant = state.get("director_mode")
	visible = observatory_enabled == true and director_mode == true
	var siming_board := get_node_or_null("../SimingDirectorBoard")
	var siming_lines: Array[String] = []
	if siming_board and siming_board.has_method("_build_director_rows"):
		siming_lines = siming_board._build_director_rows(state.call("get_latest_siming_state"))
	label.text = "\n\n".join(
		[
			_build_cast_board(state),
			_build_scene_state_board(state),
			_build_world_board(state),
			"司命导演席\n%s" % " | ".join(siming_lines),
		]
	)


func _get_state() -> Node:
	return get_node_or_null("../CharacterDirectorState")


func _build_cast_board(state: Node) -> String:
	var lines := ["演员总览"]
	var latest_actor_states: Dictionary = state.call("get_visible_actor_states")
	if latest_actor_states.is_empty():
		lines.append("还没有任何角色状态。先让角色发生一次对话或交互。")
		return "\n".join(lines)
	for actor_id in latest_actor_states.keys():
		var payload: Dictionary = latest_actor_states[actor_id]
		lines.append(
			"%s | 想做=%s | 盯着=%s | 状态=%s | 原因=%s | 世界结果=%s | 司命影响=%s" % [
				str(actor_id),
				str(payload.get("current_intent", "") or ""),
				str(payload.get("focus_target", "") or ""),
				str(payload.get("state_label", "") or ""),
				str(payload.get("why_now_summary", "") or ""),
				str(payload.get("latest_outcome_summary", "") or ""),
				str(payload.get("latest_siming_summary", "") or ""),
			]
		)
	return "\n".join(lines)


func _build_scene_state_board(state: Node) -> String:
	var beat_summaries: Array[String] = []
	var beats: Array[Dictionary] = state.call("get_recent_script_beats")
	for beat in beats.slice(max(beats.size() - 2, 0), beats.size()):
		beat_summaries.append(str(beat.get("dramatic_summary", "") or ""))
	var script_mode_enabled: Variant = state.get("script_mode")
	var freeze_mode_enabled: Variant = state.get("freeze_mode")
	var script_mode_label := "剧本回放已开" if script_mode_enabled == true else "剧本回放未开"
	var freeze_mode_label := "当前已冻结" if freeze_mode_enabled == true else "当前是实时刷新"
	return "\n".join(
		[
			"现场状态",
			"当前观察角色：%s" % str(state.get("selected_actor_id")),
			"当前模式：%s；%s" % [script_mode_label, freeze_mode_label],
			"最近节拍数量：%s" % str(beats.size()),
			"最近两条戏：%s" % (" || ".join(beat_summaries) if not beat_summaries.is_empty() else "还没有形成戏剧节拍。"),
		]
	)


func _build_world_board(state: Node) -> String:
	var lines := ["世界结算 / 约束结果"]
	var recent_world_outcomes: Array[Dictionary] = state.call("get_recent_world_outcomes")
	if recent_world_outcomes.is_empty():
		lines.append("世界这边还没给出结果。先做一次成功交互或失败交互。")
		return "\n".join(lines)
	for outcome in recent_world_outcomes.slice(max(recent_world_outcomes.size() - 4, 0), recent_world_outcomes.size()):
		lines.append(
			"%s -> %s | 卡住原因=%s | 世界变化=%s | 戏剧后果=%s" % [
				str(outcome.get("request_type", "") or ""),
				str(outcome.get("settlement_status", "") or ""),
				str(outcome.get("constraint_summary", "") or ""),
				str(outcome.get("world_change_summary", "") or ""),
				str(outcome.get("dramatic_consequence_summary", "") or ""),
			]
		)
	return "\n".join(lines)
