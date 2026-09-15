extends RefCounted
class_name MotionContributionComposer
const PhysicsMotionCommandRef = preload("res://scripts/character/PhysicsMotionCommand.gd")
const MAX_ROOT_DELTA := 1.0
const MAX_CORRECTION := 0.5
static func compose(frame: Dictionary, profile: Dictionary, _delta: float) -> Dictionary:
	var desired := Vector3.ZERO
	var root_delta := Vector3.ZERO
	var impulse := Vector3.ZERO
	var correction := Vector3.ZERO
	var facing := float(profile.get("facing_yaw", 0.0))
	for entry in frame.get("admitted", []):
		var move: Variant = entry.get("move_local", Vector2.ZERO)
		if move is Vector2: desired += Vector3(move.x, 0.0, move.y) * float(profile.get("speed", 4.0))
		root_delta += entry.get("root_delta", Vector3.ZERO)
		impulse += entry.get("impulse", Vector3.ZERO)
		correction += entry.get("runtime_correction", Vector3.ZERO)
		facing = float(entry.get("desired_facing_yaw", facing))
	return PhysicsMotionCommandRef.build(StringName(profile.get("actor_ref", "")), int(frame.get("physics_tick", -1)), desired, root_delta.limit_length(MAX_ROOT_DELTA), impulse, correction.limit_length(MAX_CORRECTION), facing, StringName("frame:%s" % frame.get("physics_tick", -1)))
static func apply_root_motion_policy(contribution: Dictionary, authority_state: StringName) -> Dictionary:
	var result := contribution.duplicate(true)
	var policy := StringName(contribution.get("root_motion_policy", "hold"))
	if policy == &"hold" and authority_state == &"pending": result["root_delta"] = Vector3.ZERO
	if policy in [&"bounded_continue", &"reversible_continue"] and not contribution.has("root_motion_envelope"): result["accepted"] = false; result["reason"] = &"root_motion_envelope_required"
	return result
