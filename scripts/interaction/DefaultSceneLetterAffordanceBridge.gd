extends Node

class_name DefaultSceneLetterAffordanceBridge

const SPACE_EXTRACTOR := preload("res://scripts/l1/space/SceneSpaceModelExtractor.gd")
const OCCUPANCY_SAMPLER := preload("res://scripts/l1/space/RuntimeOccupancySampler.gd")
const REGISTRY := preload("res://scripts/interaction/SceneAffordanceRegistry.gd")

const BINDING_REVISION := 1
const SCENE_INSTANCE_ID := "scene_instance:main_demo:1"

@export_node_path("Node3D") var target_object_path := NodePath("../InteractiveObject")
@export var object_id := "obj_letter"
@export var affordance_id := "affordance:obj_letter:inspect"
@export var semantic_type := "letter"
@export var semantic_tags := PackedStringArray(["letter", "inspectable", "readable"])
@export var policy_ref := "authority_policy:esm_inspect_letter:v1"
@export var supported_interaction_types := PackedStringArray(["inspect", "read"])
@export var primary_interaction_type := "inspect"
@export var default_interaction_by_state: Dictionary = {}
@export var action_semantic := "inspect"
@export var intent_route := "interact"
@export var state_preconditions := PackedStringArray(["partially_visible", "visible"])
@export var execution_profile_ref := "execution_profile:inspect:authority_only:v1"

var registry = REGISTRY.new()
var occupancy_sampler = OCCUPANCY_SAMPLER.new()
var initialized := false
var registration_status := "registry_uninitialized"


func _ready() -> void:
	var bus := _get_bus()
	if bus != null:
		bus.world_result_received.connect(_on_world_result_received)
	call_deferred("configure_reviewed_binding")


func configure_reviewed_binding() -> Dictionary:
	var target := _target_object()
	if target == null:
		registration_status = "registry_binding_unhealthy"
		return {"status": registration_status}
	var extractor = SPACE_EXTRACTOR.new()
	var scene_root: Node = get_parent()
	var space_model: Dictionary = extractor.extract(scene_root)
	occupancy_sampler.initialize_from_space_model(space_model)
	_refresh_local_occupancy(target)
	registry.configure(
		space_model,
		occupancy_sampler.snapshot(),
		_grounding_catalog(),
		Time.get_ticks_msec(),
		30000
	)
	var result: Dictionary = registry.register_reviewed_record(_record(target))
	registration_status = str(result.get("status", "registry_binding_unhealthy"))
	initialized = registration_status == "registered"
	return result


func resolve_interaction(target_object_id: String, interaction_type: String) -> Dictionary:
	if not handles_interaction(target_object_id, interaction_type):
		return {"status": "not_applicable"}
	if not initialized:
		return {"status": registration_status}
	var target := _target_object()
	if target == null:
		return {"status": "registry_binding_unhealthy"}
	_refresh_local_occupancy(target)
	registry.current_tick = Time.get_ticks_msec()
	return registry.resolve(
		"scene_demo",
		SCENE_INSTANCE_ID,
		object_id,
		affordance_id,
		BINDING_REVISION,
		["approach_stance", "observation"],
		"controller"
	)


func handles_interaction(target_object_id: String, interaction_type: String) -> bool:
	return target_object_id == object_id and interaction_type in supported_interaction_types


func default_interaction_type(target_object_id: String) -> String:
	if target_object_id != object_id:
		return ""
	var target := _target_object()
	if target != null:
		var state_selected := str(default_interaction_by_state.get(str(target.get("current_state")), ""))
		if state_selected in supported_interaction_types:
			return state_selected
	if primary_interaction_type not in supported_interaction_types:
		return ""
	return primary_interaction_type


func route_for_interaction(target_object_id: String, interaction_type: String) -> String:
	if not handles_interaction(target_object_id, interaction_type):
		return ""
	return intent_route


func _on_world_result_received(payload: Dictionary) -> void:
	if str(payload.get("result_type", "")) != "object_state_result":
		return
	if str(payload.get("target_object_id", "")) != object_id:
		return
	var current_state := str(payload.get("current_state", ""))
	if current_state.is_empty():
		return
	occupancy_sampler.apply_object_state(
		object_id,
		"zone_focus",
		current_state,
		supported_interaction_types,
		false,
		str(payload.get("result_id", "world_result:%s" % object_id))
	)
	registry.occupancy_snapshot = occupancy_sampler.snapshot()
	registry.current_tick = Time.get_ticks_msec()


func _refresh_local_occupancy(target: Node3D) -> void:
	# This is a local spatial-freshness sample only; authority still settles object truth.
	occupancy_sampler.apply_object_state(
		object_id,
		"zone_focus",
		str(target.get("current_state")),
		supported_interaction_types,
		false,
		"local_observation:%s" % object_id
	)
	registry.occupancy_snapshot = occupancy_sampler.snapshot()


func _target_object() -> Node3D:
	return get_node_or_null(target_object_path) as Node3D


func _record(target: Node3D) -> Dictionary:
	return {
		"entity_ref": object_id,
		"scene_id": "scene_demo",
		"scene_instance_id": SCENE_INSTANCE_ID,
		"binding_revision": BINDING_REVISION,
		"semantic_type": semantic_type,
		"semantic_tags": semantic_tags,
		"authoritative_state_ref": "esm:object:%s" % object_id,
		"local_binding": {
			"node_ref": "runtime://node%s" % str(target.get_path()),
			"collider_refs": ["collider:%s:body" % object_id],
			"navigation_footprint_ref": "nav:%s:approach_footprint" % object_id,
		},
		"anchors": [
			{"anchor_id": "anchor:%s:stance" % object_id, "role": "approach_stance"},
			{"anchor_id": "anchor:%s:observation" % object_id, "role": "observation"},
		],
		"affordances": [
			{
				"affordance_id": affordance_id,
				"action_semantic": action_semantic,
				"preconditions": state_preconditions,
				"execution_profile_ref": execution_profile_ref,
				"observation_rule_ref": "observation_rule:%s_visible:v1" % semantic_type,
				"policy_ref": policy_ref,
			}
		],
		"grounding_catalog_refs": {
			"entity_ref": object_id,
			"collider_refs": ["collider:%s:body" % object_id],
			"anchor_refs": ["anchor:%s:stance" % object_id, "anchor:%s:observation" % object_id],
		},
		"physical_profile_ref": "physical_profile:%s_static:v1" % semantic_type,
		"visibility_policy": "public_safe",
		"binding_health": "healthy",
	}


func _grounding_catalog() -> Dictionary:
	return {
		"entity_refs": [object_id],
		"collider_refs": ["collider:%s:body" % object_id],
		"anchor_refs": ["anchor:%s:stance" % object_id, "anchor:%s:observation" % object_id],
		"affordance_refs": [affordance_id],
	}


func _get_bus() -> Node:
	return get_node_or_null("/root/LocalPresentationBus")
