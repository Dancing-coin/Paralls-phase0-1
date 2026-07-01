extends RefCounted

class_name FactProjectionBridge


func project_probe_facts(actor_id: String, target_object_id: String, zone_id: String, occupancy: Dictionary) -> Array[Dictionary]:
	var zone_states: Dictionary = occupancy.get("zone_states", {})
	var zone: Dictionary = zone_states.get(zone_id, {})
	var facts: Array[Dictionary] = []
	if str(zone.get("visibility", "clear")) != "clear":
		facts.append(_raw_fact("line_of_sight_blocked", actor_id, target_object_id, zone_id, "blocked", true))
	if str(zone.get("passability", "passable")) != "passable":
		facts.append(_raw_fact("target_unreachable", actor_id, target_object_id, zone_id, str(zone.get("passability", "")), true))
	var object_states: Dictionary = occupancy.get("object_states", {})
	if object_states.has(target_object_id):
		var object_state: Dictionary = object_states[target_object_id]
		facts.append(_raw_fact("interaction_affordance_changed", actor_id, target_object_id, zone_id, ",".join(object_state.get("affordances", [])), false))
	return facts


func _raw_fact(fact_type: String, actor_id: String, target_object_id: String, zone_id: String, state_after: String, occluded: bool) -> Dictionary:
	var producer_ts := Time.get_ticks_msec()
	return {
		"event_type": "raw_fact_event",
		"fact_family": "spatial_access_fact",
		"fact_type": fact_type,
		"relation_type": "l1_world_fact_projection",
		"producer_ts": producer_ts,
		"room_id": "room_demo",
		"scene_id": "scene_demo",
		"zone_id": zone_id,
		"source": {
			"layer": "L1",
			"system": "godot.l1_fact_projection_bridge",
			"actor_id": actor_id,
			"object_id": "",
			"environment_id": "",
		},
		"targets": {
			"actor_id": actor_id,
			"object_id": target_object_id,
			"environment_id": "",
		},
		"world": {
			"state_after": state_after,
		},
		"observability": {
			"visual": true,
			"auditory": false,
			"occluded": occluded,
		},
		"effect_kind": "pulse",
		"subject_key": fact_type,
		"causation_id": "godot_l1_projection:%s" % producer_ts,
		"correlation_id": "godot_l1_projection:%s" % producer_ts,
	}
