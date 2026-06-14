extends RefCounted

class_name CharacterEquipmentBindingProfile


static func normalize(candidate: Dictionary) -> Dictionary:
	return {
		"slots": candidate.get("slots", []),
		"slot_anchor_paths": candidate.get("slot_anchor_paths", {}),
		"offset_defaults": candidate.get("offset_defaults", {}),
		"visibility_rules": candidate.get("visibility_rules", {}),
	}
