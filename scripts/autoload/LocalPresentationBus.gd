extends Node

signal dialogue_received(payload)
signal dialogue_stream_started(payload)
signal dialogue_stream_delta_received(payload)
signal dialogue_stream_ended(payload)
signal action_request_received(payload)
signal world_result_received(payload)
signal state_machine_transition_received(payload)
signal siming_output_received(payload)
signal focus_state_received(payload)
signal character_runtime_state_snapshot_received(payload)
signal character_runtime_state_delta_received(payload)
signal conversation_candidate_received(payload)
signal character_agent_output_received(payload)
signal character_agent_execution_received(payload)
signal character_agent_debug_snapshot_received(payload)
signal character_agent_debug_event_received(payload)
signal siming_debug_snapshot_received(payload)
signal siming_debug_event_received(payload)
signal world_outcome_trace_received(payload)
signal scheduling_round_trace_received(payload)
signal script_beat_event_received(payload)
signal character_actor_status_emitted(payload)
signal embodied_controller_bound_received(payload)
signal embodied_action_request_received(payload)
signal embodied_settlement_result_received(payload)
signal embodied_cancel_directive_received(payload)
signal embodied_resync_projection_received(payload)
signal embodied_interaction_session_event_received(payload)
signal embodied_handoff_event_received(payload)
signal embodied_carry_place_event_received(payload)
signal embodied_phase_event_emitted(payload)
signal embodied_local_outcome_emitted(payload)
signal embodied_resync_request_emitted(payload)
signal debug_event_logged(message)
signal backend_connected(url)
signal backend_disconnected(code)
signal backend_ack_received(payload)
signal backend_connection_failed(url, code)

var debug_logging_enabled := false

func _ready() -> void:
	debug_logging_enabled = (
		OS.get_environment("PHASE0_AUTOTEST") == "1"
		or OS.get_environment("PHASE0_FOCUS_AUTOTEST") == "1"
		or OS.get_environment("PHASE0_DEBUG_LOGGING") == "1"
	)
	_apply_debug_logging_mode()

func _input(event: InputEvent) -> void:
	_log_mouse_button_event("global_input", event)

func _unhandled_input(event: InputEvent) -> void:
	_log_mouse_button_event("global_unhandled_input", event)

func set_debug_logging_enabled(enabled: bool) -> void:
	debug_logging_enabled = enabled
	_apply_debug_logging_mode()

func is_debug_logging_enabled() -> bool:
	return debug_logging_enabled

func _apply_debug_logging_mode() -> void:
	set_process_input(debug_logging_enabled)
	set_process_unhandled_input(debug_logging_enabled)

func log_debug(message: String) -> void:
	if not debug_logging_enabled:
		return
	print("[LocalPresentationBus] %s" % message)
	emit_signal("debug_event_logged", message)

func _log_mouse_button_event(source: String, event: InputEvent) -> void:
	if not (event is InputEventMouseButton):
		return
	var mouse_event := event as InputEventMouseButton
	log_debug(
		"%s:button=%s pressed=%s device=%s" % [
			source,
			mouse_event.button_index,
			str(mouse_event.pressed),
			mouse_event.device,
		]
	)
