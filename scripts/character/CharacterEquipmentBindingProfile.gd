extends RefCounted

class_name CharacterEquipmentBindingProfile

const REQUIRED_WEAPON_SLOT_IDS := [&"weapon_hand", &"weapon_slot:sword", &"weapon_hit_volume:sword"]

var _slots: Dictionary = {}


func _init(candidate: Dictionary = {}) -> void:
	_slots = normalize(candidate).get("slots", {})


static func normalize(candidate: Dictionary) -> Dictionary:
	var normalized_slots: Dictionary = {}
	var raw_slots: Variant = candidate.get("slots", {})
	if raw_slots is Dictionary:
		for raw_slot_id in raw_slots:
			var slot_id := StringName(str(raw_slot_id))
			var raw_slot: Variant = raw_slots[raw_slot_id]
			if String(slot_id).is_empty() or not (raw_slot is Dictionary):
				continue
			var slot: Dictionary = raw_slot
			var anchor_ref := str(slot.get("anchor_ref", ""))
			var canonical_bone := str(slot.get("canonical_bone", ""))
			if anchor_ref.is_empty() or canonical_bone.is_empty():
				continue
			normalized_slots[slot_id] = {
				"slot_id": slot_id,
				"anchor_ref": anchor_ref,
				"canonical_bone": canonical_bone,
				"attachment_mode": "held_item" if bool(slot.get("held_item", false)) else "socket",
			}
	return {
		"slots": normalized_slots,
		"slot_anchor_paths": candidate.get("slot_anchor_paths", {}),
		"offset_defaults": candidate.get("offset_defaults", {}),
		"visibility_rules": candidate.get("visibility_rules", {}),
	}


func resolve_slot(slot_id: StringName) -> Dictionary:
	var slot: Variant = _slots.get(slot_id, {})
	return slot.duplicate(true) if slot is Dictionary else {}
