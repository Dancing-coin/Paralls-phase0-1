extends Node

@export var actor_id := "char_c"
@export var room_id := "room_demo"
@export var scene_id := "scene_demo"
@export var zone_id := "zone_focus"

func emit_visual_fact(
	fact_type: String,
	relation_type: String,
	target_actor_id: String = "",
	target_object_id: String = "",
	target_environment_id: String = ""
) -> bool:
	var bridge := _get_bridge()
	if bridge == null or not bridge.has_method("send_envelope"):
		_bus_log("phase0_visual_fact_emitter_missing_bridge")
		return false
	if bridge.has_method("is_backend_open") and not bridge.is_backend_open():
		_bus_log("phase0_visual_fact_emitter_backend_closed")
		return false

	var payload := {
		"actor_id": actor_id,
		"room_id": room_id,
		"scene_id": scene_id,
		"zone_id": zone_id,
		"producer_ts": Time.get_ticks_msec(),
		"fact_type": fact_type,
		"relation_type": relation_type,
	}
	if target_actor_id != "":
		payload["target_actor_id"] = target_actor_id
	if target_object_id != "":
		payload["target_object_id"] = target_object_id
	if target_environment_id != "":
		payload["target_environment_id"] = target_environment_id

	var envelope := {
		"message_type": "visual_fact_event",
		"payload": payload,
	}
	var err: int = bridge.send_envelope(envelope)
	if err != OK:
		_bus_log("phase0_visual_fact_emitter_send_failed:%s" % err)
		return false

	_bus_log(
		"phase0_visual_fact_emitter:%s:%s" % [
			fact_type,
			relation_type,
		]
	)
	return true

func _get_bridge() -> Node:
	return get_node_or_null("/root/BackendBridge")

func _get_bus() -> Node:
	return get_node_or_null("/root/LocalPresentationBus")

func _bus_log(message: String) -> void:
	var bus := _get_bus()
	if bus and bus.has_method("log_debug"):
		bus.log_debug(message)
