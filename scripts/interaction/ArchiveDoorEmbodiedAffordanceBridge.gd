extends Node

class_name ArchiveDoorEmbodiedAffordanceBridge

const SPACE_EXTRACTOR := preload("res://scripts/l1/space/SceneSpaceModelExtractor.gd")
const OCCUPANCY_SAMPLER := preload("res://scripts/l1/space/RuntimeOccupancySampler.gd")
const REGISTRY := preload("res://scripts/interaction/SceneAffordanceRegistry.gd")

const BINDING_REVISION := 2
const SCENE_INSTANCE_ID := "scene_instance:main_demo:1"
const OBJECT_ID := "obj_archive_door"
const AFFORDANCE_ID := "affordance:obj_archive_door:open"

@export_node_path("Node3D") var door_path := NodePath("../ArchiveDoorPhysical")
@export_node_path("Marker3D") var approach_stance_path := NodePath("../ArchiveDoorPhysical/ApproachStance")
@export_node_path("Marker3D") var contact_anchor_path := NodePath("../ArchiveDoorPhysical/ContactAnchor")
@export_node_path("Marker3D") var observation_anchor_path := NodePath("../ArchiveDoorPhysical/ObservationAnchor")
@export_node_path("Node") var presentation_path := NodePath("../ArchiveDoorPhysical/ArchiveDoorPhysicalPresentation")

var registry = REGISTRY.new()
var occupancy_sampler = OCCUPANCY_SAMPLER.new()
var initialized := false
var registration_status := "registry_uninitialized"
var _stance_lease_owner_id := 0
var _stance_lease_ref := ""


func _ready() -> void:
	var bus := _get_bus()
	if bus != null and bus.has_signal("world_result_received"):
		bus.world_result_received.connect(_on_world_result_received)
	call_deferred("configure_reviewed_binding")


func configure_reviewed_binding() -> Dictionary:
	if _door() == null or _approach_stance() == null or _contact_anchor() == null or _observation_anchor() == null:
		registration_status = "registry_binding_unhealthy"
		return {"status": registration_status}
	var extractor = SPACE_EXTRACTOR.new()
	var space_model: Dictionary = extractor.extract(get_parent())
	occupancy_sampler.initialize_from_space_model(space_model)
	_refresh_local_occupancy()
	registry.configure(space_model, occupancy_sampler.snapshot(), _grounding_catalog(), Time.get_ticks_msec(), 30000)
	var result: Dictionary = registry.register_reviewed_record(_record())
	registration_status = str(result.get("status", "registry_binding_unhealthy"))
	initialized = registration_status == "registered"
	return result


func handles_interaction(target_object_id: String, interaction_type: String) -> bool:
	return target_object_id == OBJECT_ID and interaction_type == "open"


func default_interaction_type(target_object_id: String) -> String:
	if target_object_id != OBJECT_ID or _current_state() != "closed":
		return ""
	return "open"


func route_for_interaction(target_object_id: String, interaction_type: String) -> String:
	return "interact" if handles_interaction(target_object_id, interaction_type) else ""


func resolve_interaction(target_object_id: String, interaction_type: String) -> Dictionary:
	if not handles_interaction(target_object_id, interaction_type):
		return {"status": "not_applicable"}
	if not initialized:
		return {"status": registration_status}
	_refresh_local_occupancy()
	registry.current_tick = Time.get_ticks_msec()
	return registry.resolve(
		"scene_demo",
		SCENE_INSTANCE_ID,
		OBJECT_ID,
		AFFORDANCE_ID,
		BINDING_REVISION,
		["approach_stance", "contact", "observation"],
		"controller"
	)


func runtime_binding() -> Dictionary:
	return {
		"object_id": OBJECT_ID,
		"affordance_id": AFFORDANCE_ID,
		"binding_revision": BINDING_REVISION,
		"approach_stance": _approach_stance(),
		"contact_anchor": _contact_anchor(),
		"observation_anchor": _observation_anchor(),
		"presentation": _presentation(),
	}


func reserve_stance_lease(actor_body: CharacterBody3D, lease_ref: String) -> bool:
	if actor_body == null or lease_ref.is_empty():
		return false
	if _stance_lease_owner_id == actor_body.get_instance_id():
		_stance_lease_ref = lease_ref
		return true
	if _stance_lease_owner_id != 0:
		return false
	if not _is_stance_clear(actor_body):
		return false
	_stance_lease_owner_id = actor_body.get_instance_id()
	_stance_lease_ref = lease_ref
	return true


func release_stance_lease(actor_body: CharacterBody3D, lease_ref: String = "") -> void:
	if actor_body == null:
		return
	if _stance_lease_owner_id != actor_body.get_instance_id():
		return
	if not lease_ref.is_empty() and _stance_lease_ref != lease_ref:
		return
	_stance_lease_owner_id = 0
	_stance_lease_ref = ""


