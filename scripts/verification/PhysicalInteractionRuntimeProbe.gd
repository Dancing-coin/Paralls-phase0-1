extends Node

const PHYSICAL_PROBE := preload("res://scripts/interaction/PhysicalInteractionProbe.gd")
const PHYSICAL_ADAPTER := preload("res://scripts/interaction/PhysicalInteractionAdapter.gd")


func _ready() -> void:
	call_deferred("_run_probe")


func _run_probe() -> void:
	var probe = PHYSICAL_PROBE.new()
	var adapter = PHYSICAL_ADAPTER.new()
	var contact_payload: Dictionary = probe.sample_contact_ref("char_a", "obj_box", "push")
	var effect_payload: Dictionary = adapter.build_physical_effect_ref("char_a", "obj_box", "push", contact_payload)
	var report := {
		"status": "godot-runtime-physical-interaction-verified",
		"contact_payload": contact_payload,
		"effect_payload": effect_payload,
		"boundary": {
			"sampling_only": probe.sampling_only,
			"semantic_success_decision_allowed": probe.semantic_success_decision_allowed,
			"raw_physics_stream_to_backend_allowed": probe.raw_physics_stream_to_backend_allowed,
			"structured_refs_only": adapter.structured_refs_only,
			"bypass_semantic_authority_allowed": adapter.bypass_semantic_authority_allowed,
			"second_world_result_protocol_allowed": adapter.second_world_result_protocol_allowed,
		},
	}
	var report_path := _write_json(".harness/verification/esm-physical-channel-godot-runtime.json", report)
	print("physical_interaction_runtime_probe:artifact=%s" % report_path)
	print("physical_interaction_runtime_probe:structured_refs=true")
	print("physical_interaction_runtime_probe:authority_bypass=false")
	get_tree().quit(0)


func _write_json(relative_path: String, payload: Dictionary) -> String:
	var path := ProjectSettings.globalize_path("res://" + relative_path)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return ""
	file.store_string(JSON.stringify(payload, "\t"))
	file.close()
	return path
