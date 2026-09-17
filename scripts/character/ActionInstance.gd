extends RefCounted

class_name ActionInstance

const LIFECYCLE := ["requested", "admitted", "queued", "windup", "contact", "recovery", "cancelled", "expired", "settled"]


static func create(action_instance_id: StringName, descriptor_id: StringName, source_id: StringName, target_ref: StringName, requested_tick: int) -> Dictionary:
	return {
		"request_id": action_instance_id,
		"action_instance_id": action_instance_id,
		"descriptor_id": descriptor_id,
		"source_id": source_id,
		"target_ref": target_ref,
		"requested_tick": requested_tick,
		"lifecycle": &"requested",
		"claims": [],
		"priority": 2,
		"cancellation_window": [],
	}


static func transition(instance: Dictionary, lifecycle: StringName) -> Dictionary:
	var result := instance.duplicate(true)
	if lifecycle in LIFECYCLE:
		result["lifecycle"] = lifecycle
	return result
