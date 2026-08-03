extends Node

var ws := WebSocketPeer.new()
var last_ready_state := WebSocketPeer.STATE_CLOSED
var last_requested_url := ""
var transport_barrier_sequence := 0

func _ready() -> void:
    ws.inbound_buffer_size = 1024 * 1024
    var bus := _get_bus()
    if bus and bus.has_signal("character_actor_status_emitted"):
        bus.character_actor_status_emitted.connect(_on_character_actor_status_emitted)
    if bus and bus.has_signal("embodied_phase_event_emitted"):
        bus.embodied_phase_event_emitted.connect(_on_embodied_phase_event_emitted)
    if bus and bus.has_signal("embodied_local_outcome_emitted"):
        bus.embodied_local_outcome_emitted.connect(_on_embodied_local_outcome_emitted)
    if bus and bus.has_signal("embodied_resync_request_emitted"):
        bus.embodied_resync_request_emitted.connect(_on_embodied_resync_request_emitted)

func is_backend_open() -> bool:
    return ws.get_ready_state() == WebSocketPeer.STATE_OPEN

func connect_to_backend(url: String) -> int:
    last_requested_url = url
    transport_barrier_sequence = 0
    if ws.get_ready_state() != WebSocketPeer.STATE_CLOSED:
        ws.close()
        ws = WebSocketPeer.new()
        ws.inbound_buffer_size = 1024 * 1024

    var err := ws.connect_to_url(url)
    if err == OK:
        _bus_log("backend_connect_requested:%s" % url)
        _bus_log("backend_connecting")
        last_ready_state = WebSocketPeer.STATE_CONNECTING
    else:
        _bus_log("backend_connect_failed:%s:%s" % [url, err])
        _bus_emit("backend_connection_failed", [url, err])
        last_ready_state = WebSocketPeer.STATE_CLOSED
    return err

func send_envelope(envelope: Dictionary) -> int:
    if ws.get_ready_state() != WebSocketPeer.STATE_OPEN:
        _bus_log("backend_send_skipped:not_open")
        return ERR_UNCONFIGURED

    var err := ws.send_text(JSON.stringify(envelope))
    if err == OK:
        _bus_log("backend_send:%s" % envelope.get("message_type", "unknown"))
    else:
        _bus_log("backend_send_failed:%s" % err)
    return err

func send_transport_barrier() -> Dictionary:
    if ws.get_ready_state() != WebSocketPeer.STATE_OPEN:
        return {}
    transport_barrier_sequence += 1
    var producer_ts: int = Time.get_ticks_msec()
    var request_id: String = "transport_barrier:%s:%s" % [producer_ts, transport_barrier_sequence]
    var err: int = send_envelope(
        {
            "message_type": "transport_barrier",
            "payload": {
                "request_id": request_id,
                "producer_ts": producer_ts,
            },
        }
    )
    if err != OK:
        return {}
    return {"request_id": request_id, "producer_ts": producer_ts}

func close_backend_connection() -> void:
    if ws.get_ready_state() == WebSocketPeer.STATE_CLOSED:
        return
    ws.close()
    _handle_state_transition()

func _process(_delta: float) -> void:
    ws.poll()
    if ws.get_ready_state() == WebSocketPeer.STATE_CLOSED and last_ready_state == WebSocketPeer.STATE_CLOSED:
        return

    _handle_state_transition()

    while ws.get_available_packet_count() > 0:
        var raw_text := ws.get_packet().get_string_from_utf8()
        _dispatch_message(raw_text)

    _handle_state_transition()

func _handle_state_transition() -> void:
    var state := ws.get_ready_state()
    if state == last_ready_state:
        return

    last_ready_state = state
    match state:
        WebSocketPeer.STATE_CONNECTING:
            _bus_log("backend_connecting")
        WebSocketPeer.STATE_OPEN:
            _bus_log("backend_connected:%s" % last_requested_url)
            _bus_emit("backend_connected", [last_requested_url])
        WebSocketPeer.STATE_CLOSING:
            _bus_log("backend_closing")
        WebSocketPeer.STATE_CLOSED:
            _bus_log("backend_closed:%s" % ws.get_close_code())
            _bus_emit("backend_disconnected", [ws.get_close_code()])

