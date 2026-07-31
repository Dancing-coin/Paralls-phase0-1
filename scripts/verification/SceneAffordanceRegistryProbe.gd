extends Node

const SPACE_EXTRACTOR := preload("res://scripts/l1/space/SceneSpaceModelExtractor.gd")
const OCCUPANCY_SAMPLER := preload("res://scripts/l1/space/RuntimeOccupancySampler.gd")
const REGISTRY := preload("res://scripts/interaction/SceneAffordanceRegistry.gd")


func _ready() -> void:
	call_deferred("_run_probe")


func _run_probe() -> void:
	var fixture_root := Node3D.new()
	fixture_root.name = "SceneAffordanceRegistryFixture"
	add_child(fixture_root)
	var chair := StaticBody3D.new()
	chair.name = "InteractiveObjectChair01"
	fixture_root.add_child(chair)
	var collider := CollisionShape3D.new()
	collider.name = "ChairCollider"
	var shape := BoxShape3D.new()
	shape.size = Vector3(0.6, 1.0, 0.6)
	collider.shape = shape
	chair.add_child(collider)
	var navigation := NavigationRegion3D.new()
	navigation.name = "ChairNavigationRegion"
	fixture_root.add_child(navigation)

	var extractor = SPACE_EXTRACTOR.new()
	var space_model: Dictionary = extractor.extract(fixture_root)
	_patch_space_model_for_chair(space_model)

	var occupancy = OCCUPANCY_SAMPLER.new()
	occupancy.initialize_from_space_model(space_model)
	occupancy.apply_object_state(
		"entity:scene_demo:chair_01",
		"zone_focus",
		"upright",
		["kick"],
		false,
		"object_state:chair_01:110"
	)
	var occupancy_snapshot: Dictionary = occupancy.snapshot()
	var object_state: Dictionary = occupancy_snapshot.get("object_states", {}).get("entity:scene_demo:chair_01", {})
	object_state["updated_at"] = 110
	occupancy_snapshot["object_states"]["entity:scene_demo:chair_01"] = object_state

	var registry = REGISTRY.new()
	registry.configure(
		space_model,
		occupancy_snapshot,
		_grounding_catalog(),
		120,
		30
	)
	var register_result: Dictionary = registry.register_reviewed_record(_chair_record())
	var resolve_result: Dictionary = registry.resolve(
		"scene_demo",
		"scene_instance:main_demo:1",
		"entity:scene_demo:chair_01",
		"affordance:chair_01:kick",
		7,
		["approach_stance", "contact"],
		"controller"
	)
	var public_result: Dictionary = registry.resolve(
		"scene_demo",
		"scene_instance:main_demo:1",
		"entity:scene_demo:chair_01",
		"affordance:chair_01:kick",
		7,
		["approach_stance", "contact"],
		"public"
	)
	var stale_result: Dictionary = registry.resolve(
		"scene_demo",
		"scene_instance:main_demo:1",
		"entity:scene_demo:chair_01",
		"affordance:chair_01:kick",
		6,
		["approach_stance", "contact"],
		"controller"
	)
	var vla_conflict: Dictionary = registry.review_vla_candidate(
		"entity:scene_demo:chair_01",
		{"entity_refs": ["entity:vla:invented"], "collider_refs": ["collider:vla:fake"]}
	)
	var report := {
		"status": "godot-runtime-scene-affordance-registry-verified",
		"register_result": register_result,
		"resolve_result": resolve_result,
		"public_result": public_result,
		"stale_result": stale_result,
		"vla_conflict": vla_conflict,
		"space_model_sources": space_model.get("extraction_sources", []),
		"identity_refs": {
			"entity_ref": resolve_result.get("record", {}).get("entity_ref", ""),
			"collider_refs": resolve_result.get("record", {}).get("local_binding", {}).get("collider_refs", []),
			"anchor_refs": resolve_result.get("record", {}).get("grounding_catalog_refs", {}).get("anchor_refs", []),
		},
		"uses_scene_space_model_extractor": true,
		"uses_runtime_occupancy_sampler": true,
	}
	var report_path := _write_json(".harness/verification/embodied-affordance-registry-godot-runtime.json", report)
	var ok: bool = (
		str(resolve_result.get("status", "")) == "available"
		and not public_result.get("projection", {}).has("local_binding")
		and str(stale_result.get("status", "")) == "registry_binding_stale"
		and str(vla_conflict.get("status", "")) == "vla_conflict_recorded"
	)
	print("scene_affordance_registry_probe:artifact=%s" % report_path)
	print("scene_affordance_registry_probe:resolved=%s" % str(ok).to_lower())
	get_tree().quit(0 if ok else 1)


func _patch_space_model_for_chair(space_model: Dictionary) -> void:
	var patched_elements: Array = []
	for element: Dictionary in space_model.get("elements", []):
		if str(element.get("element_id", "")) == "obj_letter":
			element["element_id"] = "entity:scene_demo:chair_01"
			element["semantic_tags"] = ["chair", "kickable"]
			var refs: Array = element.get("source_refs", [])
			refs.append("collider:chair_01:body")
			refs.append("anchor:chair_01:stance")
			refs.append("anchor:chair_01:contact")
			refs.append("affordance:chair_01:kick")
			element["source_refs"] = refs
		if str(element.get("element_type", "")) == "navigation_lane":
			element["element_id"] = "nav:chair_01:footprint"
		patched_elements.append(element)
	space_model["elements"] = patched_elements


func _chair_record() -> Dictionary:
	return {
		"entity_ref": "entity:scene_demo:chair_01",
		"scene_id": "scene_demo",
		"scene_instance_id": "scene_instance:main_demo:1",
		"binding_revision": 7,
		"semantic_type": "chair",
		"semantic_tags": ["chair", "kickable"],
		"authoritative_state_ref": "esm:object:chair_01",
		"local_binding": {
			"node_ref": "runtime://node/SceneAffordanceRegistryFixture/InteractiveObjectChair01",
			"collider_refs": ["collider:chair_01:body"],
			"navigation_footprint_ref": "nav:chair_01:footprint",
		},
		"anchors": [
			{"anchor_id": "anchor:chair_01:stance", "role": "approach_stance"},
			{"anchor_id": "anchor:chair_01:contact", "role": "contact"},
		],
		"affordances": [
			{
				"affordance_id": "affordance:chair_01:kick",
				"action_semantic": "kick",
				"preconditions": ["upright"],
				"execution_profile_ref": "execution_profile:kick:v1",
				"observation_rule_ref": "observation_rule:chair_tipped:v1",
				"policy_ref": "authority_policy:kick_chair:v1",
			}
		],
		"grounding_catalog_refs": {
			"entity_ref": "entity:scene_demo:chair_01",
			"collider_refs": ["collider:chair_01:body"],
			"anchor_refs": ["anchor:chair_01:stance", "anchor:chair_01:contact"],
		},
		"physical_profile_ref": "physical_profile:chair_rigidbody:v1",
		"visibility_policy": "public_safe",
		"binding_health": "healthy",
	}


func _grounding_catalog() -> Dictionary:
	return {
		"entity_refs": ["entity:scene_demo:chair_01"],
		"collider_refs": ["collider:chair_01:body"],
		"anchor_refs": ["anchor:chair_01:stance", "anchor:chair_01:contact"],
		"affordance_refs": ["affordance:chair_01:kick"],
	}


func _write_json(relative_path: String, payload: Dictionary) -> String:
	var path := ProjectSettings.globalize_path("res://" + relative_path)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return ""
	file.store_string(JSON.stringify(payload, "\t"))
	file.close()
	return path
