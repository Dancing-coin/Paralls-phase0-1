extends RefCounted
class_name MotionContribution
const KINDS := [&"input", &"root_motion", &"impulse", &"runtime_correction", &"gravity"]
const ROOT_POLICIES := [&"hold", &"bounded_continue", &"reversible_continue"]
const MAX_CORRECTION := 0.5
const MAX_ROOT_DELTA := 1.0
static func normalize(raw: Dictionary) -> Dictionary:
	if raw.has("transform") or raw.has("position") or raw.has("velocity"): return {"accepted": false, "reason": &"direct_body_write_forbidden"}
	var kind := StringName(raw.get("contribution_kind", "input"))
	if kind not in KINDS: return {"accepted": false, "reason": &"contribution_kind_invalid"}
	var policy := StringName(raw.get("root_motion_policy", "hold"))
	if policy not in ROOT_POLICIES: return {"accepted": false, "reason": &"root_motion_policy_invalid"}
	if not _is_vector(raw.get("desired_velocity", Vector3.ZERO)) or not _is_vector(raw.get("root_delta", Vector3.ZERO)) or not _is_vector(raw.get("impulse", Vector3.ZERO)) or not _is_vector(raw.get("runtime_correction", Vector3.ZERO)):
		return {"accepted": false, "reason": &"motion_vector_invalid"}
	return {"accepted": true, "actor_ref": StringName(raw.get("actor_ref", "")), "physics_tick": int(raw.get("physics_tick", -1)), "contribution_kind": kind, "source_kind": StringName(raw.get("source_kind", "locomotion")), "source_id": StringName(raw.get("source_id", "")), "action_instance_id": StringName(raw.get("action_instance_id", "")), "desired_velocity": raw.get("desired_velocity", Vector3.ZERO), "root_delta": raw.get("root_delta", Vector3.ZERO), "impulse": raw.get("impulse", Vector3.ZERO), "runtime_correction": raw.get("runtime_correction", Vector3.ZERO), "facing_yaw": float(raw.get("facing_yaw", 0.0)), "priority": int(raw.get("priority", 0)), "revision": int(raw.get("revision", 0)), "root_motion_policy": policy, "root_motion_envelope": raw.get("root_motion_envelope", {}).duplicate(true), "constraint_refs": raw.get("constraint_refs", []).duplicate()}

static func _is_vector(value: Variant) -> bool:
	return value is Vector3
