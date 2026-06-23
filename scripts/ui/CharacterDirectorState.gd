extends Node

signal observatory_state_changed()

var observatory_enabled := false
var director_mode := false
var script_mode := false
var freeze_mode := false
var selected_actor_id := "char_a"
var frozen_frame := {}
var latest_actor_states := {}
var recent_actor_events := {}
var latest_siming_state := {}
var recent_siming_events: Array[Dictionary] = []
var recent_world_outcomes: Array[Dictionary] = []
var recent_script_beats: Array[Dictionary] = []

const MAX_EVENT_HISTORY := 24
const DEFAULT_OBSERVATORY_ACTOR_IDS := ["char_c", "char_a", "char_b"]


func _ready() -> void:
	var bus := get_node_or_null("/root/LocalPresentationBus")
	if bus == null:
		return
	if bus.has_signal("character_agent_debug_snapshot_received"):
		bus.character_agent_debug_snapshot_received.connect(_on_character_agent_debug_snapshot_received)
	if bus.has_signal("character_agent_debug_event_received"):
		bus.character_agent_debug_event_received.connect(_on_character_agent_debug_event_received)
	if bus.has_signal("siming_debug_snapshot_received"):
		bus.siming_debug_snapshot_received.connect(_on_siming_debug_snapshot_received)
	if bus.has_signal("siming_debug_event_received"):
		bus.siming_debug_event_received.connect(_on_siming_debug_event_received)
	if bus.has_signal("world_outcome_trace_received"):
		bus.world_outcome_trace_received.connect(_on_world_outcome_trace_received)
	if bus.has_signal("script_beat_event_received"):
		bus.script_beat_event_received.connect(_on_script_beat_event_received)


func set_observatory_enabled(enabled: bool) -> void:
	observatory_enabled = enabled
	emit_signal("observatory_state_changed")


func set_director_mode(enabled: bool) -> void:
	director_mode = enabled
	emit_signal("observatory_state_changed")


func set_script_mode(enabled: bool) -> void:
	script_mode = enabled
	emit_signal("observatory_state_changed")


func set_freeze_mode(enabled: bool) -> void:
	if enabled and not freeze_mode:
		_capture_frozen_frame()
	elif not enabled:
		frozen_frame = {}
	freeze_mode = enabled
	emit_signal("observatory_state_changed")


func cycle_actor(step: int) -> void:
	var actor_ids := _get_cycle_actor_ids()
	if actor_ids.is_empty():
		return
	actor_ids.sort()
	var current_index := actor_ids.find(selected_actor_id)
	if current_index == -1:
		current_index = 0
	selected_actor_id = actor_ids[(current_index + step + actor_ids.size()) % actor_ids.size()]
	emit_signal("observatory_state_changed")


func set_selected_actor(actor_id: String) -> void:
	if actor_id.is_empty():
		return
	selected_actor_id = actor_id
	emit_signal("observatory_state_changed")


func get_selected_actor_state() -> Dictionary:
	return _state_frame_value("latest_actor_states", {}).get(selected_actor_id, {})

func get_selected_actor_label() -> String:
	return _actor_label(selected_actor_id)


func get_selected_actor_events() -> Array[Dictionary]:
	var events: Variant = _state_frame_value("recent_actor_events", {}).get(selected_actor_id, [])
	return _dictionary_array(events)


func get_visible_actor_states() -> Dictionary:
	return _state_frame_value("latest_actor_states", {})


func get_recent_world_outcomes() -> Array[Dictionary]:
	return _dictionary_array(_state_frame_value("recent_world_outcomes", []))


func get_recent_script_beats() -> Array[Dictionary]:
	return _dictionary_array(_state_frame_value("recent_script_beats", []))

func get_latest_script_beat_summaries(limit: int = 3) -> Array[String]:
	var rows: Array[String] = []
	var beats: Array[Dictionary] = get_recent_script_beats()
	var start: int = beats.size() - limit
	if start < 0:
		start = 0
	for beat in beats.slice(start, beats.size()):
		rows.append(str(beat.get("dramatic_summary", "") or ""))
	return rows


func get_latest_siming_state() -> Dictionary:
	return _state_frame_value("latest_siming_state", {})


func get_recent_siming_events() -> Array[Dictionary]:
	return _dictionary_array(_state_frame_value("recent_siming_events", []))

