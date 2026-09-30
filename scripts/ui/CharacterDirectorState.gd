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
var latest_siming_summaries_by_actor := {}
var recent_siming_events: Array[Dictionary] = []
var recent_world_outcomes: Array[Dictionary] = []
var recent_scheduling_rounds: Array[Dictionary] = []
var recent_script_beats: Array[Dictionary] = []
var recent_dialogue_pairs: Array[Dictionary] = []
var _observatory_refresh_queued := false
var _state_refresh_queued := false

const MAX_EVENT_HISTORY := 24
const DEFAULT_OBSERVATORY_ACTOR_IDS := ["char_c", "char_a", "char_b"]

# GDScript's `or` returns a boolean, unlike Python's value-coalescing `or`.
# Keep presentation payload normalization value-preserving at this boundary.
func _text(value: Variant, fallback: String = "") -> String:
	if value == null:
		return fallback
	var result := str(value)
	return fallback if result.is_empty() else result

func _first_text(values: Array) -> String:
	for value in values:
		var result := _text(value)
		if not result.is_empty():
			return result
	return ""


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
	if bus.has_signal("siming_output_received"):
		bus.siming_output_received.connect(_on_siming_output_received)
	if bus.has_signal("world_outcome_trace_received"):
		bus.world_outcome_trace_received.connect(_on_world_outcome_trace_received)
	if bus.has_signal("scheduling_round_trace_received"):
		bus.scheduling_round_trace_received.connect(_on_scheduling_round_trace_received)
	if bus.has_signal("script_beat_event_received"):
		bus.script_beat_event_received.connect(_on_script_beat_event_received)


func _emit_observatory_state_changed() -> void:
	_observatory_refresh_queued = false
	if not freeze_mode:
		emit_signal("observatory_state_changed")


func set_observatory_enabled(enabled: bool) -> void:
	observatory_enabled = enabled
	_queue_state_refresh()


func set_director_mode(enabled: bool) -> void:
	director_mode = enabled
	_queue_state_refresh()


func set_script_mode(enabled: bool) -> void:
	script_mode = enabled
	_queue_state_refresh()


func set_freeze_mode(enabled: bool) -> void:
	if enabled and not freeze_mode:
		_capture_frozen_frame()
	elif not enabled:
		frozen_frame = {}
	freeze_mode = enabled
	_queue_state_refresh()


func cycle_actor(step: int) -> void:
	var actor_ids := _get_cycle_actor_ids()
	if actor_ids.is_empty():
		return
	actor_ids.sort()
	var current_index := actor_ids.find(selected_actor_id)
	if current_index == -1:
		current_index = 0
	selected_actor_id = actor_ids[(current_index + step + actor_ids.size()) % actor_ids.size()]
	_queue_state_refresh()


func set_selected_actor(actor_id: String) -> void:
	if actor_id.is_empty():
		return
	selected_actor_id = actor_id
	_queue_state_refresh()


func get_selected_actor_state() -> Dictionary:
	return _state_frame_value("latest_actor_states", {}).get(selected_actor_id, {})

func get_selected_actor_label() -> String:
	return _actor_label(selected_actor_id)


func get_selected_actor_events() -> Array[Dictionary]:
	var events: Variant = _state_frame_value("recent_actor_events", {}).get(selected_actor_id, [])
	return _dictionary_array(events)


func get_selected_actor_latest_siming_summary() -> String:
	return _text(get_selected_actor_state().get("latest_siming_summary", ""))


func get_selected_actor_recent_siming_reasons(limit: int = 2) -> Array[String]:
	if limit <= 0:
		return []
	var rows: Array[String] = []
	var events: Array[Dictionary] = get_recent_siming_events()
	for event in events:
		if _text(event.get("target_ref", "")) != selected_actor_id:
			continue
		var reason := _text(event.get("reason_summary", ""))
		rows.append(reason if not reason.is_empty() else _text(event.get("summary", "")))
	if rows.size() > limit:
		rows = _string_array(rows.slice(rows.size() - limit, rows.size()))
	return rows


