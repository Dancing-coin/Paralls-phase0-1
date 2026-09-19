extends Node

class_name GameplayMirrorBridge

## 连接与表现桥；后端持有会话授权和权威状态。

signal projection_applied(actor_ref: String, snapshot: Dictionary)
signal projection_removed(actor_ref: String)

const MAX_ACTIVE_ACTORS := 160

var _session_enrollment: Dictionary = {}
var _bound_session_ref := ""
var _allowed_actor_refs: Array[String] = []
var _allowed_government_drought_advisory_jurisdiction_refs: Array[String] = []
var _consumers_by_actor: Dictionary = {}
var _government_drought_advisory_consumers: Dictionary = {}
var _supports_receipt := false
var _connection_epoch := 0
var _last_delivery_sequence := 0
var connection_gap_count := 0


func _ready() -> void:
	var bus := _get_bus()
	if bus and bus.has_signal("websocket_session_bound_received"):
		bus.websocket_session_bound_received.connect(_on_session_bound)
	if bus and bus.has_signal("websocket_session_revoked_received"):
		bus.websocket_session_revoked_received.connect(_on_session_revoked)
	if bus and bus.has_signal("websocket_session_renewal_enrollment_received"):
		bus.websocket_session_renewal_enrollment_received.connect(_on_renewal_enrollment)
	if bus and bus.has_signal("gameplay_runtime_state_projection_received"):
		bus.gameplay_runtime_state_projection_received.connect(_on_projection)
	if bus and bus.has_signal("gameplay_mirror_delivery_received"):
		bus.gameplay_mirror_delivery_received.connect(_on_delivery)
	if bus and bus.has_signal("gameplay_mirror_resync_required_received"):
		bus.gameplay_mirror_resync_required_received.connect(_on_resync_required)
	if bus and bus.has_signal("government_drought_advisory_projection_received"):
		bus.government_drought_advisory_projection_received.connect(_on_government_drought_advisory_projection)
	if bus and bus.has_signal("government_drought_advisory_delivery_received"):
		bus.government_drought_advisory_delivery_received.connect(_on_government_drought_advisory_delivery)
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


func register_consumer(actor_ref: String, consumer: GameplayRuntimeStateMirrorConsumer) -> int:
	if actor_ref.is_empty() or consumer == null:
		return ERR_INVALID_PARAMETER
	if not _consumers_by_actor.has(actor_ref) and _consumers_by_actor.size() >= MAX_ACTIVE_ACTORS:
		return ERR_OUT_OF_MEMORY
	if _consumers_by_actor.has(actor_ref) and _consumers_by_actor[actor_ref] != consumer:
		unregister_consumer(actor_ref)
	_consumers_by_actor[actor_ref] = consumer
	return OK


func unregister_consumer(actor_ref: String) -> void:
	var consumer: GameplayRuntimeStateMirrorConsumer = _consumers_by_actor.get(actor_ref)
	if consumer != null:
		consumer.clear_projection()
	_consumers_by_actor.erase(actor_ref)
	projection_removed.emit(actor_ref)


func register_government_drought_advisory_consumer(jurisdiction_ref: String, consumer: GovernmentDroughtAdvisoryPresentationConsumer) -> void:
	if jurisdiction_ref.is_empty() or consumer == null:
		return
	_government_drought_advisory_consumers[jurisdiction_ref] = consumer


func unregister_government_drought_advisory_consumer(jurisdiction_ref: String) -> void:
	_government_drought_advisory_consumers.erase(jurisdiction_ref)


func bind_session() -> int:
	if _session_enrollment.is_empty():
		return ERR_UNCONFIGURED
	var payload := _session_enrollment.duplicate(true)
	payload["capability_offer"] = {
		"protocol_version": 2,
		"supports_snapshot": true,
		"supports_delta": true,
		"supports_receipt": true,
		"projection_schemas": ["gameplay_runtime_state.godot.v1"],
	}
	return _bridge().send_envelope({"message_type": "websocket_session_bind", "payload": payload})


func request_subscription(actor_ref: String) -> int:
	if not _allowed_actor_refs.has(actor_ref) or not _consumers_by_actor.has(actor_ref):
		return ERR_UNAUTHORIZED
	return _bridge().send_envelope({"message_type": "gameplay_mirror_subscribe", "payload": {"actor_ref": actor_ref}})


func request_snapshot(actor_ref: String) -> int:
	if not _allowed_actor_refs.has(actor_ref):
		return ERR_UNAUTHORIZED
	return _bridge().send_envelope({"message_type": "gameplay_mirror_snapshot_request", "payload": {"actor_ref": actor_ref}})


