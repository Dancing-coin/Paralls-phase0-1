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
var pending_predictions: Dictionary = {}
var prediction_resolution_trace: Array[Dictionary] = []


func consume_delivery(payload: Dictionary) -> Dictionary:
	# 单 actor 离线 probe 入口；真实混流由 GameplayMirrorBridge 统一验证连接序列。
	var next_epoch := int(payload.get("connection_epoch", 0))
	var sequence := int(payload.get("delivery_sequence", 0))
	if next_epoch < connection_epoch or next_epoch < 1:
		return _delivery_rejected("mirror_sequence_stale")
	var previous_sequence := last_delivery_sequence if next_epoch == connection_epoch else 0
	if sequence <= previous_sequence:
		return _delivery_rejected("mirror_sequence_duplicate")
	if sequence != previous_sequence + 1 and not resync_required:
		resync_required = true
		return _delivery_rejected("mirror_sequence_gap")
	var result := consume_validated_delivery(payload)
	if bool(result.get("accepted", false)):
		connection_epoch = next_epoch
		last_delivery_sequence = sequence
	return result


func consume_validated_delivery(payload: Dictionary) -> Dictionary:
	# 仅由已验证连接序列的桥调用；这里只验证逐 actor 内容，不推断全连接 +1。
	var delivery_kind := str(payload.get("delivery_kind", ""))
	if delivery_kind not in ["snapshot", "delta", "prediction"]:
		return _delivery_rejected("mirror_sequence_invalid")
	if resync_required and delivery_kind != "snapshot":
		return _delivery_rejected("mirror_resync_required")
	if delivery_kind == "prediction":
		if str(payload.get("actor_ref", "")) != actor_ref or str(payload.get("facade_revision", "")) != facade_revision:
			return _delivery_rejected("actor_ref_mismatch")
		return _apply_prediction_resolutions(payload.get("prediction_resolutions", []), facade_revision)
	var projection: Variant = payload.get("payload", {})
	if typeof(projection) != TYPE_DICTIONARY:
		resync_required = true
		return _delivery_rejected("projection_payload_invalid")
	if str(payload.get("actor_ref", "")) != str(projection.get("actor_ref", "")) or str(payload.get("facade_revision", "")) != str(projection.get("facade_revision", "")) or str(payload.get("projection_schema", "")) != str(projection.get("projection_kind", "")):
		resync_required = true
		return _delivery_rejected("projection_payload_invalid")
	if payload.get("source_revision_vector", {}) != projection.get("source_revision_vector", {}):
		return _delivery_rejected("projection_payload_invalid")
	var prediction_check := _apply_prediction_resolutions(payload.get("prediction_resolutions", []), str(projection.get("facade_revision", "")), false)
	if not bool(prediction_check.get("accepted", false)):
		return prediction_check
	var result := _apply_delta_delivery(payload, projection as Dictionary) if delivery_kind == "delta" else consume_projection(projection as Dictionary)
	if not bool(result.get("accepted", false)):
		resync_required = true
		return result
	_apply_prediction_resolutions(payload.get("prediction_resolutions", []), facade_revision)
	return result


func consume_projection(payload: Dictionary) -> Dictionary:
	if not _valid_json_value(payload):
		return _delivery_rejected("projection_payload_invalid")
	var forbidden_field := _find_forbidden_field(payload)
	if not forbidden_field.is_empty():
		return _delivery_rejected("forbidden_projection_field")
	if str(payload.get("projection_kind", "")) != "gameplay_runtime_state.godot.v1":
		return _delivery_rejected("unsupported_projection_kind")
	var next_actor_ref := str(payload.get("actor_ref", ""))
	if not actor_ref.is_empty() and next_actor_ref != actor_ref:
		return _delivery_rejected("actor_ref_mismatch")
	var verified := _verified_snapshot(payload)
	if verified.is_empty():
		return _delivery_rejected("snapshot_checksum_invalid")
	var next_revision := str(verified["facade_revision"])
	var next_checksum := str(payload["snapshot_checksum"])
	if next_revision == facade_revision:
		if next_checksum != snapshot_checksum:
			return _delivery_rejected("snapshot_checksum_invalid")
		resync_required = false
		return {"accepted": true, "replayed": true, "authority_mutation": false, "actor_ref": actor_ref, "facade_revision": facade_revision}
	actor_ref = next_actor_ref
	facade_revision = next_revision
	visible_groups = (verified["groups"] as Dictionary).duplicate(true)
	snapshot_checksum = next_checksum
	schema_capabilities.assign(verified["schema_capabilities"])
	resync_required = false
	accepted_projection_count += 1
	return {"accepted": true, "authority_mutation": false, "actor_ref": actor_ref, "facade_revision": facade_revision}