func get_visible_actor_states() -> Dictionary:
	return _state_frame_value("latest_actor_states", {})


func get_recent_world_outcomes() -> Array[Dictionary]:
	return _dictionary_array(_state_frame_value("recent_world_outcomes", []))

func get_recent_scheduling_rounds() -> Array[Dictionary]:
	return _dictionary_array(_state_frame_value("recent_scheduling_rounds", []))


func get_recent_script_beats() -> Array[Dictionary]:
	return _dictionary_array(_state_frame_value("recent_script_beats", []))

func get_latest_script_beat_summaries(limit: int = 3) -> Array[String]:
	var rows: Array[String] = []
	var beats: Array[Dictionary] = get_recent_script_beats()
	var start: int = beats.size() - limit
	if start < 0:
		start = 0
	for beat in beats.slice(start, beats.size()):
		rows.append(_text(beat.get("dramatic_summary", "")))
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
		rows.append(_text(event.get("summary", "")))
	return rows

func get_latest_bottom_strip_entries() -> Array[Dictionary]:
	var rows: Array[Dictionary] = []
	for outcome in get_recent_world_outcomes():
		rows.append(
			{
				"type": "世界",
				"summary": _first_text([outcome.get("dramatic_consequence_summary", ""), outcome.get("world_change_summary", ""), outcome.get("settlement_status", "")]),
				"producer_ts": int(outcome.get("producer_ts", 0)),
			}
		)
	for round in get_recent_scheduling_rounds():
		rows.append(
			{
				"type": "调度",
				"summary": _text(round.get("round_summary", "")),
				"producer_ts": int(round.get("round_started_at", round.get("producer_ts", 0))),
			}
		)
	for event in get_recent_siming_events():
		rows.append(
			{
				"type": "司命",
				"summary": _text(event.get("summary", "")),
				"producer_ts": int(event.get("producer_ts", 0)),
			}
		)
	for beat in get_recent_script_beats():
		rows.append(
			{
				"type": "节拍",
				"summary": _text(beat.get("dramatic_summary", "")),
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
	var rows := _dictionary_array(_state_frame_value("recent_dialogue_pairs", []))
	rows = _attach_siming_pressure_context(rows, _latest_siming_pressure_context())
	rows.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return str(a.get("pair_key", "")) < str(b.get("pair_key", ""))
	)
	return rows


func _latest_siming_pressure_context() -> String:
	for event in get_recent_siming_events():
		var summary := _first_text([event.get("reason_summary", ""), event.get("summary", "")])
		if not summary.is_empty():
			return summary
	var beats := get_recent_script_beats()
	for index in range(beats.size() - 1, -1, -1):
		var summaries: Variant = beats[index].get("siming_summaries", [])
		if summaries is Array:
			for item in summaries:
				if item is Dictionary:
					var summary := _first_text([(item as Dictionary).get("reason_summary", ""), (item as Dictionary).get("summary", "")])
					if not summary.is_empty():
						return summary
	return ""


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
	var actor_id := _text(payload.get("actor_id", ""))
	if actor_id.is_empty():
		return
	var snapshot := payload.duplicate(true)
	var siming_summary := _text(latest_siming_summaries_by_actor.get(actor_id, ""))
	if siming_summary.is_empty():
		siming_summary = _first_text([latest_siming_state.get("prompt_summary", ""), latest_siming_state.get("reason_summary", ""), latest_siming_state.get("summary", "")])
	if not siming_summary.is_empty():
		snapshot["latest_siming_summary"] = siming_summary
	latest_actor_states[actor_id] = snapshot
	_queue_state_refresh()


func _on_character_agent_debug_event_received(payload: Dictionary) -> void:
	if freeze_mode:
		return
	var actor_id := _text(payload.get("actor_id", ""))
	if actor_id.is_empty():
		return
	var history: Array[Dictionary] = _dictionary_array(recent_actor_events.get(actor_id, []))
	history.append(payload.duplicate(true))
	if history.size() > MAX_EVENT_HISTORY:
		history = _dictionary_array(history.slice(history.size() - MAX_EVENT_HISTORY, history.size()))
	recent_actor_events[actor_id] = history
	_queue_state_refresh()


func _on_siming_debug_snapshot_received(payload: Dictionary) -> void:
	if freeze_mode:
		return
	latest_siming_state = payload.duplicate(true)
	_queue_state_refresh()


func _on_siming_debug_event_received(payload: Dictionary) -> void:
	if freeze_mode:
		return
	latest_siming_state = payload.duplicate(true)
	var debug_summary := _first_text([payload.get("prompt_summary", ""), payload.get("reason_summary", ""), payload.get("summary", "")])
	var debug_target := _text(payload.get("target_actor_id", payload.get("target_ref", "")))
	if not debug_summary.is_empty() and not debug_target.is_empty() and debug_target.begins_with("char_"):
		latest_siming_summaries_by_actor[debug_target] = debug_summary
	recent_siming_events.append(payload.duplicate(true))
	if recent_siming_events.size() > MAX_EVENT_HISTORY:
		recent_siming_events = _dictionary_array(recent_siming_events.slice(recent_siming_events.size() - MAX_EVENT_HISTORY, recent_siming_events.size()))
	recent_dialogue_pairs = _attach_siming_pressure_context(
		recent_dialogue_pairs,
		_first_text([payload.get("reason_summary", ""), payload.get("summary", "")])
	)
	_queue_state_refresh()


func _on_siming_output_received(payload: Dictionary) -> void:
	if freeze_mode:
		return
	latest_siming_state = payload.duplicate(true)
	var summary := _first_text([payload.get("prompt_summary", ""), payload.get("reason_summary", ""), payload.get("summary", "")])
	var target_ref := _first_text([payload.get("target_actor_id", ""), payload.get("target_object_id", ""), payload.get("target_environment_id", "")])
	if not summary.is_empty():
		var target_actor_id := _text(payload.get("target_actor_id", ""))
		if not target_actor_id.is_empty():
			latest_siming_summaries_by_actor[target_actor_id] = summary
		for actor_id in latest_actor_states.keys():
			if target_actor_id.is_empty() and latest_siming_summaries_by_actor.has(actor_id):
				continue
			var actor_state: Dictionary = latest_actor_states[actor_id]
			# A Siming output is a public runtime feedback signal. Keep it visible
			# on the observed actor rail even when the prompt targets an object.
			actor_state["latest_siming_summary"] = summary
			latest_actor_states[actor_id] = actor_state
	_queue_state_refresh()


func _on_world_outcome_trace_received(payload: Dictionary) -> void:
	if freeze_mode:
		return
	recent_world_outcomes.append(payload.duplicate(true))
	if recent_world_outcomes.size() > MAX_EVENT_HISTORY:
		recent_world_outcomes = _dictionary_array(recent_world_outcomes.slice(recent_world_outcomes.size() - MAX_EVENT_HISTORY, recent_world_outcomes.size()))
	_queue_state_refresh()


func _on_scheduling_round_trace_received(payload: Dictionary) -> void:
	if freeze_mode:
		return
	recent_scheduling_rounds.append(payload.duplicate(true))
	if recent_scheduling_rounds.size() > MAX_EVENT_HISTORY:
		recent_scheduling_rounds = _dictionary_array(recent_scheduling_rounds.slice(recent_scheduling_rounds.size() - MAX_EVENT_HISTORY, recent_scheduling_rounds.size()))
	_queue_state_refresh()


func _on_script_beat_event_received(payload: Dictionary) -> void:
	if freeze_mode:
		return
	var presentation_beat := _presentation_script_beat(payload)
	recent_script_beats.append(presentation_beat)
	if recent_script_beats.size() > MAX_EVENT_HISTORY:
		recent_script_beats = _dictionary_array(recent_script_beats.slice(recent_script_beats.size() - MAX_EVENT_HISTORY, recent_script_beats.size()))
	recent_dialogue_pairs = _merge_dialogue_pair_rows(
		recent_dialogue_pairs,
		presentation_beat.get("dialogue_pairs", [])
	)
	_request_observatory_refresh()


func _presentation_script_beat(payload: Dictionary) -> Dictionary:
	var siming_summaries := _presentation_siming_summaries(payload.get("siming_summaries", []))
	return {
		"beat_id": _text(payload.get("beat_id", "")),
		"producer_ts": int(payload.get("producer_ts", 0) or 0),
		"causation_id": _text(payload.get("causation_id", "")),
		"correlation_id": _text(payload.get("correlation_id", "")),
		"participants": _string_array(payload.get("participants", [])),
		"dramatic_summary": _first_text([payload.get("dramatic_summary", ""), payload.get("summary", "")]),
		"actor_event_refs": _string_array(payload.get("actor_event_refs", [])),
		"siming_event_refs": _string_array(payload.get("siming_event_refs", [])),
		"world_event_refs": _string_array(payload.get("world_event_refs", [])),
		"actor_summaries": _presentation_actor_summaries(payload.get("actor_summaries", [])),
		"siming_summaries": siming_summaries,
		"world_summaries": _dictionary_array(payload.get("world_summaries", [])),
		"dialogue_pairs": _presentation_dialogue_pairs(payload.get("dialogue_pairs", []), siming_summaries),
	}


func _presentation_actor_summaries(value: Variant) -> Array[Dictionary]:
	var rows: Array[Dictionary] = []
	if not (value is Array):
		return rows
	for row_value in value:
		if not (row_value is Dictionary):
			continue
		var row: Dictionary = row_value
		rows.append(
			{
				"actor_id": _text(row.get("actor_id", "")),
				"stage": _text(row.get("stage", "")),
				"summary": _text(row.get("summary", "")),
				"focus_target": _text(row.get("focus_target", "")),
				"intent_label": _text(row.get("intent_label", "")),
			}
		)
	return rows

func _queue_state_refresh() -> void:
	if _state_refresh_queued:
		return
	_state_refresh_queued = true
	call_deferred("_emit_state_changed")


func _request_observatory_refresh() -> void:
	if _observatory_refresh_queued:
		return
	_observatory_refresh_queued = true
	call_deferred("_emit_observatory_state_changed")

func _emit_state_changed() -> void:
	_state_refresh_queued = false
	emit_signal("observatory_state_changed")


func _capture_frozen_frame() -> void:
	frozen_frame = {
		"latest_actor_states": latest_actor_states.duplicate(true),
		"recent_actor_events": recent_actor_events.duplicate(true),
		"latest_siming_state": latest_siming_state.duplicate(true),
		"latest_siming_summaries_by_actor": latest_siming_summaries_by_actor.duplicate(true),
		"recent_siming_events": recent_siming_events.duplicate(true),
		"recent_world_outcomes": recent_world_outcomes.duplicate(true),
		"recent_scheduling_rounds": recent_scheduling_rounds.duplicate(true),
		"recent_script_beats": recent_script_beats.duplicate(true),
		"recent_dialogue_pairs": recent_dialogue_pairs.duplicate(true),
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


func _string_array(value: Variant) -> Array[String]:
	var rows: Array[String] = []
	if value is Array:
		for entry in value:
			rows.append(str(entry))
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
	var speaker_perceived := _first_text([entry.get("speaker_perceived_summary", ""), entry.get("perceived_summary", "")])
	var listener_perceived := _text(entry.get("listener_perceived_summary", ""))
	var speaker_interpreted := _first_text([entry.get("speaker_interpreted_summary", ""), entry.get("interpreted_summary", "")])
	var listener_interpreted := _text(entry.get("listener_interpreted_summary", ""))
	var speaker_said := _first_text([entry.get("speaker_said", ""), entry.get("spoken_content", "")])
	var listener_said := _text(entry.get("listener_said", ""))
	var speaker_alignment := _first_text([entry.get("speaker_alignment_label", ""), entry.get("alignment_label", "alignment"), "alignment"])
	var listener_alignment := _first_text([entry.get("listener_alignment_label", ""), speaker_alignment, "alignment"])
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


func _presentation_siming_summaries(value: Variant) -> Array[Dictionary]:
	var rows: Array[Dictionary] = []
	if value is Array:
		for item in value:
			if not (item is Dictionary):
				continue
			var row := item as Dictionary
			rows.append({
				"stage": _text(row.get("stage", "")),
				"summary": _text(row.get("summary", "")),
				"target_ref": _text(row.get("target_ref", "")),
				"reason_summary": _text(row.get("reason_summary", "")),
				"downstream_status": _text(row.get("downstream_status", "")),
			})
	return rows


func _presentation_dialogue_pairs(value: Variant, siming_summaries: Array[Dictionary]) -> Array[Dictionary]:
	var rows := _dictionary_array(value)
	var pressure_context := ""
	for summary in siming_summaries:
		pressure_context = _first_text([summary.get("reason_summary", ""), summary.get("summary", "")])
		if not pressure_context.is_empty():
			break
	if pressure_context.is_empty():
		for event in recent_siming_events:
			pressure_context = _first_text([event.get("reason_summary", ""), event.get("summary", "")])
			if not pressure_context.is_empty():
				break
	for row in rows:
		if _text(row.get("siming_pressure_context", "")).is_empty() and not pressure_context.is_empty():
			row["siming_pressure_context"] = pressure_context
	return rows


func _attach_siming_pressure_context(rows: Array[Dictionary], pressure_context: String) -> Array[Dictionary]:
	if pressure_context.is_empty():
		return rows
	var updated: Array[Dictionary] = []
	for source_row in rows:
		var row := source_row.duplicate(true)
		if _text(row.get("siming_pressure_context", "")).is_empty():
			row["siming_pressure_context"] = pressure_context
		updated.append(row)
	return updated


func _merge_dialogue_pair_rows(existing_rows: Array[Dictionary], incoming_rows_value: Variant) -> Array[Dictionary]:
	var pairs_by_key := {}
	for row in existing_rows:
		var pair_key := _text(row.get("pair_key", ""))
		if pair_key.is_empty():
			continue
		pairs_by_key[pair_key] = row.duplicate(true)
	if incoming_rows_value is Array:
		for incoming_variant in incoming_rows_value:
			if not (incoming_variant is Dictionary):
				continue
			var incoming_row := _normalize_dialogue_pair_entry((incoming_variant as Dictionary).duplicate(true))
			var incoming_pair_key := _text(incoming_row.get("pair_key", ""))
			if incoming_pair_key.is_empty():
				continue
			var existing_row: Dictionary = (pairs_by_key.get(incoming_pair_key, {}) as Dictionary).duplicate(true)
			for field_name in ["speaker_perceived_summary", "listener_perceived_summary", "speaker_interpreted_summary", "listener_interpreted_summary", "speaker_said", "listener_said"]:
				var incoming_value: Variant = incoming_row.get(field_name, "")
				if incoming_value is String and incoming_value.is_empty() and not _text(existing_row.get(field_name, "")).is_empty():
					incoming_row[field_name] = existing_row[field_name]
			for field_name in incoming_row.keys():
				var incoming_value: Variant = incoming_row.get(field_name)
				if existing_row.has(field_name) and incoming_value is String and incoming_value.is_empty():
					continue
				existing_row[field_name] = incoming_value
			pairs_by_key[incoming_pair_key] = existing_row
	var merged_rows: Array[Dictionary] = []
	for pair_key in pairs_by_key.keys():
		merged_rows.append((pairs_by_key[pair_key] as Dictionary).duplicate(true))
	if merged_rows.size() > MAX_EVENT_HISTORY:
		merged_rows = _dictionary_array(merged_rows.slice(merged_rows.size() - MAX_EVENT_HISTORY, merged_rows.size()))
	return merged_rows
