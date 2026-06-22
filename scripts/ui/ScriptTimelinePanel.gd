extends CanvasLayer

@onready var label: RichTextLabel = RichTextLabel.new()

var filter_actor_id := ""
var filter_participant := ""
var expanded_beat_id := ""


func _ready() -> void:
	add_child(label)
	label.position = Vector2(960, 48)
	label.size = Vector2(380, 300)
	var state := _get_state()
	if state and state.has_signal("observatory_state_changed"):
		state.observatory_state_changed.connect(_refresh)
	_refresh()


func _refresh() -> void:
	var state := _get_state()
	if state == null:
		return
	visible = bool(state.observatory_enabled and state.script_mode)
	var lines: Array[String] = []
	for beat in _build_filtered_beats(state.get_recent_script_beats()):
		lines.append(_build_beat_summary_line(beat))
		if expanded_beat_id == str(beat.get("beat_id", "") or ""):
			lines.append_array(_build_expanded_payload_lines(beat))
	label.text = "\n".join(lines)


func _get_state() -> Node:
	return get_node_or_null("../CharacterDirectorState")


func _build_filtered_beats(beats: Array[Dictionary]) -> Array[Dictionary]:
	var filtered: Array[Dictionary] = []
	for beat in beats:
		if filter_actor_id != "" and str(beat.get("participants", [])).find(filter_actor_id) == -1:
			continue
		if filter_participant != "" and str(beat.get("participants", [])).find(filter_participant) == -1:
			continue
		filtered.append(beat)
	filtered.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return int(a.get("producer_ts", 0)) < int(b.get("producer_ts", 0))
	)
	return filtered


func _build_beat_summary_line(beat: Dictionary) -> String:
	return "%s | %s | %s" % [
		str(beat.get("correlation_id", "") or ""),
		JSON.stringify(beat.get("participants", [])),
		str(beat.get("dramatic_summary", "") or ""),
	]


func _build_expanded_payload_lines(beat: Dictionary) -> Array[String]:
	return [
		"actors=%s" % JSON.stringify(beat.get("actor_summaries", [])),
		"siming=%s" % JSON.stringify(beat.get("siming_summaries", [])),
		"world=%s" % JSON.stringify(beat.get("world_summaries", [])),
		"pairs=%s" % JSON.stringify(beat.get("dialogue_pairs", [])),
	]
