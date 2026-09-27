extends RefCounted

class_name CharacterActionAssetDescriptor


const COMPATIBILITY_LEVELS := CharacterAssetBindingProfile.COMPATIBILITY_LEVELS
const ROOT_MOTION_POLICIES := [&"hold", &"bounded_continue", &"reversible_continue"]
const REALIZATION_MODES := [&"native_upper_body", &"derived_upper_body", &"full_body_exclusive", &"drive_locomotion", &"additive"]
const LOCOMOTION_RELATIONS := [&"coexist", &"drive_locomotion", &"replace_locomotion", &"suspend"]
const FORBIDDEN_TRUTH_FIELDS := [&"transform", &"global_position", &"velocity", &"damage", &"hit", &"inventory", &"status", &"action_attempt", &"esm", &"gameplay"]


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
		"semantic_action_id": str(candidate.get("semantic_action_id", candidate.get("action_tag", ""))),
		"action_tag": str(candidate.get("action_tag", "")),
		"atomic_sequence": atomic_sequence,
		"required_clips": candidate.get("required_clips", []),
		"optional_clips": candidate.get("optional_clips", []),
		"realization_profiles": candidate.get("realization_profiles", []),
		"realization_profile": candidate.get("realization_profile", {}),
		"canonical_skeleton_mapping_ref": str(candidate.get("canonical_skeleton_mapping_ref", "")),
		"canonical_bone_mask_ref": str(candidate.get("canonical_bone_mask_ref", "")),
		"resource_claims": candidate.get("resource_claims", []),
		"physics_claims": candidate.get("physics_claims", []),
		"physics_profile_ref": str(candidate.get("physics_profile_ref", "")),
		"authority_route_ref": str(candidate.get("authority_route_ref", "")),
		"animation_clip_ref": candidate.get("animation_clip_ref", null),
		"source_clip_ref": str(candidate.get("source_clip_ref", candidate.get("animation_clip_ref", ""))),
		"derived_clip_ref": str(candidate.get("derived_clip_ref", "")),
		"derived_from_clip_ref": str(candidate.get("derived_from_clip_ref", "")),
		"locomotion_compatibility": str(candidate.get("locomotion_compatibility", "")),
		"root_motion_profile": candidate.get("root_motion_profile", null),
		"root_motion_policy": str(candidate.get("root_motion_policy", "hold")),
		"root_motion_envelope": root_motion_envelope,
		"timing_markers": candidate.get("timing_markers", candidate.get("markers", [])),
		"cancel_windows": candidate.get("cancel_windows", []),
		"modifier_profile": candidate.get("modifier_profile", null),
		"equipment_override": candidate.get("equipment_override", {}),
		"required_slots": candidate.get("required_slots", []),
		"fallback": candidate.get("fallback", {}),
		"fallback_policy": str(candidate.get("fallback_policy", "")),
		"qualification_report_ref": str(candidate.get("qualification_report_ref", "")),
		"package_digest": str(candidate.get("package_digest", "")),
		"compatibility_level": str(candidate.get("compatibility_level", "locomotion_only")),
	}


static func validate_phase1(candidate: Dictionary) -> Dictionary:
	var descriptor := normalize(candidate)
	if not (descriptor.get("atomic_sequence", []) as Array).is_empty():
		return {"accepted": false, "reason": &"atomic_sequence_forbidden"}
	for field in FORBIDDEN_TRUTH_FIELDS:
		if candidate.has(String(field)):
			return {"accepted": false, "reason": StringName("world_truth_field_forbidden:%s" % field)}
	if str(descriptor.get("semantic_action_id", "")).is_empty():
		return {"accepted": false, "reason": &"semantic_action_id_missing"}
	if str(descriptor.get("authority_route_ref", "")) not in ["esm", "gameplay", "composite"]:
		return {"accepted": false, "reason": &"authority_route_invalid"}
	if not (descriptor.get("resource_claims", []) is Array) or not (descriptor.get("physics_claims", []) is Array):
		return {"accepted": false, "reason": &"claims_invalid"}
	if str(descriptor.get("locomotion_compatibility", "")) not in LOCOMOTION_RELATIONS:
		return {"accepted": false, "reason": &"locomotion_compatibility_invalid"}
	if str(descriptor.get("physics_profile_ref", "")).is_empty():
		return {"accepted": false, "reason": &"physics_profile_missing"}
	var root_motion_validation := validate_root_motion_descriptor(descriptor)
	if not bool(root_motion_validation.get("accepted", false)):
		return root_motion_validation
	return {"accepted": true, "descriptor": descriptor}


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
