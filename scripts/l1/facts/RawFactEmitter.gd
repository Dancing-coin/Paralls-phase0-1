extends RefCounted

const FACT_ENVELOPE_BUILDER := preload("res://scripts/l1/facts/FactEnvelopeBuilder.gd")
const FACT_DEDUPER := preload("res://scripts/l1/facts/FactDeduper.gd")

var _owner: Node
var _bridge_path: NodePath
var _bus_path: NodePath
var _builder = FACT_ENVELOPE_BUILDER.new()
var _deduper


func _init(
	owner: Node,
	dedupe_window_ms: int = 0,
	bridge_path: NodePath = NodePath("/root/BackendBridge"),
	bus_path: NodePath = NodePath("/root/LocalPresentationBus")
) -> void:
	_owner = owner
	_bridge_path = bridge_path
	_bus_path = bus_path
	_deduper = FACT_DEDUPER.new(dedupe_window_ms)


func emit_raw_fact(
	payload: Dictionary,
	log_prefix: String,
	success_log: String = "",
	dedupe_key: String = ""
) -> bool:
	var bridge := _get_bridge()
	if bridge == null or not bridge.has_method("send_envelope"):
		_bus_log("%s_missing_bridge" % log_prefix)
		return false
	if bridge.has_method("is_backend_open") and not bridge.is_backend_open():
		_bus_log("%s_backend_closed" % log_prefix)
		return false

	var envelope := _builder.build_raw_fact_envelope(payload)
	if not _deduper.should_emit(envelope, dedupe_key):
		return true

	var err: int = bridge.send_envelope(envelope)
	if err != OK:
		_bus_log("%s_send_failed:%s" % [log_prefix, err])
		return false

	if success_log != "":
		_bus_log(success_log)
	return true


func _get_bridge() -> Node:
	if _owner == null:
		return null
	return _owner.get_node_or_null(_bridge_path)


func _get_bus() -> Node:
	if _owner == null:
		return null
	return _owner.get_node_or_null(_bus_path)


func _bus_log(message: String) -> void:
	var bus := _get_bus()
	if bus and bus.has_method("log_debug"):
		bus.log_debug(message)
