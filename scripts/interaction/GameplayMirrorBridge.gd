extends Node

class_name GameplayMirrorBridge

## Transport/presentation bridge only. The backend still owns session scope and truth.

var _session_enrollment: Dictionary = {}
var _bound_session_ref := ""
var _allowed_actor_refs: Array[String] = []
var _consumers_by_actor: Dictionary = {}
var _supports_receipt := false


func _ready() -> void:
	var bus := _get_bus()
	if bus and bus.has_signal("websocket_session_bound_received"):
		bus.websocket_session_bound_received.connect(_on_session_bound)
	if bus and bus.has_signal("gameplay_runtime_state_projection_received"):
		bus.gameplay_runtime_state_projection_received.connect(_on_projection)
	if bus and bus.has_signal("gameplay_mirror_delivery_received"):
		bus.gameplay_mirror_delivery_received.connect(_on_delivery)
	if bus and bus.has_signal("gameplay_mirror_resync_required_received"):
		bus.gameplay_mirror_resync_required_received.connect(_on_resync_required)
	if bus and bus.has_signal("backend_disconnected"):
		bus.backend_disconnected.connect(_on_backend_disconnected)


func set_session_enrollment(enrollment: Dictionary) -> void:
	# Credential material comes from a launcher or approved local bootstrap, never scene data.
	_session_enrollment = enrollment.duplicate(true)


func has_pending_enrollment() -> bool:
	return not _session_enrollment.is_empty()


func load_session_enrollment_from_environment() -> int:
	var raw_enrollment := OS.get_environment("PARALLS_GAMEPLAY_MIRROR_ENROLLMENT_JSON")
	if raw_enrollment.is_empty():
		return ERR_UNCONFIGURED
	var parsed: Variant = JSON.parse_string(raw_enrollment)
	if typeof(parsed) != TYPE_DICTIONARY:
		return ERR_INVALID_DATA
	var enrollment: Dictionary = parsed
	if enrollment.size() != 3:
		return ERR_INVALID_DATA
	if str(enrollment.get("credential_kind", "")) != "trusted_local_launch":
		return ERR_INVALID_DATA
	if str(enrollment.get("credential", "")).is_empty():
		return ERR_INVALID_DATA
	if int(enrollment.get("protocol_version", 0)) < 1:
		return ERR_INVALID_DATA
	set_session_enrollment(enrollment)
	return OK


func register_consumer(actor_ref: String, consumer: GameplayRuntimeStateMirrorConsumer) -> void:
	if actor_ref.is_empty() or consumer == null:
		return
	_consumers_by_actor[actor_ref] = consumer


func unregister_consumer(actor_ref: String) -> void:
	_consumers_by_actor.erase(actor_ref)


func bind_session() -> int:
	if _session_enrollment.is_empty():
		return ERR_UNCONFIGURED
	var payload := _session_enrollment.duplicate(true)
	payload["capability_offer"] = {
		"protocol_version": 2,
		"supports_snapshot": true,
		"supports_delta": false,
		"supports_receipt": true,
		"projection_schemas": ["gameplay_runtime_state.godot.v1"],
	}
	return _bridge().send_envelope({"message_type": "websocket_session_bind", "payload": payload})


func request_subscription(actor_ref: String) -> int:
	if not _allowed_actor_refs.has(actor_ref):
		return ERR_UNAUTHORIZED
	return _bridge().send_envelope({"message_type": "gameplay_mirror_subscribe", "payload": {"actor_ref": actor_ref}})


func request_snapshot(actor_ref: String) -> int:
	if not _allowed_actor_refs.has(actor_ref):
		return ERR_UNAUTHORIZED
	return _bridge().send_envelope({"message_type": "gameplay_mirror_snapshot_request", "payload": {"actor_ref": actor_ref}})


func unsubscribe(actor_ref: String) -> int:
	if not _allowed_actor_refs.has(actor_ref):
		return ERR_UNAUTHORIZED
	return _bridge().send_envelope({"message_type": "gameplay_mirror_unsubscribe", "payload": {"actor_ref": actor_ref}})


func _on_session_bound(payload: Dictionary) -> void:
	_bound_session_ref = str(payload.get("session_ref", ""))
	_session_enrollment.clear()
	_allowed_actor_refs.clear()
	_supports_receipt = bool((payload.get("capability_profile", {}) as Dictionary).get("supports_receipt", false))
	for value: Variant in payload.get("allowed_actor_refs", []):
		var actor_ref := str(value)
		if not actor_ref.is_empty():
			_allowed_actor_refs.append(actor_ref)


func _on_projection(payload: Dictionary) -> void:
	var actor_ref := str(payload.get("actor_ref", ""))
	if actor_ref.is_empty() or not _allowed_actor_refs.has(actor_ref):
		return
	var consumer: GameplayRuntimeStateMirrorConsumer = _consumers_by_actor.get(actor_ref)
	if consumer == null:
		return
	consumer.consume_projection(payload)


func _on_delivery(payload: Dictionary) -> void:
	var actor_ref := str(payload.get("actor_ref", ""))
	if actor_ref.is_empty() or not _allowed_actor_refs.has(actor_ref):
		return
	var consumer: GameplayRuntimeStateMirrorConsumer = _consumers_by_actor.get(actor_ref)
	if consumer == null:
		return
	var result := consumer.consume_delivery(payload)
	if consumer.resync_required:
		# The backend remains the only source for the replacement snapshot.
		request_snapshot(actor_ref)
	if _supports_receipt and bool(result.get("accepted", false)):
		_bridge().send_envelope({
			"message_type": "gameplay_mirror_receipt",
			"payload": {
				"connection_epoch": int(payload.get("connection_epoch", 0)),
				"delivery_sequence": int(payload.get("delivery_sequence", 0)),
			},
		})


func _on_resync_required(payload: Dictionary) -> void:
	var actor_ref := str(payload.get("actor_ref", ""))
	if actor_ref.is_empty() or not _allowed_actor_refs.has(actor_ref):
		return
	var consumer: GameplayRuntimeStateMirrorConsumer = _consumers_by_actor.get(actor_ref)
	if consumer == null:
		return
	consumer.mark_resync_required()
	request_snapshot(actor_ref)


func _on_backend_disconnected(_code: int) -> void:
	_bound_session_ref = ""
	_allowed_actor_refs.clear()
	_supports_receipt = false
	for consumer: Variant in _consumers_by_actor.values():
		if consumer is GameplayRuntimeStateMirrorConsumer:
			(consumer as GameplayRuntimeStateMirrorConsumer).clear_projection()


func _bridge() -> Node:
	return get_node_or_null("/root/BackendBridge")


func _get_bus() -> Node:
	return get_node_or_null("/root/LocalPresentationBus")
