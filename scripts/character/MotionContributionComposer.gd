extends RefCounted
class_name MotionContributionComposer
const PhysicsMotionCommandRef = preload("res://scripts/character/PhysicsMotionCommand.gd")
const MotionContributionRef = preload("res://scripts/character/MotionContribution.gd")
const MAX_ROOT_DELTA := 1.0
const MAX_CORRECTION := 0.5
static func compose(frame: Dictionary, profile: Dictionary, _delta: float) -> Dictionary:
	var desired := Vector3.ZERO
	var root_delta := Vector3.ZERO
	var impulse := Vector3.ZERO
	var correction := Vector3.ZERO
	var facing := float(profile.get("facing_yaw", 0.0))
	var admitted: Array[Dictionary] = []
	for raw_entry in frame.get("admitted", []):
		var entry: Dictionary = raw_entry.duplicate(true)
		var move: Variant = entry.get("move_local", Vector2.ZERO)
		if move is Vector2 and desired == Vector3.ZERO:
			desired = Vector3(move.x, 0.0, move.y) * float(profile.get("speed", 4.0))
		var normalized := MotionContributionRef.normalize(entry)
		if bool(normalized.get("accepted", false)):
			admitted.append(normalized)
			facing = float(entry.get("desired_facing_yaw", facing))
	# Root motion and impulses are deterministic by action identity, independent of input order.
	admitted.sort_custom(_sort_action_contributions)
	for contribution in admitted:
		var policy_result := apply_root_motion_policy(contribution, StringName(contribution.get("authority_state", "accepted")))
		if not bool(policy_result.get("accepted", false)):
			continue
		root_delta += policy_result.get("root_delta", Vector3.ZERO)
		impulse += contribution.get("impulse", Vector3.ZERO)
		var correction_result := filter_runtime_correction(contribution, int(profile.get("projection_revision", 0)))
		correction += correction_result.get("runtime_correction", Vector3.ZERO)
	var actor_id := StringName(str(profile.get("actor_id", profile.get("actor_ref", frame.get("actor_id", "")))))
	var physics_tick := int(frame.get("physics_tick", profile.get("physics_tick", -1)))
	var root_delta_local := root_delta.limit_length(MAX_ROOT_DELTA)
	var source_digest := StringName("frame:%s:%s" % [physics_tick, actor_id])
	var command := PhysicsMotionCommandRef.build(actor_id, physics_tick, desired, root_delta_local, impulse, correction.limit_length(MAX_CORRECTION), facing, source_digest)
	# Stable aliases make the command a typed cross-controller contract.  The
	# Motor consumes the token once per actor/tick; callers may still use the
	# historical actor_ref/root_delta fields during migration.
	command["actor_id"] = actor_id
	command["move_local"] = Vector2(desired.x, desired.z)
	command["root_delta_local"] = root_delta_local
	command["root_policy"] = StringName("hold") if root_delta_local.length() <= 0.0001 else StringName("bounded_continue")
	command["consumption_token"] = StringName("%s:%s:%s" % [actor_id, physics_tick, source_digest])
	command["source_digest"] = source_digest
	command["vertical_mode"] = StringName(profile.get("vertical_mode", "gravity"))
	command["collision_policy"] = StringName(profile.get("collision_policy", "slide"))
	command["support_requirements"] = profile.get("support_requirements", []).duplicate()
	command["composition_order"] = [&"locomotion", &"root_motion", &"impulse", &"runtime_correction"]
	command["root_delta_local"] = command.get("root_delta", Vector3.ZERO)
	return command

static func _sort_action_contributions(left: Dictionary, right: Dictionary) -> bool:
	return str(left.get("action_instance_id", "")) < str(right.get("action_instance_id", ""))

static func apply_root_motion_policy(contribution: Dictionary, authority_state: StringName) -> Dictionary:
	var result := contribution.duplicate(true)
	result["accepted"] = bool(contribution.get("accepted", true))
	var policy := StringName(contribution.get("root_motion_policy", "hold"))
	if policy not in MotionContributionRef.ROOT_POLICIES:
		result["accepted"] = false
		result["reason"] = &"root_motion_policy_invalid"
		return result
	var envelope: Dictionary = contribution.get("root_motion_envelope", {})
	if policy in [&"bounded_continue", &"reversible_continue"]:
		var max_distance := float(envelope.get("max_distance", 0.0))
		var max_ticks := int(envelope.get("max_duration_ticks", 0))
		if max_distance <= 0.0 or max_ticks <= 0:
			result["accepted"] = false
			result["reason"] = &"root_motion_envelope_required"
			return result
		result["root_delta"] = (contribution.get("root_delta", Vector3.ZERO) as Vector3).limit_length(min(max_distance, MAX_ROOT_DELTA))
		result["root_motion_envelope"] = {"max_distance": max_distance, "max_duration_ticks": max_ticks}
		if policy == &"reversible_continue":
			result["recovery_reverse_delta"] = -(result["root_delta"] as Vector3)
	if authority_state == &"unknown":
		result["root_delta"] = Vector3.ZERO
		result["unsafe_frozen"] = true
	elif policy == &"hold" and authority_state == &"pending":
		result["root_delta"] = Vector3.ZERO
	if authority_state in [&"rejected", &"timed_out", &"cancelled", &"target_invalid"]:
		result["root_delta"] = Vector3.ZERO
		result["runtime_correction"] = result.get("recovery_reverse_delta", Vector3.ZERO)
	return result

static func filter_runtime_correction(contribution: Dictionary, projection_revision: int) -> Dictionary:
	var result := contribution.duplicate(true)
	var correction_revision := int(contribution.get("projection_revision", projection_revision))
	if correction_revision < projection_revision:
		result["runtime_correction"] = Vector3.ZERO
		result["stale_ignored"] = true
		result["resync_required"] = true
	return result
