extends RefCounted

class_name IntentProposal

const CharacterTagContractRef = preload("res://scripts/character/CharacterTagContract.gd")
const FORBIDDEN_WORLD_FIELDS := ["damage", "hit_result", "inventory_mutation", "status_write", "transform", "velocity"]


static func normalize(raw: Dictionary, source_id: StringName, control_mode: StringName) -> Dictionary:
	for field in FORBIDDEN_WORLD_FIELDS:
		if raw.has(field):
			return {"accepted": false, "reason": "world_write_forbidden:%s" % field}
	var raw_tags: Array[StringName] = []
	for value in raw.get("intent_tags", []) + raw.get("context_tags", []):
		raw_tags.append(StringName(value))
	var tag_result := CharacterTagContractRef.normalize_ingress_tags(
		raw_tags,
		bool(raw.get("authority_committed", false)),
		StringName(raw.get("authority_route", "")),
	)
	if not tag_result["rejected"].is_empty():
		return {"accepted": false, "reason": "tag_rejected", "rejected_tags": tag_result["rejected"]}
	var move: Variant = raw.get("move_local", Vector2.ZERO)
	var facing := float(raw.get("desired_facing_yaw", 0.0))
	return {
		"accepted": true,
		"source_id": source_id,
		"control_mode": control_mode,
		"intent_tags": tag_result["accepted"],
		"context_tags": [],
		"move_local": move if move is Vector2 else Vector2.ZERO,
		"desired_facing_yaw": facing,
		"action_id": StringName(raw.get("action_id", "")),
		"target_ref": StringName(raw.get("target_ref", "")),
		"priority": int(raw.get("priority", 0)),
		"causation_id": StringName(raw.get("causation_id", "")),
		"correlation_id": StringName(raw.get("correlation_id", "")),
		"metadata": raw.get("metadata", {}).duplicate(true),
	}
