extends CanvasLayer

@onready var label: RichTextLabel = RichTextLabel.new()


func _ready() -> void:
	add_child(label)
	label.position = Vector2(24, 648)
	label.size = Vector2(1290, 72)
	var state := _get_state()
	if state and state.has_signal("observatory_state_changed"):
		state.observatory_state_changed.connect(_refresh)
	_refresh()


func _refresh() -> void:
	var state := _get_state()
	if state == null:
		return
	var observatory_enabled: Variant = state.get("observatory_enabled")
	visible = observatory_enabled == true
	var rows_value: Variant = state.call("get_latest_bottom_strip_entries")
	var rows: Array[Dictionary] = []
	if rows_value is Array:
		for row_value in rows_value:
			if row_value is Dictionary:
				rows.append((row_value as Dictionary).duplicate(true))
	var lines: Array[String] = []
	for row in rows:
		lines.append(_format_bottom_strip_row(row))
	label.text = "最近 3 条\n%s" % "\n".join(lines)


func _get_state() -> Node:
	return get_node_or_null("../CharacterDirectorState")


func _format_bottom_strip_row(row: Dictionary) -> String:
	var row_type := _string_or_empty(row.get("type", ""))
	var summary := _summary_or_placeholder(row.get("summary", ""))
	if row_type == "世界":
		return "[世界] %s" % summary
	if row_type == "司命":
		return "[司命] %s" % summary
	if row_type == "节拍":
		return "[节拍] %s" % summary
	return "[%s] %s" % [row_type, summary]


func _string_or_empty(value: Variant) -> String:
	if value == null:
		return ""
	return str(value)


func _summary_or_placeholder(value: Variant) -> String:
	var summary := _string_or_empty(value)
	if summary.is_empty():
		return "暂无摘要"
	return summary
