extends RefCounted

class_name CharacterWeaponActionProfile


const SEMANTIC_KINDS := [&"melee", &"hitscan"]
const FORBIDDEN_TRUTH_FIELDS := [&"damage", &"hit", &"ammo", &"projectile", &"transform", &"global_position", &"velocity", &"inventory", &"status"]


static func normalize(raw: Dictionary) -> Dictionary:
	for field in FORBIDDEN_TRUTH_FIELDS:
		if raw.has(String(field)):
			return {"accepted": false, "reason": StringName("world_truth_field_forbidden:%s" % field)}
	var semantic_kind := StringName(str(raw.get("semantic_kind", "")))
	if semantic_kind not in SEMANTIC_KINDS:
		return {"accepted": false, "reason": &"semantic_kind_invalid"}
	var semantic_action_id := StringName(str(raw.get("semantic_action_id", "")))
	if String(semantic_action_id).is_empty():
		return {"accepted": false, "reason": &"semantic_action_id_missing"}
	var required_slots: Variant = raw.get("required_slots", [])
	var resource_claims: Variant = raw.get("resource_claims", [])
	var physics_claims: Variant = raw.get("physics_claims", [])
	if not (required_slots is Array) or not (resource_claims is Array) or not (physics_claims is Array):
		return {"accepted": false, "reason": &"weapon_profile_fields_invalid"}
	return {
		"accepted": true,
		"semantic_kind": semantic_kind,
		"semantic_action_id": semantic_action_id,
		"required_slots": required_slots.duplicate(),
		"resource_claims": resource_claims.duplicate(),
		"physics_claims": physics_claims.duplicate(),
		"authority_route_ref": str(raw.get("authority_route_ref", "")),
		"presentation_only": bool(raw.get("presentation_only", false)),
	}
