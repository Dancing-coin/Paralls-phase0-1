extends RefCounted
class_name CharacterControlIntent

const DEFAULT_SOURCE_KIND := "compatibility"
const DEFAULT_JUMP_TYPE := "none"
const DEFAULT_ACTION_ID := ""
const DEFAULT_TARGET_REF := ""
const DEFAULT_GAIT := "idle"
const DEFAULT_STANCE := "stand"
const SOURCE_KINDS := ["player", "agent", "program", "compatibility"]

static func create(
	move_direction: Vector3 = Vector3.ZERO,
	wants_run: bool = false,
	jump_type: StringName = &"none",
	action_id: StringName = &"",
	source_kind: StringName = &"compatibility",
	target_ref: StringName = &"",
) -> Dictionary:
	var normalized_source := _normalize_source_kind(source_kind)
	var normalized_jump := str(jump_type) if not str(jump_type).is_empty() else DEFAULT_JUMP_TYPE
	var normalized_action := str(action_id)
	var normalized_target := str(target_ref)
	var planar := Vector3(move_direction.x, 0.0, move_direction.z)
	var gait := "run" if wants_run and planar.length() > 0.001 else ("walk" if planar.length() > 0.001 else DEFAULT_GAIT)
	var intent := {
		"move_direction": planar,
		"move_local": Vector2(planar.x, planar.z),
		"wants_run": wants_run,
		"jump_type": normalized_jump,
		"action_id": normalized_action if not normalized_action.is_empty() else DEFAULT_ACTION_ID,
		"source_kind": normalized_source,
		"target_ref": normalized_target if not normalized_target.is_empty() else DEFAULT_TARGET_REF,
		"gait": gait,
		"stance": DEFAULT_STANCE,
		"physics_tick": Engine.get_physics_frames(),
	}
	intent["source_digest"] = digest({"source_kind": normalized_source, "target_ref": intent["target_ref"]})
	intent["intent_digest"] = digest(intent)
	return intent

static func normalize(candidate: Dictionary) -> Dictionary:
	var move_value: Variant = candidate.get("move_direction", candidate.get("move_world", Vector3.ZERO))
	var move: Vector3 = move_value if move_value is Vector3 else Vector3.ZERO
	var intent := create(
		move,
		bool(candidate.get("wants_run", candidate.get("gait", "") == "run")),
		StringName(candidate.get("jump_type", DEFAULT_JUMP_TYPE)),
		StringName(candidate.get("action_id", DEFAULT_ACTION_ID)),
		StringName(candidate.get("source_kind", DEFAULT_SOURCE_KIND)),
		StringName(candidate.get("target_ref", DEFAULT_TARGET_REF)),
	)
	for key in ["actor_id", "causation_id", "correlation_id", "look_target", "stance", "gait"]:
		if candidate.has(key):
			intent[key] = candidate[key]
	intent["physics_tick"] = int(candidate.get("physics_tick", intent["physics_tick"]))
	intent["source_digest"] = digest({"source_kind": intent["source_kind"], "target_ref": intent["target_ref"]})
	intent["intent_digest"] = digest(intent)
	return intent

static func digest(value: Variant) -> String:
	return "%016x" % (hash(JSON.stringify(value)) & 0x7fffffffffffffff)

static func _normalize_source_kind(value: StringName) -> String:
	var source := str(value)
	return source if source in SOURCE_KINDS else DEFAULT_SOURCE_KIND
