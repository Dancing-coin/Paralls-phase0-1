extends Node

@export_node_path("Node") var visual_fact_emitter_path := NodePath("..")


func emit_visual_evidence_projection(target_object_id: String = "", target_environment_id: String = "") -> bool:
	var visual_fact_emitter := get_node_or_null(visual_fact_emitter_path)
	if visual_fact_emitter == null or not visual_fact_emitter.has_method("emit_visual_fact"):
		return false

	if target_object_id == "" and target_environment_id == "":
		return false

	return visual_fact_emitter.emit_visual_fact(
		"visual_evidence_projection",
		"evidence_projection",
		"",
		target_object_id,
		target_environment_id
	)
