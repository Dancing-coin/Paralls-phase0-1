extends Node

class_name CarryPlaceMirrorConsumer

const FORBIDDEN_SAFE_PROJECTION_FIELDS: Array[String] = [
	"world_truth_claim",
	"final_world_state",
	"participant_private_terms",
	"character_actor_status",
	"bone_transforms",
	"rigid_body_velocity",
]

var asset_ref := ""
var carried_by_ref := ""
var drop_target_ref := ""
var custody_holder_ref := ""
var owner_ref := ""
var authority_transaction_id := ""
var last_global_sequence := 0
var accepted_event_count := 0
var rejected_event_count := 0
var local_carry_hint_ref := ""
var event_trace: Array[Dictionary] = []


func apply_local_carry_hint(payload: Dictionary) -> Dictionary:
	local_carry_hint_ref = str(payload.get("intended_drop_target_ref", ""))
	return {
		"accepted": true,
		"authority_mutation": false,
		"reason": "presentation_hint_only",
	}


func consume_authority_event(payload: Dictionary) -> Dictionary:
	for field_name: String in FORBIDDEN_SAFE_PROJECTION_FIELDS:
		if payload.has(field_name):
			rejected_event_count += 1
			return {"accepted": false, "error_code": "forbidden_projection_field", "field": field_name}

	var event_type := str(payload.get("event_type", ""))
	if event_type != "embodied.place.settled":
		rejected_event_count += 1
		return {"accepted": false, "error_code": "unsupported_event_type"}

	var sequence := int(payload.get("global_sequence", 0))
	if sequence <= last_global_sequence:
		rejected_event_count += 1
		return {"accepted": false, "error_code": "global_sequence_not_monotonic"}

	var directive_variant: Variant = payload.get("placement_directive", {})
	if typeof(directive_variant) != TYPE_DICTIONARY:
		rejected_event_count += 1
		return {"accepted": false, "error_code": "placement_directive_required"}
	var directive: Dictionary = directive_variant
	if not bool(directive.get("authority_only", false)):
		rejected_event_count += 1
		return {"accepted": false, "error_code": "authority_only_directive_required"}

	asset_ref = str(payload.get("asset_ref", ""))
	carried_by_ref = str(payload.get("actor_ref", ""))
	drop_target_ref = str(payload.get("drop_target_ref", directive.get("place_at_ref", "")))
	custody_holder_ref = str(payload.get("custody_holder_ref", custody_holder_ref))
	owner_ref = str(payload.get("owner_ref", owner_ref))
	authority_transaction_id = str(payload.get("transaction_id", ""))
	last_global_sequence = sequence
	accepted_event_count += 1
	event_trace.append({
		"event_type": event_type,
		"asset_ref": asset_ref,
		"carried_by_ref": carried_by_ref,
		"drop_target_ref": drop_target_ref,
		"custody_holder_ref": custody_holder_ref,
		"owner_ref": owner_ref,
		"global_sequence": sequence,
	})
	return {
		"accepted": true,
		"asset_ref": asset_ref,
		"carried_by_ref": carried_by_ref,
		"drop_target_ref": drop_target_ref,
		"custody_holder_ref": custody_holder_ref,
		"owner_ref": owner_ref,
		"authority_mutation": false,
	}