func unsubscribe(actor_ref: String) -> int:
	if not _allowed_actor_refs.has(actor_ref):
		return ERR_UNAUTHORIZED
	var result: int = _bridge().send_envelope({"message_type": "gameplay_mirror_unsubscribe", "payload": {"actor_ref": actor_ref}})
	if result == OK:
		unregister_consumer(actor_ref)
	return result


func request_government_drought_advisory_subscription(jurisdiction_ref: String) -> int:
	if not _allowed_government_drought_advisory_jurisdiction_refs.has(jurisdiction_ref):
		return ERR_UNAUTHORIZED
	return _bridge().send_envelope({"message_type": "gameplay_government_drought_advisory_subscribe", "payload": {"jurisdiction_ref": jurisdiction_ref}})


func _on_session_bound(payload: Dictionary) -> void:
	if not _positive_integer(payload.get("connection_epoch")) or str(payload.get("session_ref", "")).is_empty():
		_on_backend_disconnected(1002)
		return
	_bound_session_ref = str(payload.get("session_ref", ""))
	_connection_epoch = int(payload["connection_epoch"])
	_last_delivery_sequence = 0
	connection_gap_count = 0
	_session_enrollment.clear()
	_allowed_actor_refs.clear()
	_allowed_government_drought_advisory_jurisdiction_refs.clear()
	_supports_receipt = bool((payload.get("capability_profile", {}) as Dictionary).get("supports_receipt", false))
	for value: Variant in payload.get("allowed_actor_refs", []):
		var actor_ref := str(value)
		if not actor_ref.is_empty():
			_allowed_actor_refs.append(actor_ref)
	for value: Variant in payload.get("allowed_government_drought_advisory_jurisdiction_refs", []):
		var jurisdiction_ref := str(value)
		if not jurisdiction_ref.is_empty():
			_allowed_government_drought_advisory_jurisdiction_refs.append(jurisdiction_ref)
	for actor_ref: String in _consumers_by_actor.keys():
		if not _allowed_actor_refs.has(actor_ref):
			unregister_consumer(actor_ref)
		else:
			(_consumers_by_actor[actor_ref] as GameplayRuntimeStateMirrorConsumer).clear_projection()
			projection_removed.emit(actor_ref)
	for jurisdiction_ref: String in _government_drought_advisory_consumers.keys():
		(_government_drought_advisory_consumers[jurisdiction_ref] as GovernmentDroughtAdvisoryPresentationConsumer).clear_projection()
		if not _allowed_government_drought_advisory_jurisdiction_refs.has(jurisdiction_ref):
			_government_drought_advisory_consumers.erase(jurisdiction_ref)


func _on_projection(payload: Dictionary) -> void:
	# 裸快照仅保留离线/旧首帧兼容，不能修复已经进入顺序流的增量基线。
	if _bound_session_ref.is_empty() or _last_delivery_sequence != 0:
		return
	var actor_ref := str(payload.get("actor_ref", ""))
	if actor_ref.is_empty() or not _allowed_actor_refs.has(actor_ref):
		return
	var consumer: GameplayRuntimeStateMirrorConsumer = _consumers_by_actor.get(actor_ref)
	if consumer == null:
		return
	var result := consumer.consume_projection(payload)
	if bool(result.get("accepted", false)) and not bool(result.get("replayed", false)):
		_emit_verified_projection(actor_ref, payload)


func _on_delivery(payload: Dictionary) -> void:
	# 先消费连接位置，再按活动角色分流；退订后的在途消息不造成伪 gap。
	if not _accept_transport(payload):
		return
	var actor_ref := str(payload.get("actor_ref", ""))
	if actor_ref.is_empty() or not _allowed_actor_refs.has(actor_ref):
		return
	var consumer: GameplayRuntimeStateMirrorConsumer = _consumers_by_actor.get(actor_ref)
	if consumer == null:
		return
	var recovering := consumer.resync_required
	var result := consumer.consume_validated_delivery(payload)
	if consumer.resync_required:
		request_snapshot(actor_ref)
	if bool(result.get("accepted", false)):
		consumer.connection_epoch = _connection_epoch
		consumer.last_delivery_sequence = _last_delivery_sequence
		_send_receipt(payload)
		if payload.get("delivery_kind") != "prediction" and (recovering or not bool(result.get("replayed", false))):
			_emit_verified_projection(actor_ref, payload["payload"])


