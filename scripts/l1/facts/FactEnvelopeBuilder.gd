extends RefCounted


func build_raw_fact_envelope(payload: Dictionary) -> Dictionary:
	return {
		"message_type": "raw_fact_event",
		"payload": payload.duplicate(true),
	}


func build_raw_fact_payload(
	fact_family: String,
	fact_type: String,
	relation_type: String,
	room_id: String,
	scene_id: String,
	zone_id: String,
	source_actor_id: String = "",
	source_object_id: String = "",
	source_environment_id: String = "",
	target_actor_id: String = "",
	target_object_id: String = "",
	target_environment_id: String = "",
	source_system: String = "godot.raw_fact_emitter",
	source_layer: String = "L1",
	world: Dictionary = {},
	observability: Dictionary = {},
	causation_id: String = "",
	correlation_id: String = "",
	producer_ts: int = -1
) -> Dictionary:
	var resolved_producer_ts := producer_ts if producer_ts >= 0 else Time.get_ticks_msec()
	return {
		"event_type": "raw_fact_event",
		"fact_family": fact_family,
		"fact_type": fact_type,
		"relation_type": relation_type,
		"producer_ts": resolved_producer_ts,
		"room_id": room_id,
		"scene_id": scene_id,
		"zone_id": zone_id,
		"source": {
			"layer": source_layer,
			"system": source_system,
			"actor_id": source_actor_id,
			"object_id": source_object_id,
			"environment_id": source_environment_id,
		},
		"targets": {
			"actor_id": target_actor_id,
			"object_id": target_object_id,
			"environment_id": target_environment_id,
		},
		"world": {
			"position": world.get("position", null),
			"distance_m": world.get("distance_m", null),
			"state_before": world.get("state_before", ""),
			"state_after": world.get("state_after", ""),
		},
		"observability": {
			"visual": observability.get("visual", false),
			"auditory": observability.get("auditory", false),
			"occluded": observability.get("occluded", false),
		},
		"causation_id": causation_id,
		"correlation_id": correlation_id,
	}