func _dispatch_message(raw_text: String) -> void:
    _bus_log("backend_message_raw:%s" % raw_text)
    var parsed: Variant = JSON.parse_string(raw_text)
    if typeof(parsed) != TYPE_DICTIONARY:
        _bus_log("backend_message_parse_failed")
        return

    var parsed_dict: Dictionary = parsed
    var message_type: String = str(parsed_dict.get("message_type", ""))
    var payload: Dictionary = parsed_dict.get("payload", {})
    _bus_log("backend_message_type:%s" % message_type)

    match message_type:
        "ack":
            _bus_emit("backend_ack_received", [payload])
            _bus_log("backend_ack")
        "dialogue_response":
            _bus_emit("dialogue_received", [payload])
        "dialogue_stream_start":
            _bus_emit("dialogue_stream_started", [payload])
        "dialogue_stream_delta":
            _bus_emit("dialogue_stream_delta_received", [payload])
        "dialogue_stream_end":
            _bus_emit("dialogue_stream_ended", [payload])
        "action_request":
            _bus_log("action_request:%s" % JSON.stringify(payload))
            _bus_emit("action_request_received", [payload])
        "focus_state":
            _bus_log("focus_state:%s" % JSON.stringify(payload))
            _bus_emit("focus_state_received", [payload])
        "conversation_candidate_event":
            _bus_log("conversation_candidate_event:%s" % JSON.stringify(payload))
            _bus_emit("conversation_candidate_received", [payload])
        "character_runtime_state_snapshot":
            _bus_log("character_runtime_state_snapshot:%s" % JSON.stringify(payload))
            _bus_emit("character_runtime_state_snapshot_received", [payload])
        "character_runtime_state_delta":
            _bus_log("character_runtime_state_delta:%s" % JSON.stringify(payload))
            _bus_emit("character_runtime_state_delta_received", [payload])
        "character_agent_output":
            _bus_log("character_agent_output:%s" % JSON.stringify(payload))
            _bus_emit("character_agent_output_received", [payload])
        "character_agent_execution":
            _bus_log("character_agent_execution:%s" % JSON.stringify(payload))
            _bus_emit("character_agent_execution_received", [payload])
        "character_agent_debug_snapshot":
            _bus_log("character_agent_debug_snapshot:%s" % JSON.stringify(payload))
            _bus_emit("character_agent_debug_snapshot_received", [payload])
        "character_agent_debug_event":
            _bus_log("character_agent_debug_event:%s" % JSON.stringify(payload))
            _bus_emit("character_agent_debug_event_received", [payload])
        "siming_debug_snapshot":
            _bus_log("siming_debug_snapshot:%s" % JSON.stringify(payload))
            _bus_emit("siming_debug_snapshot_received", [payload])
        "siming_debug_event":
            _bus_log("siming_debug_event:%s" % JSON.stringify(payload))
            _bus_emit("siming_debug_event_received", [payload])
        "world_outcome_trace":
            _bus_log("world_outcome_trace:%s" % JSON.stringify(payload))
            _bus_emit("world_outcome_trace_received", [payload])
        "scheduling_round_trace":
            _bus_log("scheduling_round_trace:%s" % JSON.stringify(payload))
            _bus_emit("scheduling_round_trace_received", [payload])
        "script_beat_event":
            _bus_log("script_beat_event:%s" % JSON.stringify(payload))
            _bus_emit("script_beat_event_received", [payload])
        "state_machine_transition":
            _bus_log("state_machine_transition:%s" % JSON.stringify(payload))
            _bus_emit("state_machine_transition_received", [payload])
        "world_result":
            _bus_emit("world_result_received", [payload])
        "siming_output":
            _bus_emit("siming_output_received", [payload])
        "authority_event":
            _dispatch_authority_event(payload)
        "embodied_controller_bound":
            _bus_log("embodied_controller_bound:%s" % JSON.stringify(payload))
            _bus_emit("embodied_controller_bound_received", [payload])
        "embodied_action_request":
            _bus_log("embodied_action_request:%s" % JSON.stringify(payload))
            _bus_emit("embodied_action_request_received", [payload])
        "embodied_settlement_result":
            _bus_log("embodied_settlement_result:%s" % JSON.stringify(payload))
            _bus_emit("embodied_settlement_result_received", [payload])
        "embodied_cancel_directive":
            _bus_log("embodied_cancel_directive:%s" % JSON.stringify(payload))
            _bus_emit("embodied_cancel_directive_received", [payload])
        "embodied_resync_projection":
            _bus_log("embodied_resync_projection:%s" % JSON.stringify(payload))
            _bus_emit("embodied_resync_projection_received", [payload])
        "embodied_interaction_session_event":
            _bus_log("embodied_interaction_session_event:%s" % JSON.stringify(payload))
            _bus_emit("embodied_interaction_session_event_received", [payload])
        "embodied_handoff_event":
            _bus_log("embodied_handoff_event:%s" % JSON.stringify(payload))
            _bus_emit("embodied_handoff_event_received", [payload])
        "embodied_carry_place_event":
            _bus_log("embodied_carry_place_event:%s" % JSON.stringify(payload))
            _bus_emit("embodied_carry_place_event_received", [payload])
        "embodied_pickup_result":
            _bus_log("embodied_pickup_result:%s" % JSON.stringify(payload))
            _bus_emit("embodied_pickup_result_received", [payload])
        "embodied_inventory_stow_result":
            _bus_log("embodied_inventory_stow_result:%s" % JSON.stringify(payload))
            _bus_emit("embodied_inventory_stow_result_received", [payload])
        "embodied_inventory_retrieve_result":
            _bus_log("embodied_inventory_retrieve_result:%s" % JSON.stringify(payload))
            _bus_emit("embodied_inventory_retrieve_result_received", [payload])
        "websocket_session_bound":
            _bus_log("websocket_session_bound:%s" % JSON.stringify(payload))
            _bus_emit("websocket_session_bound_received", [payload])
        "gameplay_runtime_state_projection":
            var projection := parsed_dict.duplicate(true)
            projection.erase("message_type")
            _bus_log("gameplay_runtime_state_projection:%s" % JSON.stringify(projection))
            _bus_emit("gameplay_runtime_state_projection_received", [projection])
        _:
            _bus_log("backend_message:%s" % message_type)

