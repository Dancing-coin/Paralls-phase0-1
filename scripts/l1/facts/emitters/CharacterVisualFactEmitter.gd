extends Node

@export_node_path("Node") var visual_fact_emitter_path := NodePath("..")


func emit_fixed_gaze_on_target(target_actor_id: String = "", target_object_id: String = "") -> bool:
	if target_actor_id == "" and target_object_id == "":
		return false

	var relation_type := "actor_looks_at_actor" if target_actor_id != "" else "actor_looks_at_object"
	_bus_log("phase0_visual_fact:%s:%s" % [
		relation_type,
		target_actor_id if target_actor_id != "" else target_object_id,
	])
	return _emit_visual_fact("fixed_gaze_on_target", relation_type, target_actor_id, target_object_id)


func emit_actor_near_object(target_object_id: String) -> bool:
	if target_object_id == "":
		return false

	_bus_log("phase0_visual_fact:actor_near_object:%s" % target_object_id)
	return _emit_visual_fact("spatial_relation", "actor_near_object", "", target_object_id)


func _emit_visual_fact(
	fact_type: String,
	relation_type: String,
	target_actor_id: String = "",
	target_object_id: String = "",
	target_environment_id: String = ""
) -> bool:
	var visual_fact_emitter := _get_visual_fact_emitter()
	if visual_fact_emitter == null or not visual_fact_emitter.has_method("emit_visual_fact"):
		return false
	return visual_fact_emitter.emit_visual_fact(
		fact_type,
		relation_type,
		target_actor_id,
		target_object_id,
		target_environment_id
	)


func _get_visual_fact_emitter() -> Node:
	return get_node_or_null(visual_fact_emitter_path)


func _get_bus() -> Node:
	return get_node_or_null("/root/LocalPresentationBus")


func _bus_log(message: String) -> void:
	var bus := _get_bus()
	if bus and bus.has_method("log_debug"):
		bus.log_debug(message)
