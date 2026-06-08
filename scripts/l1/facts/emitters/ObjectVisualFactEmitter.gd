extends Node

@export_node_path("Node") var visual_fact_emitter_path := NodePath("..")


func emit_object_state_transition(target_object_id: String, relation_type: String = "object_state_changed") -> bool:
	if target_object_id == "":
		return false

	var visual_fact_emitter := get_node_or_null(visual_fact_emitter_path)
	if visual_fact_emitter == null or not visual_fact_emitter.has_method("emit_visual_fact"):
		return false

	return visual_fact_emitter.emit_visual_fact(
		"object_state_change",
		relation_type,
		"",
		target_object_id,
		""
	)
