extends Node

const CONSUMER := preload("res://scripts/interaction/CarryPlaceMirrorConsumer.gd")
const REPORT_PATH := ".harness/verification/embodied-carry-place-godot-runtime.json"
const VERIFIED_MARKER := "embodied_carry_place_probe:verified=true"

var _backend_carry_place_events: Array[Dictionary] = []
var _backend_acks: Array[Dictionary] = []


func _ready() -> void:
	call_deferred("_run_probe")


func _run_probe() -> void:
	var consumer: Variant = CONSUMER.new()
	consumer.name = "CarryPlaceMirrorConsumer"
	add_child(consumer)

	var local_hint: Dictionary = consumer.apply_local_carry_hint({
		"asset_ref": "item:crate_01",
		"carried_by_ref": "character:siming",
		"intended_drop_target_ref": "world:anchor:floor_slot_01",
		"source_ref": "godot:probe:local_hint",
	})
	var unsafe_directive: Dictionary = _carry_place_event(1)
	unsafe_directive["placement_directive"]["authority_only"] = false
	var unsafe_rejection: Dictionary = consumer.consume_authority_event(unsafe_directive)
	var authority_event: Dictionary = consumer.consume_authority_event(_carry_place_event(2))
	var forbidden_event: Dictionary = _carry_place_event(3)
	forbidden_event["world_truth_claim"] = {"custody_holder_ref": "world:anchor:floor_slot_01"}
	var forbidden_rejection: Dictionary = consumer.consume_authority_event(forbidden_event)
	var backend_url := OS.get_environment("EMBODIED_CARRY_PLACE_BACKEND_URL")
	var live_backend: Dictionary = await _run_backend_bridge_probe(backend_url)
	var ok: bool = (
		bool(local_hint.get("accepted", false))
		and bool(local_hint.get("authority_mutation", true)) == false
		and consumer.custody_holder_ref == "world:anchor:floor_slot_01"
		and str(unsafe_rejection.get("error_code", "")) == "authority_only_directive_required"
		and bool(authority_event.get("accepted", false))
		and str(forbidden_rejection.get("error_code", "")) == "forbidden_projection_field"
		and bool(live_backend.get("accepted", backend_url == ""))
	)
	var report := {
		"status": "godot-runtime-carry-place-verified" if ok else "godot-runtime-carry-place-failed",
		"local_hint": local_hint,
		"unsafe_rejection": unsafe_rejection,
		"authority_event": authority_event,
		"forbidden_rejection": forbidden_rejection,
		"consumer_state": {
			"asset_ref": consumer.asset_ref,
			"carried_by_ref": consumer.carried_by_ref,
			"drop_target_ref": consumer.drop_target_ref,
			"custody_holder_ref": consumer.custody_holder_ref,
			"owner_ref": consumer.owner_ref,
			"authority_transaction_id": consumer.authority_transaction_id,
			"last_global_sequence": consumer.last_global_sequence,
			"accepted_event_count": consumer.accepted_event_count,
			"rejected_event_count": consumer.rejected_event_count,
			"event_trace": consumer.event_trace,
		},
		"live_backend": live_backend,
	}
	var report_path := _write_json(REPORT_PATH, report)
	print("embodied_carry_place_probe:artifact=%s" % report_path)
	print(VERIFIED_MARKER if ok else "embodied_carry_place_probe:verified=false")
	get_tree().quit(0 if ok else 1)


func _on_backend_carry_place_event_received(payload: Dictionary) -> void:
	_backend_carry_place_events.append(payload)


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
	live_consumer.name = "CarryPlaceLiveConsumer"
	add_child(live_consumer)
	_backend_carry_place_events.clear()
	_backend_acks.clear()
	if bus.has_signal("embodied_carry_place_event_received"):
		bus.embodied_carry_place_event_received.connect(live_consumer.consume_authority_event)
		if not bus.embodied_carry_place_event_received.is_connected(_on_backend_carry_place_event_received):
			bus.embodied_carry_place_event_received.connect(_on_backend_carry_place_event_received)
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

	var send_err: int = bridge.send_envelope({
		"message_type": "embodied_grab_carry_place_probe",
		"payload": {
			"session_id": "session:carry-place:godot-websocket:1",
			"asset_ref": "item:crate_01",
			"actor_ref": "character:siming",
			"source_holder_ref": "world:anchor:table_01",
			"drop_target_ref": "world:anchor:floor_slot_01",
		},
	})
	if send_err != OK:
		return {"accepted": false, "error_code": "send_failed", "send_err": send_err}

	var receive_deadline := Time.get_ticks_msec() + 5000
	while Time.get_ticks_msec() < receive_deadline:
		if _backend_carry_place_events.size() >= 1 and live_consumer.custody_holder_ref == "world:anchor:floor_slot_01":
			break
		await get_tree().process_frame
	bridge.close_backend_connection()
	var ack_ok := false
	for ack: Dictionary in _backend_acks:
		if bool(ack.get("accepted", false)) and str(ack.get("route", "")) == "embodied_carry_place_authority":
			ack_ok = true
	var privacy_ok := (
		not str(_backend_carry_place_events).contains("world_truth_claim")
		and not str(_backend_carry_place_events).contains("participant_private_terms")
		and not str(_backend_carry_place_events).contains("character_actor_status")
	)
	var accepted: bool = (
		ack_ok
		and _backend_carry_place_events.size() >= 1
		and live_consumer.custody_holder_ref == "world:anchor:floor_slot_01"
		and live_consumer.drop_target_ref == "world:anchor:floor_slot_01"
		and privacy_ok
	)
	return {
		"accepted": accepted,
		"url": backend_url,
		"ack_ok": ack_ok,
		"received_event_count": _backend_carry_place_events.size(),
		"custody_holder_ref": live_consumer.custody_holder_ref,
		"drop_target_ref": live_consumer.drop_target_ref,
		"last_global_sequence": live_consumer.last_global_sequence,
		"privacy_ok": privacy_ok,
	}


func _carry_place_event(sequence: int) -> Dictionary:
	return {
		"event_type": "embodied.place.settled",
		"session_id": "session:carry-place:godot-runtime:1",
		"asset_ref": "item:crate_01",
		"actor_ref": "character:siming",
		"source_holder_ref": "world:anchor:table_01",
		"drop_target_ref": "world:anchor:floor_slot_01",
		"custody_holder_ref": "world:anchor:floor_slot_01",
		"owner_ref": "character:siming",
		"settlement_ref": "settlement:session:carry-place:godot-runtime:1",
		"transaction_id": "tx:carry-place:godot:%s" % sequence,
		"event_id": "evt:carry-place:godot:%s" % sequence,
		"stream_revision": sequence,
		"global_sequence": sequence,
		"placement_directive": {
			"mode": "place_for_presentation",
			"asset_ref": "item:crate_01",
			"place_at_ref": "world:anchor:floor_slot_01",
			"authority_only": true,
		},
	}


func _write_json(relative_path: String, payload: Dictionary) -> String:
	var path := ProjectSettings.globalize_path("res://" + relative_path)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return ""
	file.store_string(JSON.stringify(payload, "\t"))
	file.close()
	return path
