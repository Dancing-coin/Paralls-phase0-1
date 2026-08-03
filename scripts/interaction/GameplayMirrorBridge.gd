extends Node

class_name GameplayMirrorBridge

## Transport/presentation bridge only. The backend still owns session scope and truth.

var _session_enrollment: Dictionary = {}
var _bound_session_ref := ""
var _allowed_actor_refs: Array[String] = []
var _consumers_by_actor: Dictionary = {}


func _ready() -> void:
	var bus := _get_bus()
	if bus and bus.has_signal("websocket_session_bound_received"):
		bus.websocket_session_bound_received.connect(_on_session_bound)
	if bus and bus.has_signal("gameplay_runtime_state_projection_received"):
		bus.gameplay_runtime_state_projection_received.connect(_on_projection)
	if bus and bus.has_signal("backend_disconnected"):
		bus.backend_disconnected.connect(_on_backend_disconnected)


func set_session_enrollment(enrollment: Dictionary) -> void:
	# Credential material comes from a launcher or approved local bootstrap, never scene data.
	_session_enrollment = enrollment.duplicate(true)


func register_consumer(actor_ref: String, consumer: GameplayRuntimeStateMirrorConsumer) -> void:
	if actor_ref.is_empty() or consumer == null:
		return
	_consumers_by_actor[actor_ref] = consumer


func unregister_consumer(actor_ref: String) -> void:
	_consumers_by_actor.erase(actor_ref)


func bind_session() -> int:
	if _session_enrollment.is_empty():
		return ERR_UNCONFIGURED
	return _bridge().send_envelope({"message_type": "websocket_session_bind", "payload": _session_enrollment})


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
	_allowed_actor_refs.clear()
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


func _on_backend_disconnected(_code: int) -> void:
	_bound_session_ref = ""
	_allowed_actor_refs.clear()
	for consumer: Variant in _consumers_by_actor.values():
		if consumer is GameplayRuntimeStateMirrorConsumer:
			(consumer as GameplayRuntimeStateMirrorConsumer).clear_projection()


func _bridge() -> Node:
	return get_node_or_null("/root/BackendBridge")


func _get_bus() -> Node:
	return get_node_or_null("/root/LocalPresentationBus")
