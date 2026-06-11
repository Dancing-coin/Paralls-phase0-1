extends Node

var ws := WebSocketPeer.new()
var last_ready_state := WebSocketPeer.STATE_CLOSED
var last_requested_url := ""

func is_backend_open() -> bool:
    return ws.get_ready_state() == WebSocketPeer.STATE_OPEN

func connect_to_backend(url: String) -> int:
    last_requested_url = url
    if ws.get_ready_state() != WebSocketPeer.STATE_CLOSED:
        ws.close()
        ws = WebSocketPeer.new()

    var err := ws.connect_to_url(url)
    if err == OK:
        _bus_log("backend_connect_requested:%s" % url)
    else:
        _bus_log("backend_connect_failed:%s:%s" % [url, err])
        _bus_emit("backend_connection_failed", [url, err])

    # Force the next _process poll to emit the actual transition even when
    # the socket reaches OPEN immediately after connect_to_url().
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
        "state_machine_transition":
            _bus_log("state_machine_transition:%s" % JSON.stringify(payload))
            _bus_emit("state_machine_transition_received", [payload])
        "world_result":
            _bus_emit("world_result_received", [payload])
        "siming_output":
            _bus_emit("siming_output_received", [payload])
        _:
            _bus_log("backend_message:%s" % message_type)

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
