extends Node

signal dialogue_received(payload)
signal action_request_received(payload)
signal world_result_received(payload)
signal state_machine_transition_received(payload)
signal siming_output_received(payload)
signal focus_state_received(payload)
signal character_runtime_state_snapshot_received(payload)
signal character_runtime_state_delta_received(payload)
signal conversation_candidate_received(payload)
signal character_agent_output_received(payload)
signal character_actor_status_emitted(payload)
signal debug_event_logged(message)
signal backend_connected(url)
signal backend_disconnected(code)
signal backend_ack_received(payload)
signal backend_connection_failed(url, code)

func _ready() -> void:
    set_process_input(true)
    set_process_unhandled_input(true)

func _input(event: InputEvent) -> void:
    _log_mouse_button_event("global_input", event)

func _unhandled_input(event: InputEvent) -> void:
    _log_mouse_button_event("global_unhandled_input", event)

func log_debug(message: String) -> void:
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
