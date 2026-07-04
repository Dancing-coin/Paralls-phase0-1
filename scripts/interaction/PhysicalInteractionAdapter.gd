extends Node

class_name PhysicalInteractionAdapter

@export var structured_refs_only := true
@export var bypass_semantic_authority_allowed := false
@export var second_world_result_protocol_allowed := false


func build_physical_effect_ref(actor_id: String, target_object_id: String, effect_kind: String, contact_payload: Dictionary) -> Dictionary:
	var now := Time.get_ticks_msec()
	return {
		"request_id": "godot_physical_request:%s:%s:%s" % [actor_id, target_object_id, now],
		"actor_id": actor_id,
		"target_object_id": target_object_id,
		"effect_kind": effect_kind,
		"contact_observation": contact_payload,
		"structured_physical_effect_refs": [
			"godot_physical_effect:%s:%s:%s" % [effect_kind, target_object_id, now],
		],
		"object_state_observation_refs": [
			"godot_object_state_obs:%s:%s" % [target_object_id, now],
		],
		"environment_state_observation_refs": [
			"godot_environment_state_obs:zone_focus:%s" % now,
		],
		"body_state_observation_refs": [
			"godot_body_state_obs:%s:%s" % [actor_id, now],
		],
		"feeds_interaction_orchestration": true,
	}
