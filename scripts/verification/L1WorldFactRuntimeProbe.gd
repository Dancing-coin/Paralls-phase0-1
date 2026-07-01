extends Node

const MAIN_DEMO_SCENE := preload("res://scenes/phase0/MainDemo.tscn")
const SCENE_EXTRACTOR := preload("res://scripts/l1/space/SceneSpaceModelExtractor.gd")
const OCCUPANCY_SAMPLER := preload("res://scripts/l1/space/RuntimeOccupancySampler.gd")
const PROJECTION_BRIDGE := preload("res://scripts/l1/space/FactProjectionBridge.gd")
const VISUAL_PROVIDER := preload("res://scripts/character/VisualPatchProvider.gd")
const SPATIAL_PROVIDER := preload("res://scripts/character/SpatialPatchProvider.gd")
const AUDITORY_PROVIDER := preload("res://scripts/character/AuditoryContextProvider.gd")
const EMBODIED_PROVIDER := preload("res://scripts/character/EmbodiedStateProvider.gd")


func _ready() -> void:
	call_deferred("_run_probe")


func _run_probe() -> void:
	var main_demo := MAIN_DEMO_SCENE.instantiate()
	add_child(main_demo)
	await get_tree().process_frame
	await get_tree().process_frame

	var extractor = SCENE_EXTRACTOR.new()
	var space_model: Dictionary = extractor.extract(main_demo)
	var space_artifact: String = extractor.write_artifact(space_model)

	var occupancy = OCCUPANCY_SAMPLER.new()
	occupancy.initialize_from_space_model(space_model)
	occupancy.apply_actor_zone("char_b", "zone_focus", "raw_fact_event:actor_entered_zone:probe")
	occupancy.apply_object_state("obj_letter", "zone_focus", "visible", ["inspect", "read"], false, "object_state_result:obj_letter:probe")
	occupancy.apply_environment_field("zone_focus", "reduced", "dense", "environment_state_result:env_lamp:probe")
	var occupancy_artifact: String = occupancy.write_artifact()

	var projection = PROJECTION_BRIDGE.new()
	var projected_facts: Array[Dictionary] = projection.project_probe_facts("char_b", "obj_letter", "zone_focus", occupancy.snapshot())
	var projection_artifact := _write_json(".harness/verification/l1-projection-runtime.json", {"projected_facts": projected_facts})

	var visual_provider = VISUAL_PROVIDER.new()
	var camera := _find_first_camera(main_demo)
	var camera_pose: Dictionary = visual_provider.build_camera_pose_ref(camera, "runtime://artifact/.harness/verification/l1-provider-runtime.json")
	var visual_ref: Dictionary = visual_provider.build_query_input_ref("char_b", camera_pose, "obj_letter")

	var spatial_provider = SPATIAL_PROVIDER.new()
	var spatial_ref: Dictionary = spatial_provider.build_runtime_patch_ref(
		"char_b",
		"zone_focus",
		"runtime://artifact/%s" % occupancy_artifact,
		["collision_shape:/root/MainDemo/ThroneRoomCollisionRoot"],
		["runtime://node/root/MainDemo/ThroneRoomCollisionRoot"]
	)

	var auditory_provider = AUDITORY_PROVIDER.new()
	var auditory_ref: Dictionary = auditory_provider.build_query_input_ref(
		"char_b",
		["raw_fact_event:auditory_fact:speaker_active:probe"],
		"quiet"
	)

	var embodied_provider = EMBODIED_PROVIDER.new()
	var embodied_ref: Dictionary = embodied_provider.build_query_input_ref(
		"char_b",
		"standing",
		"idle",
		true,
		true,
		true
	)

	var pqf := {
		"query_id": "pqf:char_b:%s" % Time.get_ticks_msec(),
		"consumer_kind": "character",
		"subject_id": "char_b",
		"time_window": {
			"started_at": 0,
			"ended_at": Time.get_ticks_msec(),
			"cadence": "short_window",
		},
		"spatial_reference": {
			"room_id": "room_demo",
			"scene_id": "scene_demo",
			"zone_id": "zone_focus",
			"coordinate_space": "godot_world",
		},
		"visual_inputs": [visual_ref],
		"spatial_inputs": [spatial_ref],
		"auditory_inputs": [auditory_ref],
		"embodied_inputs": [embodied_ref],
		"structured_fact_refs": projected_facts.map(func(fact: Dictionary) -> String: return "raw_fact_event:%s:%s" % [fact.get("fact_family", ""), fact.get("fact_type", "")]),
		"multimodal_context_id": "character_mm:char_b",
		"cache_namespace": "character_mm:char_b:l1_world_fact_cache",
	}
	var provider_artifact := _write_json(".harness/verification/l1-provider-runtime.json", {
		"visual_ref": visual_ref,
		"spatial_ref": spatial_ref,
		"auditory_ref": auditory_ref,
		"embodied_ref": embodied_ref,
		"perception_query_frame": pqf,
	})

	print("l1_world_fact_runtime_probe:space_artifact=%s" % space_artifact)
	print("l1_world_fact_runtime_probe:occupancy_artifact=%s" % occupancy_artifact)
	print("l1_world_fact_runtime_probe:projection_artifact=%s" % projection_artifact)
	print("l1_world_fact_runtime_probe:provider_artifact=%s" % provider_artifact)
	print("l1_world_fact_runtime_probe:projected_fact_count=%s" % projected_facts.size())
	print("l1_world_fact_runtime_probe:runtime_source_refs=true")
	get_tree().quit(0)


func _find_first_camera(root: Node) -> Camera3D:
	if root is Camera3D:
		return root as Camera3D
	for child: Node in root.get_children():
		var found := _find_first_camera(child)
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
