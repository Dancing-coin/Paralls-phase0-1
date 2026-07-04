extends Node

class_name PhysicalInteractionProbe

@export var sampling_only := true
@export var semantic_success_decision_allowed := false
@export var raw_physics_stream_to_backend_allowed := false
@export var feeds_interaction_orchestration := true


func sample_contact_ref(actor_id: String, target_object_id: String, effect_kind: String = "contact") -> Dictionary:
	var now := Time.get_ticks_msec()
	return {
		"contact_ref": "godot_contact:%s:%s:%s" % [actor_id, target_object_id, now],
		"body_ref": "godot_body:%s:primary" % actor_id,
		"object_ref": "godot_object:%s" % target_object_id,
		"environment_ref": "godot_environment:zone_focus",
		"normal_summary": "structured contact sample for %s" % effect_kind,
		"sampled_by": "godot_physical_interaction_probe",
		"retention": "ref_only",
		"runtime_source_refs": [
			"actor:%s" % actor_id,
			"object:%s" % target_object_id,
		],
	}
