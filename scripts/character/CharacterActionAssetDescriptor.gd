extends RefCounted

class_name CharacterActionAssetDescriptor


const COMPATIBILITY_LEVELS := CharacterAssetBindingProfile.COMPATIBILITY_LEVELS


static func normalize(candidate: Dictionary) -> Dictionary:
	var atomic_sequence: Array[StringName] = []
	var raw_atomic_sequence: Variant = candidate.get("atomic_sequence", [])
	if raw_atomic_sequence is Array:
		for atom in raw_atomic_sequence:
			var atom_id := StringName(str(atom))
			if String(atom_id).is_empty():
				continue
			atomic_sequence.append(atom_id)
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
		"modifier_profile": candidate.get("modifier_profile", null),
		"equipment_override": candidate.get("equipment_override", {}),
		"required_slots": candidate.get("required_slots", []),
		"compatibility_level": str(candidate.get("compatibility_level", "locomotion_only")),
	}
