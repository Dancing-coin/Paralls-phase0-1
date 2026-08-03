extends Node

const CONSUMER := preload("res://scripts/interaction/InteractionSessionSlotConsumer.gd")
const REPORT_PATH := ".harness/verification/embodied-interaction-session-godot-runtime.json"
const VERIFIED_MARKER := "embodied_interaction_session_probe:verified=true"

var _emitted_observations: Array[Dictionary] = []
var _backend_session_events: Array[Dictionary] = []
var _backend_acks: Array[Dictionary] = []


func _ready() -> void:
	call_deferred("_run_probe")


func _run_probe() -> void:
	var bus := get_node_or_null("/root/LocalPresentationBus")
	var consumer: Variant = CONSUMER.new()
	consumer.name = "InteractionSessionSlotConsumer"
	add_child(consumer)
	consumer.configure("character:maya")
	consumer.participant_observation_emitted.connect(_on_participant_observation_emitted)

	var proposal: Dictionary = consumer.consume_authority_event(_event("embodied.interaction_session.proposed", 1, "awaiting_responses"))
	var authorized: Dictionary = consumer.consume_authority_event(_event("embodied.interaction_session.authorized", 2, "authorized", true))
	var realizing: Dictionary = consumer.consume_authority_event(_event("embodied.interaction_session.realizing", 3, "realizing", true))
	var observation: Dictionary = consumer.build_terminal_participation_observation("completed")
	var private_rejection: Dictionary = consumer.consume_authority_event(_event("embodied.interaction_session.authorized", 4, "authorized", true, true))
	var interrupted: Dictionary = consumer.consume_authority_event(_event("embodied.interaction_session.interrupted", 5, "interrupted", true))
	var late_observation: Dictionary = consumer.build_terminal_participation_observation("completed")

	var bus_signal_ok := bus != null and bus.has_signal("embodied_interaction_session_event_received")
	var bridge_source := FileAccess.get_file_as_string("res://scripts/autoload/BackendBridge.gd")
	var bridge_route_ok := bridge_source.contains("\"embodied_interaction_session_event\"")
	var session_route_index := bridge_source.find("_bus_emit(\"embodied_interaction_session_event_received\"")
	var route_tail := bridge_source.substr(session_route_index, 160) if session_route_index >= 0 else ""
	var bridge_legacy_reuse := route_tail.contains("character_actor_status")
	var backend_url := OS.get_environment("EMBODIED_INTERACTION_SESSION_BACKEND_URL")
	var live_backend := await _run_backend_bridge_probe(backend_url)
	var ok: bool = (
		bool(proposal.get("accepted", false))
		and bool(authorized.get("accepted", false))
		and bool(realizing.get("accepted", false))
		and bool(observation.get("accepted", false))
		and not bool(private_rejection.get("accepted", false))
		and str(private_rejection.get("error_code", "")) == "private_terms_rejected"
		and bool(interrupted.get("accepted", false))
		and not bool(late_observation.get("accepted", false))
		and str(late_observation.get("error_code", "")) == "session_not_realizing"
		and consumer.reservation_state == "released"
		and _emitted_observations.size() == 1
		and bus_signal_ok
		and bridge_route_ok
		and not bridge_legacy_reuse
		and bool(live_backend.get("accepted", backend_url == ""))
	)
	var report := {
		"status": "godot-runtime-interaction-session-verified" if ok else "godot-runtime-interaction-session-failed",
		"bus_signal_ok": bus_signal_ok,
		"bridge_route_ok": bridge_route_ok,
		"bridge_legacy_reuse": bridge_legacy_reuse,
		"live_backend": live_backend,
		"proposal": proposal,
		"authorized": authorized,
		"realizing": realizing,
		"participant_observation_emitted": observation,
		"private_terms_rejected": private_rejection,
		"interrupted": interrupted,
		"late_observation": late_observation,
		"consumer_state": {
			"session_id": consumer.session_id,
			"participant_ref": consumer.participant_ref,
			"state": consumer.state,
			"slot_id": consumer.slot_id,
			"reservation_ref": consumer.reservation_ref,
			"reservation_state": consumer.reservation_state,
			"last_global_sequence": consumer.last_global_sequence,
			"accepted_event_count": consumer.accepted_event_count,
			"rejected_event_count": consumer.rejected_event_count,
			"private_terms_rejected": consumer.private_terms_rejected,
			"event_trace": consumer.event_trace,
		},
		"emitted_observations": _emitted_observations,
	}
	var report_path := _write_json(REPORT_PATH, report)
	print("embodied_interaction_session_probe:artifact=%s" % report_path)
	print(VERIFIED_MARKER if ok else "embodied_interaction_session_probe:verified=false")
	get_tree().quit(0 if ok else 1)


func _on_participant_observation_emitted(payload: Dictionary) -> void:
	_emitted_observations.append(payload)


func _on_backend_session_event_received(payload: Dictionary) -> void:
	_backend_session_events.append(payload)


func _on_backend_ack_received(payload: Dictionary) -> void:
	_backend_acks.append(payload)