func _emit_verified_projection(actor_ref: String, payload: Dictionary) -> void:
	# consumer 已验证规范文本与候选完整快照一致；只发布这份已校验结果。
	var snapshot: Dictionary = JSON.parse_string(payload["canonical_snapshot_json"])
	projection_applied.emit(actor_ref, snapshot)


func _positive_integer(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(float(value)) and float(value) >= 1 and float(value) == floor(float(value))


func _accept_transport(payload: Dictionary) -> bool:
	if _bound_session_ref.is_empty() or not _positive_integer(payload.get("connection_epoch")) or not _positive_integer(payload.get("delivery_sequence")):
		return false
	if int(payload["connection_epoch"]) != _connection_epoch:
		return false
	var sequence := int(payload["delivery_sequence"])
	# 重复消息幂等丢弃；不再发 receipt，避免把上次拒绝的内容误记为成功。
	if sequence <= _last_delivery_sequence:
		return false
	var gap := sequence != _last_delivery_sequence + 1
	_last_delivery_sequence = sequence
	if gap:
		connection_gap_count += 1
		for actor_ref: String in _consumers_by_actor:
			var consumer: GameplayRuntimeStateMirrorConsumer = _consumers_by_actor[actor_ref]
			consumer.mark_resync_required()
			request_snapshot(actor_ref)
		for jurisdiction_ref: String in _government_drought_advisory_consumers:
			request_government_drought_advisory_subscription(jurisdiction_ref)
		return false
	return true


func _send_receipt(payload: Dictionary) -> void:
	if _supports_receipt:
		_bridge().send_envelope({"message_type": "gameplay_mirror_receipt", "payload": {
			"connection_epoch": _connection_epoch, "delivery_sequence": int(payload["delivery_sequence"]),
		}})


func _on_resync_required(payload: Dictionary) -> void:
	var actor_ref := str(payload.get("actor_ref", ""))
	if actor_ref.is_empty() or not _allowed_actor_refs.has(actor_ref):
		return
	var consumer: GameplayRuntimeStateMirrorConsumer = _consumers_by_actor.get(actor_ref)
	if consumer == null:
		return
	consumer.mark_resync_required()
	request_snapshot(actor_ref)


func _on_government_drought_advisory_projection(payload: Dictionary) -> void:
	var jurisdiction_ref := str(payload.get("jurisdiction_ref", ""))
	if jurisdiction_ref.is_empty() or not _allowed_government_drought_advisory_jurisdiction_refs.has(jurisdiction_ref):
		return
	var consumer: GovernmentDroughtAdvisoryPresentationConsumer = _government_drought_advisory_consumers.get(jurisdiction_ref)
	if consumer != null:
		consumer.consume_projection(payload)


func _on_government_drought_advisory_delivery(payload: Dictionary) -> void:
	if not _accept_transport(payload):
		return
	var jurisdiction_ref := str(payload.get("jurisdiction_ref", ""))
	if jurisdiction_ref.is_empty() or not _allowed_government_drought_advisory_jurisdiction_refs.has(jurisdiction_ref):
		return
	var consumer: GovernmentDroughtAdvisoryPresentationConsumer = _government_drought_advisory_consumers.get(jurisdiction_ref)
	if consumer == null:
		return
	var result := consumer.consume_projection(payload)
	if bool(result.get("accepted", false)):
		consumer.connection_epoch = _connection_epoch
		consumer.last_delivery_sequence = _last_delivery_sequence
		_send_receipt(payload)


func _on_session_revoked(_payload: Dictionary) -> void:
	_on_backend_disconnected(4403)


func _on_renewal_enrollment(payload: Dictionary) -> void:
	_on_backend_disconnected(1000)
	set_session_enrollment(payload)


func _on_backend_disconnected(_code: int) -> void:
	_bound_session_ref = ""
	_connection_epoch = 0
	_last_delivery_sequence = 0
	_session_enrollment.clear()
	_allowed_actor_refs.clear()
	_allowed_government_drought_advisory_jurisdiction_refs.clear()
	_supports_receipt = false
	for actor_ref: String in _consumers_by_actor.keys():
		unregister_consumer(actor_ref)
	for consumer: Variant in _government_drought_advisory_consumers.values():
		if consumer is GovernmentDroughtAdvisoryPresentationConsumer:
			(consumer as GovernmentDroughtAdvisoryPresentationConsumer).clear_projection()
	_government_drought_advisory_consumers.clear()


func _bridge() -> Node:
	return get_node_or_null("/root/BackendBridge")


func _get_bus() -> Node:
	return get_node_or_null("/root/LocalPresentationBus")
