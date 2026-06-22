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
	var cast_names := PackedStringArray(state.latest_actor_states.keys())
	label.text = "\n".join(
		[
			"Cast Board",
			", ".join(cast_names),
			"Scene State",
			"selected_actor=%s script_mode=%s" % [state.selected_actor_id, str(state.script_mode)],
			"World / Constraint Status",
			"recent_world_outcomes=%s" % state.recent_world_outcomes.size(),
			"SimingDirectorBoard",
		]
	)


func _get_state() -> Node:
	return get_node_or_null("../CharacterDirectorState")
