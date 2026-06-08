extends Node

@export_node_path("Node") var visual_fact_emitter_path := NodePath("..")


func emit_spatial_relation_fact(
	relation_type: String,
	target_actor_id: String = "",
	target_object_id: String = "",
	target_environment_id: String = ""
) -> bool:
	var visual_fact_emitter := get_node_or_null(visual_fact_emitter_path)
	if visual_fact_emitter == null or not visual_fact_emitter.has_method("emit_visual_fact"):
		return false

	return visual_fact_emitter.emit_visual_fact(
		"spatial_relation",
		relation_type,
		target_actor_id,
		target_object_id,
		target_environment_id
	)
