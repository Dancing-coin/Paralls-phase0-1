extends Node

class_name GameplayRuntimeStateMirrorConsumer

const FORBIDDEN_FIELDS: Array[String] = [
	"world_truth_claim",
	"authority_command",
	"private_mind_state",
	"bone_transforms",
	"rigid_body_velocity",
]

var actor_ref := ""
var facade_revision := ""
var accepted_projection_count := 0
var rejected_projection_count := 0
var visible_groups: Dictionary = {}


func consume_projection(payload: Dictionary) -> Dictionary:
	var forbidden_field := _find_forbidden_field(payload)
	if not forbidden_field.is_empty():
		rejected_projection_count += 1
		return {"accepted": false, "error_code": "forbidden_projection_field", "field": forbidden_field}
	if str(payload.get("projection_kind", "")) != "gameplay_runtime_state.godot.v1":
		rejected_projection_count += 1
		return {"accepted": false, "error_code": "unsupported_projection_kind"}
	var next_actor_ref := str(payload.get("actor_ref", ""))
	var next_revision := str(payload.get("facade_revision", ""))
	var groups_variant: Variant = payload.get("groups", {})
	if next_actor_ref.is_empty() or next_revision.is_empty() or typeof(groups_variant) != TYPE_DICTIONARY:
		rejected_projection_count += 1
		return {"accepted": false, "error_code": "projection_payload_invalid"}
	if not actor_ref.is_empty() and next_actor_ref != actor_ref:
		rejected_projection_count += 1
		return {"accepted": false, "error_code": "actor_ref_mismatch"}
	if not facade_revision.is_empty() and next_revision == facade_revision:
		rejected_projection_count += 1
		return {"accepted": false, "error_code": "facade_revision_duplicate"}
	actor_ref = next_actor_ref
	facade_revision = next_revision
	visible_groups = (groups_variant as Dictionary).duplicate(true)
	accepted_projection_count += 1
	return {"accepted": true, "authority_mutation": false, "actor_ref": actor_ref, "facade_revision": facade_revision}


func clear_projection() -> void:
	actor_ref = ""
	facade_revision = ""
	visible_groups.clear()


func _find_forbidden_field(value: Variant) -> String:
	if typeof(value) == TYPE_DICTIONARY:
		for key: Variant in (value as Dictionary).keys():
			var field_name := str(key)
			if FORBIDDEN_FIELDS.has(field_name):
				return field_name
			var nested_field := _find_forbidden_field((value as Dictionary)[key])
			if not nested_field.is_empty():
				return nested_field
	elif typeof(value) == TYPE_ARRAY:
		for item: Variant in value as Array:
			var nested_field := _find_forbidden_field(item)
			if not nested_field.is_empty():
				return nested_field
	return ""
