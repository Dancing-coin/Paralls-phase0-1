extends CanvasLayer

@onready var label: RichTextLabel = RichTextLabel.new()

var filter_actor_id := ""
var filter_participant := ""
var expanded_beat_id := ""


func _ready() -> void:
	add_child(label)
	label.position = Vector2(760, 48)
	label.size = Vector2(560, 320)
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
	var source_beats: Array[Dictionary] = state.call("get_recent_script_beats")
	var beats: Array[Dictionary] = _build_filtered_beats(source_beats)
	if beats.is_empty():
		label.text = "还没有形成可回放的戏。先做一次对话、一次成功交互，再看这里。"
		return
	if not beats.is_empty():
		if expanded_beat_id == "" or not _beat_is_rich(_find_beat_by_id(beats, expanded_beat_id)):
			expanded_beat_id = _pick_default_expanded_beat_id(beats)
	var lines: Array[String] = []
	for beat in beats:
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
	return "线索链=%s | 参与者=%s | 这一拍发生了：%s" % [
		str(beat.get("correlation_id", "") or ""),
		JSON.stringify(beat.get("participants", [])),
		str(beat.get("dramatic_summary", "") or ""),
	]


func _build_expanded_payload_lines(beat: Dictionary) -> Array[String]:
	return [
		"节拍编号=%s" % str(beat.get("beat_id", "") or ""),
		"角色侧摘要=%s" % JSON.stringify(beat.get("actor_summaries", [])),
		"司命侧摘要=%s" % JSON.stringify(beat.get("siming_summaries", [])),
		"世界侧摘要=%s" % JSON.stringify(beat.get("world_summaries", [])),
		"对话对账=%s" % JSON.stringify(beat.get("dialogue_pairs", [])),
	]


func _pick_default_expanded_beat_id(beats: Array[Dictionary]) -> String:
	for beat in beats:
		if _beat_is_rich(beat):
			return str(beat.get("beat_id", "") or "")
	if not beats.is_empty():
		return str(beats[-1].get("beat_id", "") or "")
	return ""


func _find_beat_by_id(beats: Array[Dictionary], beat_id: String) -> Dictionary:
	for beat in beats:
		if str(beat.get("beat_id", "") or "") == beat_id:
			return beat
	return {}


func _beat_is_rich(beat: Dictionary) -> bool:
	if beat.is_empty():
		return false
	var actor_summaries = beat.get("actor_summaries", [])
	var siming_summaries = beat.get("siming_summaries", [])
	return actor_summaries is Array and not actor_summaries.is_empty() and siming_summaries is Array and not siming_summaries.is_empty()
