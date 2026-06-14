extends RefCounted

class_name CharacterAssetBindingProfile


const COMPATIBILITY_LEVELS := [
	"locomotion_only",
	"locomotion_plus_equipment",
	"full_action_ready",
	"binder_ready",
]


static func normalize(candidate: Dictionary) -> Dictionary:
	return {
		"role_asset_id": str(candidate.get("role_asset_id", "")),
		"skeleton_profile_id": str(candidate.get("skeleton_profile_id", "")),
		"equipment_slots": candidate.get("equipment_slots", []),
		"supported_action_tags": candidate.get("supported_action_tags", []),
		"supported_expression_tags": candidate.get("supported_expression_tags", []),
		"locomotion_binding_mode": str(candidate.get("locomotion_binding_mode", "physics")),
		"compatibility_level": str(candidate.get("compatibility_level", "locomotion_only")),
	}