func _verified_snapshot(payload: Dictionary) -> Dictionary:
	var canonical: Variant = payload.get("canonical_snapshot_json")
	if typeof(canonical) != TYPE_STRING or (canonical as String).is_empty():
		return {}
	if "sha256:" + (canonical as String).sha256_text() != str(payload.get("snapshot_checksum", "")):
		return {}
	var parser := JSON.new()
	if parser.parse(canonical) != OK or typeof(parser.data) != TYPE_DICTIONARY:
		return {}
	var verified: Dictionary = parser.data
	var candidate := {}
	for key: String in ["actor_ref", "facade_revision", "source_revision_vector", "schema_capabilities", "enabled_state_groups", "groups"]:
		if not payload.has(key):
			return {}
		candidate[key] = payload[key]
	if not _valid_json_value(candidate) or not _valid_json_value(verified) or not verified.recursive_equal(candidate, 0):
		return {}
	if not _find_forbidden_field(verified).is_empty():
		return {}
	if typeof(verified["actor_ref"]) != TYPE_STRING or str(verified["actor_ref"]).is_empty() or typeof(verified["facade_revision"]) != TYPE_STRING or str(verified["facade_revision"]).is_empty():
		return {}
	if verified["schema_capabilities"] != ["gameplay_runtime_state.godot.v1"] or not _valid_revision_vector(verified["source_revision_vector"]):
		return {}
	if typeof(verified["groups"]) != TYPE_DICTIONARY or typeof(verified["enabled_state_groups"]) != TYPE_ARRAY:
		return {}
	var groups: Dictionary = verified["groups"]
	var enabled: Array = verified["enabled_state_groups"]
	if groups.size() != enabled.size():
		return {}
	var seen := {}
	for group_id: Variant in enabled:
		if typeof(group_id) != TYPE_STRING or str(group_id).is_empty() or seen.has(group_id) or not groups.has(group_id):
			return {}
		seen[group_id] = true
		var envelope: Variant = groups[group_id]
		if typeof(envelope) != TYPE_DICTIONARY or envelope.size() != 5 or not envelope.has_all(["definition_version", "projection_schema_version", "projection_revision", "source_revision_vector", "payload"]):
			return {}
		if typeof(envelope["definition_version"]) != TYPE_STRING or str(envelope["definition_version"]).is_empty() or typeof(envelope["projection_revision"]) != TYPE_STRING or str(envelope["projection_revision"]).is_empty():
			return {}
		if not _nonnegative_integer(envelope["projection_schema_version"]) or int(envelope["projection_schema_version"]) < 1 or not _valid_revision_vector(envelope["source_revision_vector"]) or typeof(envelope["payload"]) != TYPE_DICTIONARY:
			return {}
		if group_id == "population_public" and not _valid_population_public(str(verified["actor_ref"]), envelope["payload"]):
			return {}
	return verified


func _valid_population_public(expected_actor_ref: String, public: Dictionary) -> bool:
	# 在替换任何base/显示之前校验本公开group的固定合同。
	if public.size() != 5 or not public.has_all(["actor_id", "confirmed_tick", "presentation_position", "animation_tag", "public_digest"]):
		return false
	if typeof(public["actor_id"]) != TYPE_STRING or public["actor_id"].is_empty() or expected_actor_ref != "character:" + public["actor_id"]:
		return false
	if not _nonnegative_integer(public["confirmed_tick"]) or public["animation_tag"] not in ["idle", "rest", "work"]:
		return false
	var point: Variant = public["presentation_position"]
	if typeof(point) != TYPE_ARRAY or point.size() != 3:
		return false
	for value: Variant in point:
		if not (value is int or value is float) or not is_finite(float(value)):
			return false
	var digest: Variant = public["public_digest"]
	if typeof(digest) != TYPE_STRING or not digest.begins_with("sha256:") or digest.length() != 71:
		return false
	for digit: String in digest.substr(7):
		if not "0123456789abcdef".contains(digit):
			return false
	return true


