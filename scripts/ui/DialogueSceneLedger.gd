extends CanvasLayer

@onready var label: RichTextLabel = RichTextLabel.new()

var selected_pair_key := ""


func _ready() -> void:
	add_child(label)
	label.position = Vector2(960, 360)
	label.size = Vector2(380, 260)
	var state := _get_state()
	if state and state.has_signal("observatory_state_changed"):
		state.observatory_state_changed.connect(_refresh)
	_refresh()


func _refresh() -> void:
	var state := _get_state()
	if state == null:
		return
	visible = bool(state.observatory_enabled and state.script_mode)
	var actor_state: Dictionary = state.get_selected_actor_state()
	var perceived := str(actor_state.get("perception_summary", "") or "")
	var interpreted := str(actor_state.get("interpretation_summary", "") or "")
	var said := str(actor_state.get("execution_summary", "") or "")
	var mismatch := perceived != interpreted
	var alignment := "alignment" if not mismatch else "mismatch"
	label.text = "\n".join(
		[
			"pair=%s" % selected_pair_key,
			"perceived=%s" % perceived,
			"interpreted=%s" % interpreted,
			"said=%s" % said,
			"mismatch=%s" % str(mismatch),
			"alignment=%s" % alignment,
		]
	)


func _get_state() -> Node:
	return get_node_or_null("../CharacterDirectorState")
