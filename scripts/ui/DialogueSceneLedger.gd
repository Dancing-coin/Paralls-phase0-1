extends CanvasLayer

@onready var label: RichTextLabel = RichTextLabel.new()

var selected_pair_key := ""


func _ready() -> void:
	add_child(label)
	label.position = Vector2(760, 380)
	label.size = Vector2(560, 240)
	var state := _get_state()
	if state and state.has_signal("observatory_state_changed"):
		state.observatory_state_changed.connect(_refresh)
	_refresh()


func _refresh() -> void:
	var state := _get_state()
	if state == null:
		return
	var observatory_enabled: Variant = state.get("observatory_enabled")
	var script_mode_enabled: Variant = state.get("script_mode")
	visible = observatory_enabled == true and script_mode_enabled == true
	var pair_rows := _build_pair_rows(state)
	if pair_rows.is_empty():
		label.text = "还没有对话对账记录。先面对角色说一句话，再回来查看。"
		return
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
			"这组对话是谁和谁：%s" % selected_pair_key,
			"说话的人当时感知到：%s" % str(selected_row.get("speaker_perceived_summary", "") or ""),
			"听的人当时感知到：%s" % str(selected_row.get("listener_perceived_summary", "") or ""),
			"说话的人怎么理解局面：%s" % str(selected_row.get("speaker_interpreted_summary", "") or ""),
			"听的人怎么理解局面：%s" % str(selected_row.get("listener_interpreted_summary", "") or ""),
			"说话的人实际说了：%s" % str(selected_row.get("speaker_said", "") or ""),
			"听的人回出来的话：%s" % str(selected_row.get("listener_said", "") or ""),
			"两边理解有没有对不上：%s" % ("有" if mismatch else "没有"),
			"说话的人这边结论：%s" % str(selected_row.get("speaker_alignment_label", "alignment") or "alignment"),
			"听的人这边结论：%s" % str(selected_row.get("listener_alignment_label", "alignment") or "alignment"),
			"这组对话总体评价：%s" % str(selected_row.get("alignment_label", "alignment") or "alignment"),
		]
	)


func _get_state() -> Node:
	return get_node_or_null("../CharacterDirectorState")


func _build_pair_rows(state: Node) -> Array[Dictionary]:
	return state.call("get_dialogue_pair_entries")