func get_latest_siming_summaries(limit: int = 3) -> Array[String]:
	var rows: Array[String] = []
	var events: Array[Dictionary] = get_recent_siming_events()
	var start: int = events.size() - limit
	if start < 0:
		start = 0
	for event in events.slice(start, events.size()):
		rows.append(str(event.get("summary", "") or ""))
	return rows

func get_latest_bottom_strip_entries() -> Array[Dictionary]:
	var rows: Array[Dictionary] = []
	for outcome in get_recent_world_outcomes():
		rows.append(
			{
				"type": "世界",
				"summary": str(outcome.get("dramatic_consequence_summary", "") or outcome.get("world_change_summary", "") or outcome.get("settlement_status", "") or ""),
				"producer_ts": int(outcome.get("producer_ts", 0)),
			}
		)
	for event in get_recent_siming_events():
		rows.append(
			{
				"type": "司命",
				"summary": str(event.get("summary", "") or ""),
				"producer_ts": int(event.get("producer_ts", 0)),
			}
		)
	for beat in get_recent_script_beats():
		rows.append(
			{
				"type": "节拍",
				"summary": str(beat.get("dramatic_summary", "") or ""),
				"producer_ts": int(beat.get("producer_ts", 0)),
			}
		)
	rows.sort_custom(
		func(a: Dictionary, b: Dictionary) -> bool:
			return int(a.get("producer_ts", 0)) > int(b.get("producer_ts", 0))
	)
	if rows.size() > 3:
		rows = _dictionary_array(rows.slice(0, 3))
	return rows


func get_dialogue_pair_entries() -> Array[Dictionary]:
	var pairs_by_key := {}
	for beat in get_recent_script_beats():
		var pair_entries = beat.get("dialogue_pairs", [])
		if not (pair_entries is Array):
			continue
		for entry_variant in pair_entries:
			if not (entry_variant is Dictionary):
				continue
			var entry: Dictionary = _normalize_dialogue_pair_entry((entry_variant as Dictionary).duplicate(true))
			var pair_key := str(entry.get("pair_key", "") or "")
			if pair_key.is_empty():
				continue
			pairs_by_key[pair_key] = entry
	var rows: Array[Dictionary] = []
	for pair_key in pairs_by_key.keys():
		rows.append(pairs_by_key[pair_key])
	rows.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return str(a.get("pair_key", "")) < str(b.get("pair_key", ""))
	)
	return rows


func resolve_target_node(target_ref: String) -> Node3D:
	if target_ref.is_empty():
		return null
	var root := get_tree().current_scene
	if root == null:
		return null
	return _find_node_with_property(root, target_ref)


func _on_character_agent_debug_snapshot_received(payload: Dictionary) -> void:
	if freeze_mode:
		return
	var actor_id := str(payload.get("actor_id", "") or "")
	if actor_id.is_empty():
		return
	latest_actor_states[actor_id] = payload.duplicate(true)
	emit_signal("observatory_state_changed")


func _on_character_agent_debug_event_received(payload: Dictionary) -> void:
	if freeze_mode:
		return
	var actor_id := str(payload.get("actor_id", "") or "")
	if actor_id.is_empty():
		return
	var history: Array[Dictionary] = _dictionary_array(recent_actor_events.get(actor_id, []))
	history.append(payload.duplicate(true))
	if history.size() > MAX_EVENT_HISTORY:
		history = _dictionary_array(history.slice(history.size() - MAX_EVENT_HISTORY, history.size()))
	recent_actor_events[actor_id] = history
	emit_signal("observatory_state_changed")


func _on_siming_debug_snapshot_received(payload: Dictionary) -> void:
	if freeze_mode:
		return
	latest_siming_state = payload.duplicate(true)
	emit_signal("observatory_state_changed")


func _on_siming_debug_event_received(payload: Dictionary) -> void:
	if freeze_mode:
		return
	recent_siming_events.append(payload.duplicate(true))
	if recent_siming_events.size() > MAX_EVENT_HISTORY:
		recent_siming_events = _dictionary_array(recent_siming_events.slice(recent_siming_events.size() - MAX_EVENT_HISTORY, recent_siming_events.size()))
	emit_signal("observatory_state_changed")


func _on_world_outcome_trace_received(payload: Dictionary) -> void:
	if freeze_mode:
		return
	recent_world_outcomes.append(payload.duplicate(true))
	if recent_world_outcomes.size() > MAX_EVENT_HISTORY:
		recent_world_outcomes = _dictionary_array(recent_world_outcomes.slice(recent_world_outcomes.size() - MAX_EVENT_HISTORY, recent_world_outcomes.size()))
	emit_signal("observatory_state_changed")


