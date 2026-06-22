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
	visible = bool(state.observatory_enabled)
	var payload: Dictionary = state.get_selected_actor_state()
	attention_lines = [{"from": str(payload.get("actor_id", "") or ""), "to": str(payload.get("focus_target", "") or "")}]
	dialogue_lines = [{"summary": str(payload.get("interpretation_summary", "") or "")}]
	action_intent_lines = [{"summary": str(payload.get("current_intent", "") or "")}]
	blocked_lines = [{"summary": str(payload.get("latest_outcome_summary", "") or "")}]
	siming_influence_lines = [{"summary": str(payload.get("latest_siming_summary", "") or "")}]
	target_markers = [{"target": str(payload.get("focus_target", "") or "")}]
	queue_redraw()


func _draw() -> void:
	var y := 24.0
	for line_family in [attention_lines, dialogue_lines, action_intent_lines, blocked_lines, siming_influence_lines]:
		for line in line_family:
			draw_string(ThemeDB.fallback_font, Vector2(18, y), JSON.stringify(line), HORIZONTAL_ALIGNMENT_LEFT, -1, 14)
			y += 18.0


func _get_state() -> Node:
	return get_node_or_null("../CharacterDirectorState")