func _dispatch_authority_event(payload: Dictionary) -> void:
    _bus_emit("authority_event_received", [payload])
    var event_type := str(payload.get("event_type", ""))
    match event_type:
        "siming.visual_observability_request":
            _bus_log("siming_visual_observability_request:%s" % JSON.stringify(payload))
            _bus_emit("siming_visual_observability_requested", [payload])
        _:
            _bus_log("authority_event_unhandled:%s" % event_type)
            _bus_emit("authority_event_unhandled", [payload])

func _on_character_actor_status_emitted(payload: Dictionary) -> void:
    if ws.get_ready_state() != WebSocketPeer.STATE_OPEN:
        return
    send_envelope(
        {
            "message_type": "character_actor_status",
            "payload": payload,
        }
    )

func _on_embodied_phase_event_emitted(payload: Dictionary) -> void:
    if ws.get_ready_state() != WebSocketPeer.STATE_OPEN:
        return
    send_envelope(
        {
            "message_type": "embodied_phase_event",
            "payload": payload,
        }
    )

func _on_embodied_local_outcome_emitted(payload: Dictionary) -> void:
    if ws.get_ready_state() != WebSocketPeer.STATE_OPEN:
        return
    send_envelope(
        {
            "message_type": "embodied_local_outcome",
            "payload": payload,
        }
    )

func _on_embodied_resync_request_emitted(payload: Dictionary) -> void:
    if ws.get_ready_state() != WebSocketPeer.STATE_OPEN:
        return
    send_envelope(
        {
            "message_type": "embodied_resync_request",
            "payload": payload,
        }
    )

func _get_bus() -> Node:
    return get_node_or_null("/root/LocalPresentationBus")

func _bus_log(message: String) -> void:
    var bus := _get_bus()
    if bus and bus.has_method("log_debug"):
        bus.log_debug(message)

func _bus_emit(signal_name: StringName, args: Array = []) -> void:
    var bus := _get_bus()
    if bus and bus.has_signal(signal_name):
        bus.emit_signal(signal_name, args[0]) if args.size() == 1 else bus.emit_signal(signal_name, args[0], args[1])
