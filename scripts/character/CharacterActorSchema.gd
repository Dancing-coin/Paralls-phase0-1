extends RefCounted

class_name CharacterActorSchema


const MOTION_STATE_KEYS := {
	"position": true,
	"velocity_world": true,
	"facing_yaw": true,
	"camera_pitch": true,
	"move_local_actual": true,
	"gait_actual": true,
	"grounded": true,
}

const PRESENTATION_INPUT_KEYS := {
	"move_x": true,
	"move_y": true,
	"speed": true,
	"gait": true,
}


static func normalize_motion_state(candidate: Dictionary) -> Dictionary:
	return {
		"position": _as_vector3(candidate.get("position", Vector3.ZERO)),
		"velocity_world": _as_vector3(candidate.get("velocity_world", Vector3.ZERO)),
		"facing_yaw": float(candidate.get("facing_yaw", 0.0)),
		"camera_pitch": float(candidate.get("camera_pitch", 0.0)),
		"move_local_actual": _as_vector2(candidate.get("move_local_actual", Vector2.ZERO)),
		"gait_actual": str(candidate.get("gait_actual", "walk")),
		"grounded": bool(candidate.get("grounded", false)),
	}


static func normalize_presentation_input(candidate: Dictionary) -> Dictionary:
	return {
		"move_x": float(candidate.get("move_x", 0.0)),
		"move_y": float(candidate.get("move_y", 0.0)),
		"speed": float(candidate.get("speed", 0.0)),
		"gait": str(candidate.get("gait", "walk")),
	}


static func _as_vector2(value: Variant) -> Vector2:
	if value is Vector2:
		return value
	return Vector2.ZERO


static func _as_vector3(value: Variant) -> Vector3:
	if value is Vector3:
		return value
	return Vector3.ZERO