func _run_backend_bridge_probe(backend_url: String) -> Dictionary:
	if backend_url == "":
		return {"accepted": true, "skipped": true, "reason": "backend_url_not_configured"}
	var bus := get_node_or_null("/root/LocalPresentationBus")
	var bridge := get_node_or_null("/root/BackendBridge")
	if bus == null:
		return {"accepted": false, "error_code": "local_presentation_bus_missing"}
	if bridge == null:
		return {"accepted": false, "error_code": "backend_bridge_missing"}
	var live_consumer: Variant = CONSUMER.new()
	live_consumer.name = "InteractionSessionLiveConsumer"
	add_child(live_consumer)
	live_consumer.configure("character:maya")
	_backend_session_events.clear()
	_backend_acks.clear()
	if bus.has_signal("embodied_interaction_session_event_received"):
		bus.embodied_interaction_session_event_received.connect(live_consumer.consume_authority_event)
		if not bus.embodied_interaction_session_event_received.is_connected(_on_backend_session_event_received):
			bus.embodied_interaction_session_event_received.connect(_on_backend_session_event_received)
	if bus.has_signal("backend_ack_received") and not bus.backend_ack_received.is_connected(_on_backend_ack_received):
		bus.backend_ack_received.connect(_on_backend_ack_received)

	var connect_err: int = bridge.connect_to_backend(backend_url)
	if connect_err != OK:
		return {"accepted": false, "error_code": "connect_failed", "connect_err": connect_err}
	var connect_deadline := Time.get_ticks_msec() + 3000
	while Time.get_ticks_msec() < connect_deadline and not bridge.is_backend_open():
		await get_tree().process_frame
	if not bridge.is_backend_open():
		return {"accepted": false, "error_code": "connect_timeout", "url": backend_url}

	var send_err: int = bridge.send_envelope(
		{
			"message_type": "embodied_interaction_session_probe",
			"payload": {
				"session_id": "session:handshake:godot-websocket",
				"semantic_action": "handshake",
				"initiator_ref": "character:siming",
				"participant_refs": ["character:siming", "character:maya"],
				"target_refs": ["character:maya"],
				"participant_private_terms": {
					"character:siming": {"relationship_note": "private initiator memory"},
					"character:maya": {"consent_note": "private target context"},
				},
			},
		}
	)
	if send_err != OK:
		return {"accepted": false, "error_code": "send_failed", "send_err": send_err}

	var receive_deadline := Time.get_ticks_msec() + 5000
	while Time.get_ticks_msec() < receive_deadline:
		if _backend_session_events.size() >= 4 and live_consumer.state == "realizing":
			break
		await get_tree().process_frame
	bridge.close_backend_connection()
	var ack_ok := false
	for ack: Dictionary in _backend_acks:
		if bool(ack.get("accepted", false)) and str(ack.get("route", "")) == "embodied_interaction_session":
			ack_ok = true
	var privacy_ok := (
		not str(_backend_session_events).contains("participant_private_terms")
		and not str(_backend_session_events).contains("private target context")
		and not str(_backend_session_events).contains("character_actor_status")
	)
	var sequence_ok := _backend_session_events.size() >= 4
	if sequence_ok:
		var first_sequence := int(_backend_session_events[0].get("global_sequence", 0))
		if first_sequence < 1:
			sequence_ok = false
		for index: int in range(4):
			var event_payload: Dictionary = _backend_session_events[index]
			if int(event_payload.get("global_sequence", 0)) != first_sequence + index:
				sequence_ok = false
	var accepted: bool = (
		ack_ok
		and _backend_session_events.size() >= 4
		and live_consumer.state == "realizing"
		and live_consumer.slot_id != ""
		and sequence_ok
		and privacy_ok
	)
	return {
		"accepted": accepted,
		"url": backend_url,
		"ack_ok": ack_ok,
		"received_event_count": _backend_session_events.size(),
		"consumer_state": live_consumer.state,
		"slot_id": live_consumer.slot_id,
		"last_global_sequence": live_consumer.last_global_sequence,
		"sequence_ok": sequence_ok,
		"privacy_ok": privacy_ok,
		"event_types": _backend_session_events.map(func(item: Dictionary) -> String: return str(item.get("event_type", ""))),
	}


func _event(event_type: String, sequence: int, state: String, include_slot: bool = false, include_private: bool = false) -> Dictionary:
	var payload := {
		"event_type": event_type,
		"session_id": "session:handshake:godot-runtime",
		"semantic_action": "handshake",
		"state": state,
		"safe_phase": state,
		"sync_status": state,
		"participant_refs": ["character:siming", "character:maya"],
		"target_refs": ["character:maya"],
		"global_sequence": sequence,
		"stream_revision": sequence,
		"transaction_id": "tx:session:handshake:godot:%s" % sequence,
		"event_id": "evt:session:handshake:godot:%s" % sequence,
	}
	if include_slot:
		payload["slot_assignments"] = [
			{
				"slot_id": "slot:session:handshake:godot-runtime:1",
				"participant_ref": "character:siming",
				"role": "initiator",
				"reservation_ref": "reservation:session:handshake:godot-runtime:character:siming",
				"reservation_state": "reserved",
			},
			{
				"slot_id": "slot:session:handshake:godot-runtime:2",
				"participant_ref": "character:maya",
				"role": "counterparty",
				"reservation_ref": "reservation:session:handshake:godot-runtime:character:maya",
				"reservation_state": "reserved",
			},
		]
	if include_private:
		payload["participant_private_terms"] = {"character:maya": {"consent_note": "hidden"}}
	return payload


func _write_json(relative_path: String, payload: Dictionary) -> String:
	var path := ProjectSettings.globalize_path("res://" + relative_path)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return ""
	file.store_string(JSON.stringify(payload, "\t"))
	file.close()
	return path
