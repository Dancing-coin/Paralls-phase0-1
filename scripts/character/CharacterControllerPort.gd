extends RefCounted

class_name CharacterControllerPort

const CharacterControlModeRef = preload("res://scripts/character/CharacterControlMode.gd")


static func normalize_intent_frame(candidate: Dictionary) -> Dictionary:
	var move_local_value: Variant = candidate.get("move_local", Vector2.ZERO)
	var move_local: Vector2 = move_local_value if move_local_value is Vector2 else Vector2.ZERO
	var look_local_value: Variant = candidate.get("look_local", Vector2.ZERO)
	var look_local: Vector2 = look_local_value if look_local_value is Vector2 else Vector2.ZERO
	var control_mode := str(candidate.get("control_mode", CharacterControlModeRef.PROGRAM_CONTROLLED))
	if not CharacterControlModeRef.is_valid(control_mode):
		control_mode = CharacterControlModeRef.PROGRAM_CONTROLLED
	var controller_source := str(candidate.get("controller_source", "program"))
	if controller_source.is_empty():
		controller_source = "program"

	return {
		"actor_id": str(candidate.get("actor_id", "")),
		"controller_source": controller_source,
		"control_mode": control_mode,
		"ttl_ms": int(candidate.get("ttl_ms", 0)),
		"causation_id": str(candidate.get("causation_id", "")),
		"correlation_id": str(candidate.get("correlation_id", "")),
		"move_local": move_local,
		"look_local": look_local,
		"desired_facing_yaw": float(candidate.get("desired_facing_yaw", 0.0)),
		"look_pitch": float(candidate.get("look_pitch", 0.0)),
		"stance": str(candidate.get("stance", "stand")),
		"gait": str(candidate.get("gait", "walk")),
		"action": str(candidate.get("action", "idle")),
	}


static func get_move_local(normalized_frame: Dictionary) -> Vector2:
	var move_local_value: Variant = normalized_frame.get("move_local", Vector2.ZERO)
	return move_local_value if move_local_value is Vector2 else Vector2.ZERO


static func get_actor_id(normalized_frame: Dictionary) -> String:
	return str(normalized_frame.get("actor_id", ""))


static func get_gait_name(normalized_frame: Dictionary) -> String:
	return str(normalized_frame.get("gait", "walk"))


static func get_action_name(normalized_frame: Dictionary) -> String:
	return str(normalized_frame.get("action", "idle"))


static func get_desired_facing_yaw(normalized_frame: Dictionary, fallback: float = 0.0) -> float:
	return float(normalized_frame.get("desired_facing_yaw", fallback))
