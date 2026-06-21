extends CanvasLayer

var lines: Array[String] = []
var label: Label
var locomotion_status := ""
var combat_status: Array[String] = []

func _ready() -> void:
	label = Label.new()
	label.position = Vector2(16, 16)
	label.size = Vector2(1200, 420)
	add_child(label)
	var bus := _get_bus()
	if bus:
		bus.debug_event_logged.connect(_on_debug_event_logged)
	_refresh_label()

func _on_debug_event_logged(message: String) -> void:
	if message.begins_with("locomotion_state:"):
		locomotion_status = message.trim_prefix("locomotion_state:")
		_refresh_label()
		return
	if (
		message.begins_with("global_input:")
		or message.begins_with("global_unhandled_input:")
		or message.begins_with("role_action_overlay:")
	):
		combat_status.append(message)
		if combat_status.size() > 8:
			combat_status = combat_status.slice(combat_status.size() - 8, combat_status.size())
		_refresh_label()
		return
	lines.append(message)
	if lines.size() > 14:
		lines = lines.slice(lines.size() - 14, lines.size())
	_refresh_label()

func _refresh_label() -> void:
	if label:
		var sections: Array[String] = []
		if locomotion_status != "":
			sections.append("Locomotion | %s" % locomotion_status)
		if not combat_status.is_empty():
			sections.append("Combat Trace")
			sections.append_array(combat_status)
		sections.append_array(lines)
		label.text = "\n".join(sections)

func _get_bus() -> Node:
	return get_node_or_null("/root/LocalPresentationBus")
