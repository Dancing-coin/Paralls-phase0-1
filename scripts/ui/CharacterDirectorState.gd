extends Node

signal observatory_state_changed()

var observatory_enabled := false
var director_mode := false
var script_mode := false
var freeze_mode := false
var selected_actor_id := "char_a"
var latest_actor_states := {}
var recent_actor_events := {}
var latest_siming_state := {}
var recent_siming_events: Array[Dictionary] = []
var recent_world_outcomes: Array[Dictionary] = []
var recent_script_beats: Array[Dictionary] = []

const MAX_EVENT_HISTORY := 24


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
	freeze_mode = enabled
	emit_signal("observatory_state_changed")


func cycle_actor(step: int) -> void:
	var actor_ids: Array[String] = []
	for actor_id in latest_actor_states.keys():
		actor_ids.append(str(actor_id))
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
	return latest_actor_states.get(selected_actor_id, {})


func get_selected_actor_events() -> Array[Dictionary]:
	return recent_actor_events.get(selected_actor_id, [])


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
	var history: Array[Dictionary] = recent_actor_events.get(actor_id, [])
	history.append(payload.duplicate(true))
	if history.size() > MAX_EVENT_HISTORY:
		history = history.slice(history.size() - MAX_EVENT_HISTORY, history.size())
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
		recent_siming_events = recent_siming_events.slice(recent_siming_events.size() - MAX_EVENT_HISTORY, recent_siming_events.size())
	emit_signal("observatory_state_changed")


func _on_world_outcome_trace_received(payload: Dictionary) -> void:
	if freeze_mode:
		return
	recent_world_outcomes.append(payload.duplicate(true))
	if recent_world_outcomes.size() > MAX_EVENT_HISTORY:
		recent_world_outcomes = recent_world_outcomes.slice(recent_world_outcomes.size() - MAX_EVENT_HISTORY, recent_world_outcomes.size())
	emit_signal("observatory_state_changed")


func _on_script_beat_event_received(payload: Dictionary) -> void:
	if freeze_mode:
		return
	recent_script_beats.append(payload.duplicate(true))
	if recent_script_beats.size() > MAX_EVENT_HISTORY:
		recent_script_beats = recent_script_beats.slice(recent_script_beats.size() - MAX_EVENT_HISTORY, recent_script_beats.size())
	emit_signal("observatory_state_changed")
