extends CanvasLayer

@onready var label: RichTextLabel = RichTextLabel.new()


func _ready() -> void:
	add_child(label)
	label.position = Vector2(500, 320)
	label.size = Vector2(420, 220)
	var state := _get_state()
	if state and state.has_signal("observatory_state_changed"):
		state.observatory_state_changed.connect(_refresh)
	_refresh()


func _refresh() -> void:
	var state := _get_state()
	if state == null:
		return
	var payload: Dictionary = state.latest_siming_state
	visible = bool(state.observatory_enabled and state.director_mode)
	label.text = "\n".join(_build_director_rows(payload))


func _get_state() -> Node:
	return get_node_or_null("../CharacterDirectorState")


func _build_director_rows(payload: Dictionary) -> Array[String]:
	return [
		"Fairness: %s" % str(payload.get("fairness_summary", "") or ""),
		"Candidate: %s" % str(payload.get("intervention_candidate", "") or ""),
		"Decision: %s" % str(payload.get("intervention_decision", "") or ""),
		"Path: %s" % str(payload.get("selected_path", "") or ""),
		"Band: %s" % str(payload.get("intervention_band", "") or ""),
		"Target: %s" % str(payload.get("target_ref", "") or ""),
		"Reason: %s" % str(payload.get("reason_summary", "") or ""),
		"Downstream: %s" % str(payload.get("downstream_status", "") or ""),
		"No Action: %s" % str(payload.get("no_action_reason", "") or ""),
	]
