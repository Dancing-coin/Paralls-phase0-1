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
var connection_epoch := 0
var last_delivery_sequence := 0
var resync_required := false
var snapshot_checksum := ""
var schema_capabilities: Array[String] = []


func consume_delivery(payload: Dictionary) -> Dictionary:
	var delivery_kind := str(payload.get("delivery_kind", ""))
	var next_epoch := int(payload.get("connection_epoch", 0))
	var sequence := int(payload.get("delivery_sequence", 0))
	if delivery_kind != "snapshot" and delivery_kind != "delta":
		return _delivery_rejected("mirror_sequence_invalid")
	if next_epoch < connection_epoch or next_epoch < 1:
		return _delivery_rejected("mirror_sequence_stale")
	if next_epoch > connection_epoch:
		actor_ref = ""
		facade_revision = ""
		visible_groups.clear()
		connection_epoch = next_epoch
		last_delivery_sequence = 0
		resync_required = false
	if sequence <= last_delivery_sequence:
		return _delivery_rejected("mirror_sequence_duplicate")
	if resync_required:
		return _delivery_rejected("mirror_resync_required")
	if sequence != last_delivery_sequence + 1:
		resync_required = true
		return _delivery_rejected("mirror_sequence_gap")
	var projection: Variant = payload.get("payload", {})
	if typeof(projection) != TYPE_DICTIONARY:
		resync_required = true
		return _delivery_rejected("projection_payload_invalid")
	var result := _apply_delta_delivery(payload, projection as Dictionary) if delivery_kind == "delta" else consume_projection(projection as Dictionary)
	if not bool(result.get("accepted", false)):
		resync_required = true
		return result
	last_delivery_sequence = sequence
	return result


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
	snapshot_checksum = str(payload.get("snapshot_checksum", ""))
	schema_capabilities.clear()
	for capability: Variant in payload.get("schema_capabilities", []):
		var capability_ref := str(capability)
		if not capability_ref.is_empty():
			schema_capabilities.append(capability_ref)
	# A backend snapshot atomically replaces the failed delivery base.
	resync_required = false
	accepted_projection_count += 1
	return {"accepted": true, "authority_mutation": false, "actor_ref": actor_ref, "facade_revision": facade_revision}


func clear_projection() -> void:
	actor_ref = ""
	facade_revision = ""
	visible_groups.clear()
	connection_epoch = 0
	last_delivery_sequence = 0
	resync_required = false
	snapshot_checksum = ""
	schema_capabilities.clear()


func mark_resync_required() -> void:
	resync_required = true


func _apply_delta_delivery(delivery: Dictionary, projection: Dictionary) -> Dictionary:
	if actor_ref.is_empty() or snapshot_checksum.is_empty():
		resync_required = true
		return _delivery_rejected("mirror_delta_base_required")
	if str(projection.get("actor_ref", "")) != actor_ref:
		resync_required = true
		return _delivery_rejected("actor_ref_mismatch")
	if str(delivery.get("base_facade_revision", "")) != facade_revision:
		resync_required = true
		return _delivery_rejected("facade_revision_conflict")
	if str(delivery.get("base_snapshot_checksum", "")) != snapshot_checksum:
		resync_required = true
		return _delivery_rejected("snapshot_checksum_invalid")
	var next_capabilities: Variant = projection.get("schema_capabilities", [])
	if typeof(next_capabilities) != TYPE_ARRAY or not (next_capabilities as Array).has("gameplay_runtime_state.godot.v1"):
		resync_required = true
		return _delivery_rejected("projection_schema_unsupported")
	var changed_groups: Variant = projection.get("groups", {})
	var removed_group_ids: Variant = projection.get("removed_group_ids", [])
	var enabled_group_ids: Variant = projection.get("enabled_state_groups", [])
	if typeof(changed_groups) != TYPE_DICTIONARY or typeof(removed_group_ids) != TYPE_ARRAY or typeof(enabled_group_ids) != TYPE_ARRAY:
		resync_required = true
		return _delivery_rejected("projection_payload_invalid")
	var next_groups := visible_groups.duplicate(true)
	for group_id_value: Variant in removed_group_ids as Array:
		next_groups.erase(str(group_id_value))
	for group_id_value: Variant in (changed_groups as Dictionary).keys():
		next_groups[str(group_id_value)] = (changed_groups as Dictionary)[group_id_value]
	var enabled := {}
	for group_id_value: Variant in enabled_group_ids as Array:
		enabled[str(group_id_value)] = true
	if enabled.size() != next_groups.size():
		resync_required = true
		return _delivery_rejected("delta_enabled_groups_invalid")
	for group_id: Variant in enabled.keys():
		if not next_groups.has(group_id):
			resync_required = true
			return _delivery_rejected("delta_enabled_groups_invalid")
	var target_checksum := str(delivery.get("target_snapshot_checksum", ""))
	var target_revision := str(projection.get("facade_revision", ""))
	if target_checksum.is_empty() or target_revision.is_empty():
		resync_required = true
		return _delivery_rejected("snapshot_checksum_invalid")
	visible_groups = next_groups
	facade_revision = target_revision
	snapshot_checksum = target_checksum
	schema_capabilities.clear()
	for capability: Variant in next_capabilities as Array:
		schema_capabilities.append(str(capability))
	accepted_projection_count += 1
	return {"accepted": true, "authority_mutation": false, "actor_ref": actor_ref, "facade_revision": facade_revision}


func _delivery_rejected(error_code: String) -> Dictionary:
	rejected_projection_count += 1
	return {"accepted": false, "error_code": error_code, "authority_mutation": false}


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
