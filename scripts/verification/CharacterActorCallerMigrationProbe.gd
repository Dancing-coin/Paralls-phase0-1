extends Node

const MAIN_DEMO_SCENE := preload("res://scenes/phase0/MainDemo.tscn")
const EMBODIED_PROVIDER := preload("res://scripts/character/EmbodiedStateProvider.gd")
const SKELETAL_PROVIDER := preload("res://scripts/character/EmbodiedSkeletalStateProvider.gd")
const VERIFICATION_PATHS := preload("res://scripts/verification/VerificationPaths.gd")

const LEGACY_HOST_NAME := "Character" + "Replica"


func _ready() -> void:
	if VERIFICATION_PATHS.resolve(".harness/verification/.context-check").is_empty():
		get_tree().quit(1)
		return
	call_deferred("_run_probe")


func _run_probe() -> void:
	var main_demo := MAIN_DEMO_SCENE.instantiate()
	add_child(main_demo)
	await get_tree().process_frame
	await get_tree().process_frame

	var actor_nodes: Array[Node] = []
	_collect_actor_nodes(main_demo, actor_nodes)
	var legacy_instances: Array[String] = []
	_collect_legacy_hosts(main_demo, legacy_instances)
	var provider_lookup_count := 0
	var provider_invocation_count := 0
	var provider_failures: Array[String] = []
	var ingress_sources: Array[Dictionary] = []
	var compatibility_call_count := 0
	var compatibility_observation_unavailable := 0
	var skeletal_binding_count := 0
	for actor in actor_nodes:
		var actor_id := str(actor.get("actor_id"))
		var embodied_provider = EMBODIED_PROVIDER.new()
		provider_invocation_count += 1
		var state: Dictionary = embodied_provider.build_from_actor_node(actor_id, actor)
		if not str(state.get("actor_node_path", "")).is_empty() and str(state.get("capability_failure", "")).is_empty():
			provider_lookup_count += 1
		else:
			provider_failures.append("embodied:%s" % actor_id)
		var skeletal_provider = SKELETAL_PROVIDER.new()
		var binding: Dictionary = skeletal_provider.bind_runtime(actor)
		if bool(binding.get("runtime_binding_verified", false)):
			skeletal_binding_count += 1
		else:
			provider_failures.append("skeletal:%s" % actor_id)
		if actor.has_method("apply_control_intent"):
			var intent := {
				"source_kind": "agent",
				"actor_id": actor_id,
				"move_direction": Vector3.ZERO,
				"wants_run": false,
				"jump_type": "none",
				"gait": "idle",
				"stance": "standing",
				"action": "",
			}
			actor.call("apply_control_intent", intent)
			ingress_sources.append({"actor_id": actor_id, "source_kind": "agent", "entry": "apply_control_intent"})
		var compatibility_observation := _read_compatibility_count(actor)
		if bool(compatibility_observation.get("supported", false)):
			compatibility_call_count += int(compatibility_observation.get("count", 0))
		else:
			compatibility_observation_unavailable += 1

	var report := {
		"status": "pass" if provider_failures.is_empty() and legacy_instances.is_empty() and compatibility_observation_unavailable == 0 else "fail",
		"live_actor_count": actor_nodes.size(),
		"live_actor_paths": _paths(actor_nodes),
		"concrete_replica_instances": legacy_instances,
		"provider_lookup_count": provider_lookup_count,
		"provider_invocation_count": provider_invocation_count,
		"skeletal_binding_count": skeletal_binding_count,
		"provider_failures": provider_failures,
		"compatibility_call_count": compatibility_call_count,
		"compatibility_observation_unavailable": compatibility_observation_unavailable,
		"ingress_sources": ingress_sources,
	}
	var report_path := _write_json(".harness/verification/character-actor-caller-migration.json", report)
	print("character_actor_caller_migration_probe:status=%s" % str(report.get("status", "fail")))
	print("character_actor_caller_migration_probe:live_actor_count=%d" % actor_nodes.size())
	print("character_actor_caller_migration_probe:concrete_replica_instances=%d" % legacy_instances.size())
	print("character_actor_caller_migration_probe:provider_lookup_count=%d" % provider_lookup_count)
	print("character_actor_caller_migration_probe:compatibility_call_count=%d" % compatibility_call_count)
	print("character_actor_caller_migration_probe:report=%s" % report_path)
	get_tree().quit(0 if str(report.get("status", "fail")) == "pass" else 1)


func _collect_actor_nodes(root: Node, output: Array[Node]) -> void:
	if _has_actor_capability(root):
		output.append(root)
	for child: Node in root.get_children():
		_collect_actor_nodes(child, output)


func _collect_legacy_hosts(root: Node, output: Array[String]) -> void:
	var script_path := ""
	var script := root.get_script()
	if script != null and script is GDScript:
		script_path = str((script as GDScript).resource_path)
	var legacy_script := "/%s.gd" % LEGACY_HOST_NAME
	var legacy_presentation_script := "/presentation/character/%s.gd" % LEGACY_HOST_NAME
	if root.name == LEGACY_HOST_NAME or script_path.ends_with(legacy_script) or script_path.ends_with(legacy_presentation_script):
		output.append(str(root.get_path()))
	for child: Node in root.get_children():
		_collect_legacy_hosts(child, output)


func _has_actor_capability(node: Node) -> bool:
	return node != null and node.has_method("apply_control_intent") and node.has_method("get_focus_anchor_position") and node.has_method("get_embodied_forward_vector")


func _read_compatibility_count(node: Node) -> Dictionary:
	if node == null:
		return {"supported": false, "count": 0}
	if node.has_method("get_compatibility_diagnostics"):
		var diagnostics: Variant = node.call("get_compatibility_diagnostics")
		if diagnostics is Dictionary:
			return {"supported": true, "count": int((diagnostics as Dictionary).get("compatibility_call_count", 0))}
	if node.get("compatibility_call_diagnostics") is Array:
		return {"supported": true, "count": (node.get("compatibility_call_diagnostics") as Array).size()}
	return {"supported": false, "count": 0}


func _paths(nodes: Array[Node]) -> Array[String]:
	var output: Array[String] = []
	for node in nodes:
		output.append(str(node.get_path()))
	return output


func _write_json(relative_path: String, payload: Dictionary) -> String:
	var path := VERIFICATION_PATHS.resolve("res://" + relative_path)
	if path.is_empty():
		return ""
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return ""
	file.store_string(JSON.stringify(payload, "\t"))
	file.close()
	return path