func _on_script_beat_event_received(payload: Dictionary) -> void:
	if freeze_mode:
		return
	recent_script_beats.append(payload.duplicate(true))
	if recent_script_beats.size() > MAX_EVENT_HISTORY:
		recent_script_beats = _dictionary_array(recent_script_beats.slice(recent_script_beats.size() - MAX_EVENT_HISTORY, recent_script_beats.size()))
	emit_signal("observatory_state_changed")


func _capture_frozen_frame() -> void:
	frozen_frame = {
		"latest_actor_states": latest_actor_states.duplicate(true),
		"recent_actor_events": recent_actor_events.duplicate(true),
		"latest_siming_state": latest_siming_state.duplicate(true),
		"recent_siming_events": recent_siming_events.duplicate(true),
		"recent_world_outcomes": recent_world_outcomes.duplicate(true),
		"recent_script_beats": recent_script_beats.duplicate(true),
	}


func _state_frame_value(key: String, fallback: Variant) -> Variant:
	if freeze_mode and frozen_frame.has(key):
		return frozen_frame.get(key, fallback)
	return get(key)


func _get_cycle_actor_ids() -> Array[String]:
	var actor_ids: Array[String] = []
	for actor_id in DEFAULT_OBSERVATORY_ACTOR_IDS:
		actor_ids.append(str(actor_id))
	for actor_id in latest_actor_states.keys():
		var actor_id_text := str(actor_id)
		if not actor_ids.has(actor_id_text):
			actor_ids.append(actor_id_text)
	return actor_ids


func _find_node_with_property(node: Node, target_ref: String) -> Node3D:
	if node is Node3D:
		if str(node.get("actor_id")) == target_ref:
			return node
		if str(node.get("object_id")) == target_ref:
			return node
		if str(node.get("environment_id")) == target_ref:
			return node
	for child in node.get_children():
		var resolved := _find_node_with_property(child, target_ref)
		if resolved != null:
			return resolved
	return null


func _dictionary_array(value: Variant) -> Array[Dictionary]:
	var rows: Array[Dictionary] = []
	if value is Array:
		for entry in value:
			if entry is Dictionary:
				rows.append((entry as Dictionary).duplicate(true))
	return rows

func _actor_label(actor_id: String) -> String:
	if actor_id == "char_a":
		return "角色A"
	if actor_id == "char_b":
		return "角色B"
	if actor_id == "char_c":
		return "玩家角色"
	return actor_id


func _normalize_dialogue_pair_entry(entry: Dictionary) -> Dictionary:
	var speaker_perceived := str(entry.get("speaker_perceived_summary", "") or entry.get("perceived_summary", "") or "")
	var listener_perceived := str(entry.get("listener_perceived_summary", "") or "")
	var speaker_interpreted := str(entry.get("speaker_interpreted_summary", "") or entry.get("interpreted_summary", "") or "")
	var listener_interpreted := str(entry.get("listener_interpreted_summary", "") or "")
	var speaker_said := str(entry.get("speaker_said", "") or entry.get("spoken_content", "") or "")
	var listener_said := str(entry.get("listener_said", "") or "")
	var speaker_alignment := str(entry.get("speaker_alignment_label", "") or entry.get("alignment_label", "alignment") or "alignment")
	var listener_alignment := str(entry.get("listener_alignment_label", "") or speaker_alignment or "alignment")
	entry["speaker_perceived_summary"] = speaker_perceived
	entry["listener_perceived_summary"] = listener_perceived
	entry["speaker_interpreted_summary"] = speaker_interpreted
	entry["listener_interpreted_summary"] = listener_interpreted
	entry["speaker_said"] = speaker_said
	entry["listener_said"] = listener_said
	entry["speaker_alignment_label"] = speaker_alignment
	entry["listener_alignment_label"] = listener_alignment
	entry["perceived_summary"] = "%s | %s" % [speaker_perceived, listener_perceived]
	entry["interpreted_summary"] = "%s | %s" % [speaker_interpreted, listener_interpreted]
	entry["spoken_content"] = "%s | %s" % [speaker_said, listener_said]
	entry["alignment_label"] = "mismatch" if speaker_alignment == "mismatch" or listener_alignment == "mismatch" else "alignment"
	return entry