func is_approach_obstructed(from_position: Vector3, to_position: Vector3, exclude: Array = []) -> bool:
	var door := _door()
	if door == null or door.get_world_3d() == null:
		return false
	var start := from_position + Vector3.UP * 0.5
	var finish := to_position + Vector3.UP * 0.5
	if start.distance_to(finish) <= 0.05:
		return false
	var query := PhysicsRayQueryParameters3D.create(start, finish)
	query.exclude = exclude
	var hit: Dictionary = door.get_world_3d().direct_space_state.intersect_ray(query)
	if hit.is_empty():
		return false
	var collider: Variant = hit.get("collider")
	return not _is_door_collider(collider)


func _on_world_result_received(payload: Dictionary) -> void:
	if str(payload.get("result_type", "")) != "object_state_result":
		return
	if str(payload.get("target_object_id", "")) != OBJECT_ID:
		return
	if str(payload.get("settlement_status", "")) != "applied":
		return
	_refresh_local_occupancy(str(payload.get("result_id", "world_result:%s" % OBJECT_ID)))


func _refresh_local_occupancy(source_ref: String = "") -> void:
	occupancy_sampler.apply_object_state(
		OBJECT_ID,
		"zone_focus",
		_current_state(),
		["open"],
		_current_state() == "closed",
		source_ref if not source_ref.is_empty() else "local_observation:%s" % OBJECT_ID
	)
	registry.occupancy_snapshot = occupancy_sampler.snapshot()


func _record() -> Dictionary:
	return {
		"entity_ref": OBJECT_ID,
		"scene_id": "scene_demo",
		"scene_instance_id": SCENE_INSTANCE_ID,
		"binding_revision": BINDING_REVISION,
		"semantic_type": "door",
		"semantic_tags": ["door", "openable", "archive_access", "physical_embodiment"],
		"authoritative_state_ref": "esm:object:%s" % OBJECT_ID,
		"local_binding": {
			"node_ref": "runtime://node%s" % str(_door().get_path()),
			"collider_refs": ["collider:obj_archive_door:body"],
			"navigation_footprint_ref": "nav:obj_archive_door:approach_footprint",
		},
		"anchors": [
			{"anchor_id": "anchor:obj_archive_door:stance", "role": "approach_stance"},
			{"anchor_id": "anchor:obj_archive_door:contact", "role": "contact"},
			{"anchor_id": "anchor:obj_archive_door:observation", "role": "observation"},
		],
		"affordances": [{
			"affordance_id": AFFORDANCE_ID,
			"action_semantic": "open",
			"preconditions": ["closed"],
			"execution_profile_ref": "execution_profile:obj_archive_door:open:v1",
			"observation_rule_ref": "observation_rule:archive_door_contact:v1",
			"policy_ref": "authority_policy:esm_open_archive_door:v1",
		}],
		"grounding_catalog_refs": {
			"entity_ref": OBJECT_ID,
			"collider_refs": ["collider:obj_archive_door:body"],
			"anchor_refs": [
				"anchor:obj_archive_door:stance",
				"anchor:obj_archive_door:contact",
				"anchor:obj_archive_door:observation",
			],
		},
		"physical_profile_ref": "physical_profile:archive_door_hinged:v1",
		"visibility_policy": "public_safe",
		"binding_health": "healthy",
	}


func _grounding_catalog() -> Dictionary:
	return {
		"entity_refs": [OBJECT_ID],
		"collider_refs": ["collider:obj_archive_door:body"],
		"anchor_refs": [
			"anchor:obj_archive_door:stance",
			"anchor:obj_archive_door:contact",
			"anchor:obj_archive_door:observation",
		],
		"affordance_refs": [AFFORDANCE_ID],
	}


func _door() -> Node3D:
	return get_node_or_null(door_path) as Node3D


func _approach_stance() -> Marker3D:
	return get_node_or_null(approach_stance_path) as Marker3D


func _contact_anchor() -> Marker3D:
	return get_node_or_null(contact_anchor_path) as Marker3D


func _observation_anchor() -> Marker3D:
	return get_node_or_null(observation_anchor_path) as Marker3D


func _presentation() -> Node:
	return get_node_or_null(presentation_path)


func _current_state() -> String:
	var presentation := _presentation()
	return str(presentation.get("current_state")) if presentation != null else "closed"


func _is_stance_clear(actor_body: CharacterBody3D) -> bool:
	var stance := _approach_stance()
	if stance == null:
		return false
	var scene := get_tree().current_scene
	if scene == null:
		return true
	return _scan_stance_clear(scene, actor_body, stance.global_position)


func _scan_stance_clear(node: Node, actor_body: CharacterBody3D, stance_position: Vector3) -> bool:
	if node is CharacterBody3D:
		var candidate := node as CharacterBody3D
		if candidate != actor_body and candidate.global_position.distance_to(stance_position) <= 0.75:
			return false
	for child in node.get_children():
		if not _scan_stance_clear(child, actor_body, stance_position):
			return false
	return true


func _is_door_collider(collider: Variant) -> bool:
	if collider == null:
		return false
	var door := _door()
	if collider == door:
		return true
	if collider is Node and door != null:
		return door.is_ancestor_of(collider as Node)
	return false


func _get_bus() -> Node:
	return get_node_or_null("/root/LocalPresentationBus")