func _nonnegative_integer(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(float(value)) and float(value) >= 0 and float(value) == floor(float(value))


func _valid_revision_vector(value: Variant) -> bool:
	if typeof(value) != TYPE_DICTIONARY:
		return false
	for key: Variant in value:
		if typeof(key) != TYPE_STRING or str(key).is_empty() or not _nonnegative_integer(value[key]):
			return false
	return true


func _valid_json_value(value: Variant, depth: int = 0) -> bool:
	if depth > 32:
		return false
	if value is float:
		return is_finite(value)
	if value is Dictionary:
		for key: Variant in value:
			if typeof(key) != TYPE_STRING or not _valid_json_value(value[key], depth + 1):
				return false
	elif value is Array:
		for item: Variant in value:
			if not _valid_json_value(item, depth + 1):
				return false
	elif typeof(value) not in [TYPE_NIL, TYPE_BOOL, TYPE_INT, TYPE_STRING]:
		return false
	return true


func clear_projection() -> void:
	actor_ref = ""
	facade_revision = ""
	visible_groups.clear()
	connection_epoch = 0
	last_delivery_sequence = 0
	resync_required = false
	snapshot_checksum = ""
	schema_capabilities.clear()
	pending_predictions.clear()
	prediction_resolution_trace.clear()


func begin_stamina_prediction(prediction_id: String, command_id: String, delta: int) -> Dictionary:
	if actor_ref.is_empty() or facade_revision.is_empty():
		return {"accepted": false, "error_code": "prediction_base_required", "authority_mutation": false}
	if prediction_id.is_empty() or command_id.is_empty() or delta == 0:
		return {"accepted": false, "error_code": "prediction_payload_invalid", "authority_mutation": false}
	if pending_predictions.has(prediction_id):
		return {"accepted": false, "error_code": "prediction_duplicate", "authority_mutation": false}
	pending_predictions[prediction_id] = {
		"prediction_id": prediction_id,
		"command_id": command_id,
		"resource_id": "core.stamina",
		"delta": delta,
		"base_facade_revision": facade_revision,
	}
	return {"accepted": true, "authority_mutation": false, "prediction_id": prediction_id}


func get_predicted_resource_current(resource_id: String) -> Variant:
	var entries: Dictionary = visible_groups.get("core.resources", {}).get("payload", {}).get("entries", {})
	var resource: Variant = entries.get(resource_id, {})
	if typeof(resource) != TYPE_DICTIONARY or not (resource as Dictionary).has("current"):
		return null
	var current: Variant = (resource as Dictionary).get("current")
	if not (current is int or current is float):
		return null
	var predicted := float(current)
	for prediction: Variant in pending_predictions.values():
		if prediction is Dictionary and str((prediction as Dictionary).get("resource_id", "")) == resource_id:
			predicted += float((prediction as Dictionary).get("delta", 0))
	return predicted


func _apply_prediction_resolutions(resolutions: Variant, confirmed_projection_revision: String, apply: bool = true) -> Dictionary:
	if typeof(resolutions) != TYPE_ARRAY:
		return _delivery_rejected("prediction_resolution_invalid")
	var traces: Array[Dictionary] = []
	var seen := {}
	for resolution_value: Variant in resolutions as Array:
		if typeof(resolution_value) != TYPE_DICTIONARY:
			return _delivery_rejected("prediction_resolution_invalid")
		var resolution := resolution_value as Dictionary
		var prediction_id := str(resolution.get("prediction_id", ""))
		var command_id := str(resolution.get("command_id", ""))
		var status := str(resolution.get("resolution", ""))
		if prediction_id.is_empty() or command_id.is_empty() or not pending_predictions.has(prediction_id):
			return _delivery_rejected("prediction_resolution_unknown")
		if seen.has(prediction_id):
			return _delivery_rejected("prediction_resolution_invalid")
		seen[prediction_id] = true
		var pending: Dictionary = pending_predictions[prediction_id]
		if str(pending.get("command_id", "")) != command_id:
			return _delivery_rejected("prediction_resolution_mismatch")
		if status == "confirmed":
			if str(resolution.get("transaction_id", "")).is_empty() or (
				confirmed_projection_revision == str(pending.get("base_facade_revision", ""))
			):
				return _delivery_rejected("prediction_confirmation_projection_required")
		elif status == "rejected":
			if str(resolution.get("error_code", "")).is_empty():
				return _delivery_rejected("prediction_rejection_error_required")
		else:
			return _delivery_rejected("prediction_resolution_invalid")
		traces.append({
			"prediction_id": prediction_id,
			"command_id": command_id,
			"resolution": status,
			"transaction_id": str(resolution.get("transaction_id", "")),
			"error_code": str(resolution.get("error_code", "")),
			"authority_mutation": false,
		})
	if apply:
		for trace: Dictionary in traces:
			pending_predictions.erase(trace["prediction_id"])
			prediction_resolution_trace.append(trace)
	return {"accepted": true, "authority_mutation": false}


func mark_resync_required() -> void:
	resync_required = true


func _apply_delta_delivery(delivery: Dictionary, projection: Dictionary) -> Dictionary:
	if actor_ref.is_empty() or snapshot_checksum.is_empty():
		resync_required = true
		return _delivery_rejected("mirror_delta_base_required")
	if str(projection.get("actor_ref", "")) != actor_ref:
		resync_required = true
		return _delivery_rejected("actor_ref_mismatch")
	# 内外层 base 必须先一致，才允许对照本地 base 构造完整候选。
	for key: String in ["base_facade_revision", "base_snapshot_checksum"]:
		if not projection.has(key) or typeof(projection[key]) != TYPE_STRING or not delivery.has(key) or typeof(delivery[key]) != TYPE_STRING or projection[key] != delivery[key]:
			resync_required = true
			return _delivery_rejected("projection_payload_invalid")
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
		if (changed_groups as Dictionary).has(group_id_value):
			return _delivery_rejected("delta_group_overlap")
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
	if target_revision != str(delivery.get("facade_revision", "")) or target_checksum != str(projection.get("target_snapshot_checksum", "")):
		return _delivery_rejected("snapshot_checksum_invalid")
	var candidate := projection.duplicate(true)
	candidate["groups"] = next_groups
	candidate["snapshot_checksum"] = target_checksum
	return consume_projection(candidate)


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
