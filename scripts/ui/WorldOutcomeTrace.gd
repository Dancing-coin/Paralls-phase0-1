extends CanvasLayer

@onready var label: RichTextLabel = RichTextLabel.new()


func _ready() -> void:
	add_child(label)
	label.position = Vector2(500, 560)
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
	var lines: Array[String] = []
	for outcome in state.recent_world_outcomes:
		lines.append(
			"%s | %s | %s" % [
				str(outcome.get("request_type", "") or ""),
				str(outcome.get("settlement_status", "") or ""),
				str(outcome.get("dramatic_consequence_summary", "") or ""),
			]
		)
	label.text = "\n".join(lines)


func _get_state() -> Node:
	return get_node_or_null("../CharacterDirectorState")
