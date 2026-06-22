extends CanvasLayer

@onready var label: RichTextLabel = RichTextLabel.new()


func _ready() -> void:
	add_child(label)
	label.position = Vector2(16, 280)
	label.size = Vector2(460, 300)
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
			"Perception: %s" % str(payload.get("perception_summary", "") or ""),
			"Internal State: %s" % str(payload.get("state_label", "") or ""),
			"Memory: %s" % str(payload.get("memory_summary", "") or ""),
			"Interpretation: %s" % str(payload.get("interpretation_summary", "") or ""),
			"Decision: %s" % str(payload.get("decision_summary", "") or ""),
			"Execution: %s" % str(payload.get("execution_summary", "") or ""),
			"Outcome: %s" % str(payload.get("latest_outcome_summary", "") or ""),
			"Siming Trace: %s" % str(payload.get("latest_siming_summary", "") or ""),
		]
	)


func _get_state() -> Node:
	return get_node_or_null("../CharacterDirectorState")
