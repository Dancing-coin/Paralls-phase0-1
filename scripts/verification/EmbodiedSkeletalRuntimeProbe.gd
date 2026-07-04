extends Node

const MAIN_DEMO_SCENE := preload("res://scenes/phase0/MainDemo.tscn")
const SKELETAL_PROVIDER := preload("res://scripts/character/EmbodiedSkeletalStateProvider.gd")


func _ready() -> void:
	call_deferred("_run_probe")


func _run_probe() -> void:
	var main_demo := MAIN_DEMO_SCENE.instantiate()
	add_child(main_demo)
	await get_tree().process_frame
	await get_tree().process_frame

	var actor_node := main_demo.get_node_or_null("PlayerCharacter")
	var skeleton := _find_first_skeleton(actor_node)
	var provider = SKELETAL_PROVIDER.new()
	var trace_refs: Array[String] = [
		"pqf:char_b:embodied-skeletal-runtime-probe",
		"bundle:character:char_b:embodied-skeletal-runtime-probe",
		"failure_trace:reachability:embodied-skeletal-runtime-probe",
	]
	var main_payload: Dictionary = provider.build_main_chain_payload_from_runtime("char_b", actor_node, trace_refs)
	var snapshot_artifact: Dictionary = provider.write_debug_snapshot_artifact("char_b", skeleton, trace_refs)
	var report := {
		"status": "godot-runtime-binding-verified" if main_payload.get("runtime_binding", {}).get("runtime_binding_verified", false) else "godot-runtime-binding-unverified",
		"main_perception_payload": main_payload,
		"debug_replay_snapshot": snapshot_artifact,
		"full_bone_main_chain_excluded": not main_payload.has("low_level_snapshot") and not main_payload.has("bones"),
		"retention": "debug_replay_only",
		"trace_refs": trace_refs,
	}
	var report_path := _write_json(".harness/verification/embodied-skeletal-debug-replay-runtime.json", report)
	print("embodied_skeletal_runtime_probe:report=%s" % report_path)
	print("embodied_skeletal_runtime_probe:runtime_binding=%s" % str(report.get("status") == "godot-runtime-binding-verified"))
	print("embodied_skeletal_runtime_probe:full_bone_main_chain_excluded=%s" % str(report.get("full_bone_main_chain_excluded", false)))
	get_tree().quit(0)


func _find_first_skeleton(root: Node) -> Skeleton3D:
	if root == null:
		return null
	if root is Skeleton3D:
		return root as Skeleton3D
	for child: Node in root.get_children():
		var found := _find_first_skeleton(child)
		if found != null:
			return found
	return null


func _write_json(relative_path: String, payload: Dictionary) -> String:
	var path := ProjectSettings.globalize_path("res://" + relative_path)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return ""
	file.store_string(JSON.stringify(payload, "\t"))
	file.close()
	return path
