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
	var pair_rows := _build_pair_rows(state)
	if selected_pair_key.is_empty() and not pair_rows.is_empty():
		selected_pair_key = str(pair_rows[0].get("pair_key", "") or "")
	var selected_row := {}
	for row in pair_rows:
		if str(row.get("pair_key", "") or "") == selected_pair_key:
			selected_row = row
			break
	var mismatch := str(selected_row.get("alignment_label", "alignment") or "") == "mismatch"
	label.text = "\n".join(
		[
			"pair=%s" % selected_pair_key,
			"perceived=%s" % str(selected_row.get("perceived_summary", "") or ""),
			"interpreted=%s" % str(selected_row.get("interpreted_summary", "") or ""),
			"said=%s" % str(selected_row.get("spoken_content", "") or ""),
			"mismatch=%s" % str(mismatch),
			"alignment=%s" % str(selected_row.get("alignment_label", "alignment") or "alignment"),
		]
	)


func _get_state() -> Node:
	return get_node_or_null("../CharacterDirectorState")


func _build_pair_rows(state: Node) -> Array[Dictionary]:
	return state.get_dialogue_pair_entries()
