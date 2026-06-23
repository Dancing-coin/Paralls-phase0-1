extends Node2D

var attention_lines: Array[Dictionary] = []
var dialogue_lines: Array[Dictionary] = []
var action_intent_lines: Array[Dictionary] = []
var blocked_lines: Array[Dictionary] = []
var siming_influence_lines: Array[Dictionary] = []
var target_markers: Array[Dictionary] = []


func _ready() -> void:
	var state := _get_state()
	if state and state.has_signal("observatory_state_changed"):
		state.observatory_state_changed.connect(_refresh)
	_refresh()


func _refresh() -> void:
	var state := _get_state()
	if state == null:
		return
	var observatory_enabled: Variant = state.get("observatory_enabled")
	visible = observatory_enabled == true
	var payload: Dictionary = state.call("get_selected_actor_state")
	attention_lines = _build_attention_line_family(state)
	dialogue_lines = _build_dialogue_line_family(state)
	action_intent_lines = _build_action_intent_line_family(state)
	blocked_lines = _build_blocked_line_family(state)
	siming_influence_lines = _build_siming_line_family(state)
	target_markers = _build_target_markers(state, payload)
	queue_redraw()


func _draw() -> void:
	for line in attention_lines:
		_draw_overlay_line(line)
	for line in dialogue_lines:
		_draw_overlay_line(line)
	for line in action_intent_lines:
		_draw_overlay_line(line)
	for line in blocked_lines:
		_draw_overlay_line(line)
	for line in siming_influence_lines:
		_draw_overlay_line(line)
	for marker in target_markers:
		draw_circle(marker.get("point", Vector2.ZERO), 8.0, marker.get("color", Color.WHITE))
		draw_string(ThemeDB.fallback_font, marker.get("point", Vector2.ZERO) + Vector2(10.0, -8.0), str(marker.get("label", "")), HORIZONTAL_ALIGNMENT_LEFT, -1, 14)


func _get_state() -> Node:
	return get_node_or_null("../CharacterDirectorState")


func _build_actor_line_family(state: Node, payload: Dictionary, color: Color, target_key: String, label: String) -> Array[Dictionary]:
	var actor_id := str(payload.get("actor_id", "") or "")
	var target_ref := str(payload.get(target_key, "") or "")
	if actor_id.is_empty() or target_ref.is_empty():
		return []
	return _build_line_entries(state, actor_id, target_ref, color, label)


func _build_attention_line_family(state: Node) -> Array[Dictionary]:
	var actor_states: Dictionary = state.call("get_visible_actor_states")
	var lines: Array[Dictionary] = []
	for actor_id in actor_states.keys():
		var payload: Dictionary = actor_states[actor_id]
		var target_ref := str(payload.get("focus_target", "") or "")
		lines.append_array(_build_line_entries(state, str(actor_id), target_ref, Color(0.45, 0.75, 1.0, 0.9), "attention"))
	return lines


func _build_action_intent_line_family(state: Node) -> Array[Dictionary]:
	var actor_states: Dictionary = state.call("get_visible_actor_states")
	var lines: Array[Dictionary] = []
	for actor_id in actor_states.keys():
		var payload: Dictionary = actor_states[actor_id]
		var target_ref := str(payload.get("focus_target", "") or "")
		if str(payload.get("current_intent", "") or "").is_empty():
			continue
		lines.append_array(_build_line_entries(state, str(actor_id), target_ref, Color(1.0, 0.75, 0.25, 0.9), "intent"))
	return lines


func _build_dialogue_line_family(state: Node) -> Array[Dictionary]:
	var lines: Array[Dictionary] = []
	for pair_entry in state.call("get_dialogue_pair_entries"):
		var speaker := str(pair_entry.get("speaker_actor_id", "") or "")
		var listener := str(pair_entry.get("listener_actor_id", "") or "")
		lines.append_array(_build_line_entries(state, speaker, listener, Color(0.6, 1.0, 0.6, 0.9), "dialogue"))
	return lines


func _build_blocked_line_family(state: Node) -> Array[Dictionary]:
	var lines: Array[Dictionary] = []
	for outcome in state.call("get_recent_world_outcomes"):
		if str(outcome.get("settlement_status", "") or "") != "rejected":
			continue
		lines.append_array(
			_build_line_entries(
				state,
				str(outcome.get("actor_id", "") or ""),
				str(outcome.get("target_ref", "") or ""),
				Color(1.0, 0.35, 0.35, 0.95),
				"blocked"
			)
		)
	return lines


func _build_siming_line_family(state: Node) -> Array[Dictionary]:
	var siming_state: Dictionary = state.get_latest_siming_state()
	var target_ref := str(siming_state.get("target_ref", "") or "")
	if target_ref.is_empty():
		return []
	var lines: Array[Dictionary] = []
	var actor_states: Dictionary = state.call("get_visible_actor_states")
	for actor_id in actor_states.keys():
		lines.append_array(_build_line_entries(state, str(actor_id), target_ref, Color(1.0, 0.45, 0.85, 0.95), "siming"))
	return lines


func _build_target_markers(state: Node, payload: Dictionary) -> Array[Dictionary]:
	var markers: Array[Dictionary] = []
	var target_ref := str(payload.get("focus_target", "") or "")
	var target_node := _resolve_world_target_node(state, target_ref)
	if target_node == null:
		return markers
	markers.append(
		{
			"point": _project_world_to_canvas(target_node.global_position + Vector3(0.0, 1.2, 0.0)),
			"label": target_ref,
			"color": Color(1.0, 0.95, 0.35, 0.95),
		}
	)
	return markers


func _build_line_entries(state: Node, source_ref: String, target_ref: String, color: Color, label: String) -> Array[Dictionary]:
	var source_node := _resolve_world_target_node(state, source_ref)
	var target_node := _resolve_world_target_node(state, target_ref)
	if source_node == null or target_node == null:
		return []
	return [
		{
			"from_point": _project_world_to_canvas(source_node.global_position + Vector3(0.0, 1.4, 0.0)),
			"to_point": _project_world_to_canvas(target_node.global_position + Vector3(0.0, 1.2, 0.0)),
			"color": color,
			"label": label,
		}
	]


func _draw_overlay_line(line: Dictionary) -> void:
	var from_point: Vector2 = line.get("from_point", Vector2.ZERO)
	var to_point: Vector2 = line.get("to_point", Vector2.ZERO)
	var color: Color = line.get("color", Color.WHITE)
	draw_line(from_point, to_point, color, 3.0)
	draw_circle(to_point, 5.0, color)
	draw_string(ThemeDB.fallback_font, (from_point + to_point) * 0.5 + Vector2(6.0, -6.0), str(line.get("label", "")), HORIZONTAL_ALIGNMENT_LEFT, -1, 14)


func _resolve_world_target_node(state: Node, target_ref: String) -> Node3D:
	if target_ref.is_empty():
		return null
	return state.call("resolve_target_node", target_ref)


func _project_world_to_canvas(world_position: Vector3) -> Vector2:
	var camera := get_viewport().get_camera_3d()
	if camera == null:
		return Vector2.ZERO
	return camera.unproject_position(world_position)
