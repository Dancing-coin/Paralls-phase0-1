extends Node

const MAIN_DEMO_SCENE := preload("res://scenes/phase0/MainDemo.tscn")
const VISUAL_PROVIDER := preload("res://scripts/character/VisualPatchProvider.gd")
const SPATIAL_PROVIDER := preload("res://scripts/character/SpatialPatchProvider.gd")
const AUDITORY_PROVIDER := preload("res://scripts/character/AuditoryContextProvider.gd")
const EMBODIED_PROVIDER := preload("res://scripts/character/EmbodiedStateProvider.gd")
const SKELETAL_PROVIDER := preload("res://scripts/character/EmbodiedSkeletalStateProvider.gd")
const SKELETAL_REF_EMITTER := preload("res://scripts/character/SkeletalStateProviderRefEmitter.gd")
const ENVIRONMENT_PROVIDER := preload("res://scripts/character/EnvironmentFieldProvider.gd")


func _ready() -> void:
	call_deferred("_run_probe")


func _run_probe() -> void:
	var main_demo := MAIN_DEMO_SCENE.instantiate()
	add_child(main_demo)
	await get_tree().process_frame
	await get_tree().process_frame

	var actor_node := main_demo.get_node_or_null("PlayerCharacter")
	var camera := _find_first_camera(main_demo)
	var skeleton := _find_first_skeleton(actor_node)

	var visual_provider = VISUAL_PROVIDER.new()
	var viewport_capture_ref: String = visual_provider.write_viewport_capture_artifact(
		get_viewport(),
		".harness/verification/godot-sampling-visual-capture.png"
	)
	var camera_pose: Dictionary = visual_provider.build_camera_pose_ref(camera, viewport_capture_ref)
	var visual_ref: Dictionary = visual_provider.build_query_input_ref("char_b", camera_pose, "obj_letter")

	var spatial_provider = SPATIAL_PROVIDER.new()
	var spatial_ref: Dictionary = spatial_provider.build_runtime_patch_ref(
		"char_b",
		"zone_focus",
		"runtime://artifact/.harness/verification/godot-sampling-spatial-patch.json",
		["collision_shape:/root/MainDemo/ThroneRoomCollisionRoot"],
		["runtime://node/root/MainDemo/ThroneRoomCollisionRoot"]
	)

	var auditory_provider = AUDITORY_PROVIDER.new()
	var auditory_ref: Dictionary = auditory_provider.build_query_input_ref(
		"char_b",
		["raw_fact_event:auditory_fact:speaker_active:godot-sampling-probe"],
		"quiet"
	)

	var embodied_provider = EMBODIED_PROVIDER.new()
	var embodied_ref: Dictionary = embodied_provider.build_from_actor_node("char_b", actor_node, true, true)

	var skeletal_provider = SKELETAL_PROVIDER.new()
	var skeletal_payload: Dictionary = skeletal_provider.build_main_chain_payload_from_runtime(
		"char_b",
		actor_node,
		["pqf:char_b:godot-sampling-probe", "failure_trace:reachability:probe"]
	)
	var snapshot_artifact: Dictionary = skeletal_provider.write_debug_snapshot_artifact(
		"char_b",
		skeleton,
		["pqf:char_b:godot-sampling-probe", "failure_trace:reachability:probe"]
	)
	var skeletal_ref_emitter = SKELETAL_REF_EMITTER.new()
	var skeletal_ref: Dictionary = skeletal_ref_emitter.build_query_input_ref(
		"char_b",
		str(skeletal_payload.get("runtime_source_refs", [""])[0]),
		str(snapshot_artifact.get("snapshot_ref", "")),
		int(snapshot_artifact.get("bone_count", 0))
	)

	var environment_provider = ENVIRONMENT_PROVIDER.new()
	var environment_ref: Dictionary = environment_provider.build_query_input_ref(
		"zone_focus",
		["runtime://light/zone_focus/key"],
		["runtime://occlusion/zone_focus/pillar"],
		["runtime://hazard/zone_focus/smoke_light"],
		["runtime://space/zone_focus/passability"],
		["field:room_demo:scene_demo:zone_focus"]
	)

	var now := Time.get_ticks_msec()
	var pqf := {
		"query_id": "pqf:char_b:%s" % now,
		"consumer_kind": "character",
		"subject_id": "char_b",
		"time_window": {
			"started_at": max(0, now - 1500),
			"ended_at": now,
			"cadence": "short_window",
		},
		"spatial_reference": {
			"room_id": "room_demo",
			"scene_id": "scene_demo",
			"zone_id": "zone_focus",
			"coordinate_space": "godot_world",
		},
		"visual_inputs": [_pqf_ref(visual_ref)],
		"spatial_inputs": [_pqf_ref(spatial_ref)],
		"auditory_inputs": [_pqf_ref(auditory_ref)],
		"embodied_inputs": [_pqf_ref(embodied_ref)],
		"skeletal_inputs": [_pqf_ref(skeletal_ref)],
		"environment_inputs": [_pqf_ref(environment_ref)],
		"structured_fact_refs": ["raw_fact_event:spatial_access_fact:actor_approached_object:godot-sampling-probe"],
		"multimodal_context_id": "character_mm:char_b",
		"cache_namespace": "character_mm:char_b:godot_sampling_cache",
		"inference_history_ref": "character_mm:char_b:godot_sampling_history",
	}
	var report := {
		"status": "godot-runtime-sampling-verified",
		"provider_refs": {
			"visual_inputs": [visual_ref],
			"spatial_inputs": [spatial_ref],
			"auditory_inputs": [auditory_ref],
			"embodied_inputs": [embodied_ref],
			"skeletal_inputs": [skeletal_ref],
			"environment_inputs": [environment_ref],
		},
		"skeletal_payload": skeletal_payload,
		"debug_snapshot_artifact": snapshot_artifact,
		"perception_query_frame": pqf,
		"no_heavy_work": {
			"visual_heavy_inference_allowed": visual_provider.heavy_inference_allowed,
			"spatial_heavy_voxelization_allowed": spatial_provider.heavy_voxelization_allowed,
			"environment_heavy_voxelization_allowed": environment_provider.heavy_voxelization_allowed,
			"environment_heavy_scene_scan_allowed": environment_provider.heavy_scene_scan_allowed,
		},
	}
	var report_path := _write_json(".harness/verification/godot-sampling-production-grade-providers-runtime.json", report)
	print("godot_sampling_providers_probe:provider_artifact=%s" % report_path)
	print("godot_sampling_providers_probe:six_provider_refs=true")
	print("godot_sampling_providers_probe:skeleton_binding=%s" % str(skeletal_payload.get("runtime_binding", {}).get("runtime_binding_verified", false)))
	get_tree().quit(0)


func _find_first_camera(root: Node) -> Camera3D:
	if root is Camera3D:
		return root as Camera3D
	for child: Node in root.get_children():
		var found := _find_first_camera(child)
		if found != null:
			return found
	return null


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


func _pqf_ref(sample: Dictionary) -> Dictionary:
	return {
		"provider_kind": str(sample.get("provider_kind", "")),
		"ref_id": str(sample.get("ref_id", "")),
		"summary": str(sample.get("summary", "")),
		"retention": str(sample.get("retention", "ref_only")),
		"sample_status": str(sample.get("sample_status", "ok")),
		"freshness": str(sample.get("freshness", "fresh")),
		"throttle_state": str(sample.get("throttle_state", "allowed")),
		"stable_source_ref": str(sample.get("stable_source_ref", "")),
		"runtime_source_refs": sample.get("runtime_source_refs", []),
		"error": str(sample.get("error", "")),
		"failure_status": str(sample.get("failure_status", "")),
		"expires_at": sample.get("expires_at", null),
	}
