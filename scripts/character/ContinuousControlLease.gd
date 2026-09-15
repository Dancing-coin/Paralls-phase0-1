extends RefCounted

class_name ContinuousControlLease


static func create(source_id: StringName, lease_id: StringName, revision: int, expires_at_tick: int, world_motion: Vector2, facing: float) -> Dictionary:
	return {
		"request_id": lease_id,
		"lease_id": lease_id,
		"kind": &"lease",
		"source_id": source_id,
		"revision": revision,
		"expires_at_tick": expires_at_tick,
		"move_local": world_motion,
		"desired_facing_yaw": facing,
		"claims": [&"world_motion", &"facing"],
		"priority": 0,
	}


static func is_active(lease: Dictionary, physics_tick: int) -> bool:
	return int(lease.get("expires_at_tick", -1)) >= physics_tick
