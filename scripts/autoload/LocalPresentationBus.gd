extends Node

signal dialogue_received(payload)
signal world_result_received(payload)
signal siming_output_received(payload)
signal focus_state_received(payload)
signal character_runtime_state_snapshot_received(payload)
signal character_runtime_state_delta_received(payload)
signal conversation_candidate_received(payload)
signal debug_event_logged(message)
signal backend_connected(url)
signal backend_disconnected(code)
signal backend_ack_received(payload)
signal backend_connection_failed(url, code)

func log_debug(message: String) -> void:
    print("[LocalPresentationBus] %s" % message)
    emit_signal("debug_event_logged", message)
