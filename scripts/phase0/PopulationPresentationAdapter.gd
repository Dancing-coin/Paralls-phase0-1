extends Node
class_name PopulationPresentationAdapter

## 使用现有 BackendBridge；本节点不创建连接，也不持有不可见人口的投影。
signal population_applied(actor_ref: String, snapshot: Dictionary)
signal membership_settled
signal subscription_failed(actor_ref: String, error_code: String)

const BRIDGE := preload("res://scripts/interaction/GameplayMirrorBridge.gd")
const CONSUMER := preload("res://scripts/interaction/GameplayRuntimeStateMirrorConsumer.gd")

@export var presenter_path: NodePath = NodePath("../PopulationPresenter")
var bridge: GameplayMirrorBridge
var presenter: PopulationPresenter
var allowed_actor_refs: Array[String] = []
var _consumers: Dictionary = {}
var _desired: Array[String] = []
var _operations: Array[Dictionary] = []
var _pending: Dictionary = {}


func _ready() -> void:
	presenter = get_node(presenter_path) as PopulationPresenter
	bridge = BRIDGE.new()
	add_child(bridge)
	bridge.projection_applied.connect(_on_projection_applied)
	bridge.projection_removed.connect(_on_projection_removed)
	bridge.load_session_enrollment_from_environment()
	var bus := get_node("/root/LocalPresentationBus")
	bus.backend_connected.connect(_on_backend_connected)
	bus.websocket_session_bound_received.connect(_on_session_bound)
	bus.websocket_session_revoked_received.connect(_on_session_ended)
	bus.websocket_session_renewal_enrollment_received.connect(_on_renewal)
	bus.backend_disconnected.connect(func(_code: int): _on_session_ended({}))
	bus.backend_ack_received.connect(_on_ack)


func _on_backend_connected(_url: String) -> void:
	if bridge.has_pending_enrollment():
		bridge.bind_session()


func _on_session_bound(payload: Dictionary) -> void:
	_operations.clear()
	_pending.clear()
	for actor_ref: String in _consumers.keys():
		_discard_consumer(actor_ref)
	allowed_actor_refs.clear()
	var granted := {}
	for value: Variant in payload.get("allowed_actor_refs", []):
		if value is String and value.begins_with("character:") and not granted.has(value):
			granted[value] = true
			allowed_actor_refs.append(value)
	allowed_actor_refs.sort()
	presenter.authorized_population = allowed_actor_refs.size()
	set_interest_window(0)


func set_interest_window(offset: int) -> int:
	if not _pending.is_empty() or not _operations.is_empty():
		return ERR_BUSY
	if allowed_actor_refs.is_empty():
		return ERR_UNAUTHORIZED
	_desired.clear()
	for index: int in range(mini(160, allowed_actor_refs.size())):
		_desired.append(allowed_actor_refs[posmod(offset + index, allowed_actor_refs.size())])
	# ACK不带actor，因此所有成员变更串行，先等待退订确认再补入新成员。
	for actor_ref: String in _consumers:
		if not _desired.has(actor_ref):
			_operations.append({"source_type": "gameplay_mirror_unsubscribe", "actor_ref": actor_ref})
	for actor_ref: String in _desired:
		if not _consumers.has(actor_ref):
			_operations.append({"source_type": "gameplay_mirror_subscribe", "actor_ref": actor_ref})
	_pump_membership()
	return OK


func _pump_membership() -> void:
	if not _pending.is_empty():
		return
	if _operations.is_empty():
		membership_settled.emit()
		return
	_pending = _operations.pop_front()
	var actor_ref: String = _pending["actor_ref"]
	var result: int
	if _pending["source_type"] == "gameplay_mirror_unsubscribe":
		result = bridge.unsubscribe(actor_ref)
		if result == OK:
			_discard_consumer(actor_ref)
	else:
		var consumer = CONSUMER.new()
		add_child(consumer)
		_consumers[actor_ref] = consumer
		result = bridge.register_consumer(actor_ref, consumer)
		if result == OK:
			result = bridge.request_subscription(actor_ref)
	if result != OK:
		_fail_membership(actor_ref, "subscription_send_failed:%d" % result)


func _on_ack(payload: Dictionary) -> void:
	if _pending.is_empty() or payload.get("source_type") != _pending["source_type"]:
		return
	var actor_ref: String = _pending["actor_ref"]
	if not bool(payload.get("accepted", false)):
		_fail_membership(actor_ref, str(payload.get("error_code", "subscription_denied")))
		return
	_pending.clear()
	call_deferred("_pump_membership")


func _fail_membership(actor_ref: String, reason: String) -> void:
	_discard_consumer(actor_ref)
	_pending.clear()
	_operations.clear()
	subscription_failed.emit(actor_ref, reason)


func apply_snapshot(payload: Dictionary) -> void:
	if payload.has("delivery_sequence"):
		bridge._on_delivery(payload)
	else:
		bridge._on_projection(payload)


func apply_delta(payload: Dictionary) -> void:
	bridge._on_delivery(payload)


func _on_projection_applied(actor_ref: String, snapshot: Dictionary) -> void:
	if not _consumers.has(actor_ref) or not allowed_actor_refs.has(actor_ref):
		return
	if not snapshot["groups"].has("population_public"):
		presenter.remove_actor(actor_ref)
		return
	presenter.set_population(snapshot)
	population_applied.emit(actor_ref, snapshot)


func _on_projection_removed(actor_ref: String) -> void:
	presenter.remove_actor(actor_ref)


func _discard_consumer(actor_ref: String) -> void:
	bridge.unregister_consumer(actor_ref)
	var consumer: Node = _consumers.get(actor_ref)
	_consumers.erase(actor_ref)
	if consumer != null:
		remove_child(consumer)
		consumer.queue_free()


func _on_session_ended(_payload: Dictionary) -> void:
	_pending.clear()
	_operations.clear()
	_desired.clear()
	allowed_actor_refs.clear()
	for actor_ref: String in _consumers.keys():
		_discard_consumer(actor_ref)
	presenter.clear_population()


func _on_renewal(_payload: Dictionary) -> void:
	# bridge先清旧epoch并保存新的opaque enrollment，再在原连接换绑。
	_on_session_ended({})
	bridge.bind_session()
