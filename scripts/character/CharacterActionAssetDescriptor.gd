extends RefCounted

class_name CharacterActionAssetDescriptor


const COMPATIBILITY_LEVELS := CharacterAssetBindingProfile.COMPATIBILITY_LEVELS
const ROOT_MOTION_POLICIES := [&"hold", &"bounded_continue", &"reversible_continue"]


static func normalize(candidate: Dictionary) -> Dictionary:
	var atomic_sequence: Array[StringName] = []
	var raw_atomic_sequence: Variant = candidate.get("atomic_sequence", [])
	if raw_atomic_sequence is Array:
		for atom in raw_atomic_sequence:
			var atom_id := StringName(str(atom))
			if String(atom_id).is_empty():
				continue
			atomic_sequence.append(atom_id)
	var root_motion_envelope: Dictionary = {}
	var raw_envelope: Variant = candidate.get("root_motion_envelope", {})
	if raw_envelope is Dictionary:
		root_motion_envelope = raw_envelope.duplicate(true)
	return {
		"action_tag": str(candidate.get("action_tag", "")),
		"atomic_sequence": atomic_sequence,
		"resource_claims": candidate.get("resource_claims", []),
		"physics_claims": candidate.get("physics_claims", []),
		"physics_profile_ref": str(candidate.get("physics_profile_ref", "")),
		"authority_route_ref": str(candidate.get("authority_route_ref", "")),
		"animation_clip_ref": candidate.get("animation_clip_ref", null),
		"root_motion_profile": candidate.get("root_motion_profile", null),
		"root_motion_policy": str(candidate.get("root_motion_policy", "hold")),
		"root_motion_envelope": root_motion_envelope,
		"modifier_profile": candidate.get("modifier_profile", null),
		"equipment_override": candidate.get("equipment_override", {}),
		"required_slots": candidate.get("required_slots", []),
		"compatibility_level": str(candidate.get("compatibility_level", "locomotion_only")),
	}


static func validate_root_motion_descriptor(candidate: Dictionary) -> Dictionary:
	var policy := StringName(candidate.get("root_motion_policy", "hold"))
	if policy not in ROOT_MOTION_POLICIES:
		return {"accepted": false, "reason": &"root_motion_policy_invalid"}
	var raw_envelope: Variant = candidate.get("root_motion_envelope", {})
	if raw_envelope == null:
		raw_envelope = {}
	if not (raw_envelope is Dictionary):
		return {"accepted": false, "reason": &"root_motion_envelope_invalid"}
	var envelope: Dictionary = raw_envelope
	if policy in [&"bounded_continue", &"reversible_continue"]:
		var max_distance := float(envelope.get("max_distance", 0.0))
		var max_duration_ticks := int(envelope.get("max_duration_ticks", 0))
		if max_distance <= 0.0 or max_duration_ticks <= 0:
			return {"accepted": false, "reason": &"root_motion_envelope_required"}
		return {
			"accepted": true,
			"root_motion_policy": policy,
			"root_motion_envelope": {"max_distance": max_distance, "max_duration_ticks": max_duration_ticks},
		}
	return {"accepted": true, "root_motion_policy": policy, "root_motion_envelope": envelope.duplicate(true)}
