extends RefCounted

class_name CharacterActionAssetDescriptor


const COMPATIBILITY_LEVELS := CharacterAssetBindingProfile.COMPATIBILITY_LEVELS


static func normalize(candidate: Dictionary) -> Dictionary:
	return {
		"action_tag": str(candidate.get("action_tag", "")),
		"animation_clip_ref": candidate.get("animation_clip_ref", null),
		"root_motion_profile": candidate.get("root_motion_profile", null),
		"modifier_profile": candidate.get("modifier_profile", null),
		"equipment_override": candidate.get("equipment_override", {}),
		"required_slots": candidate.get("required_slots", []),
		"compatibility_level": str(candidate.get("compatibility_level", "locomotion_only")),
	}
