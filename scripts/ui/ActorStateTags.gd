extends CanvasLayer

@onready var label: Label = Label.new()


func _ready() -> void:
	add_child(label)
	label.position = Vector2(16, 48)
	label.size = Vector2(420, 220)
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
	label.text = "\n".join(
		[
			"Actor: %s" % str(payload.get("actor_id", "") or ""),
			"Intent: %s" % str(payload.get("current_intent", "") or ""),
			"Focus: %s" % str(payload.get("focus_target", "") or ""),
			"State: %s" % str(payload.get("state_label", "") or ""),
			"Why now: %s" % str(payload.get("why_now_summary", "") or ""),
			"Siming: %s" % str(payload.get("latest_siming_summary", "") or ""),
		]
	)


func _get_state() -> Node:
	return get_node_or_null("../CharacterDirectorState")
