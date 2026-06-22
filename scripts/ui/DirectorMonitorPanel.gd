extends CanvasLayer

@onready var label: RichTextLabel = RichTextLabel.new()


func _ready() -> void:
	add_child(label)
	label.position = Vector2(500, 48)
	label.size = Vector2(520, 260)
	var state := _get_state()
	if state and state.has_signal("observatory_state_changed"):
		state.observatory_state_changed.connect(_refresh)
	_refresh()


func _refresh() -> void:
	var state := _get_state()
	if state == null:
		return
	visible = bool(state.observatory_enabled and state.director_mode)
	label.text = "\n\n".join(
		[
			_build_cast_board(state),
			_build_scene_state_board(state),
			_build_world_board(state),
			"SimingDirectorBoard",
		]
	)


func _get_state() -> Node:
	return get_node_or_null("../CharacterDirectorState")


func _build_cast_board(state: Node) -> String:
	var lines := ["Cast Board"]
	var latest_actor_states: Dictionary = state.get_visible_actor_states()
	for actor_id in latest_actor_states.keys():
		var payload: Dictionary = latest_actor_states[actor_id]
		lines.append(
			"%s | intent=%s | focus=%s | why=%s" % [
				str(actor_id),
				str(payload.get("current_intent", "") or ""),
				str(payload.get("focus_target", "") or ""),
				str(payload.get("why_now_summary", "") or ""),
			]
		)
	return "\n".join(lines)


func _build_scene_state_board(state: Node) -> String:
	return "\n".join(
		[
			"Scene State",
			"selected_actor=%s" % str(state.selected_actor_id),
			"script_mode=%s freeze_mode=%s" % [str(state.script_mode), str(state.freeze_mode)],
			"recent_beats=%s" % str(state.get_recent_script_beats().size()),
		]
	)


func _build_world_board(state: Node) -> String:
	var lines := ["World / Constraint Status"]
	for outcome in state.get_recent_world_outcomes().slice(max(state.get_recent_world_outcomes().size() - 4, 0), state.get_recent_world_outcomes().size()):
		lines.append(
			"%s -> %s | %s" % [
				str(outcome.get("request_type", "") or ""),
				str(outcome.get("settlement_status", "") or ""),
				str(outcome.get("dramatic_consequence_summary", "") or ""),
			]
		)
	return "\n".join(lines)
