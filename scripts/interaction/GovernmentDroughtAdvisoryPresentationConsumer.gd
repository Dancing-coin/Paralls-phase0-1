extends Node

class_name GovernmentDroughtAdvisoryPresentationConsumer

## Read-only presentation cache for one server-granted project jurisdiction.

var jurisdiction_ref := ""
var advisory_refs: Array[String] = []
var source_revision_vector: Dictionary = {}
var projection_hash := ""
var connection_epoch := 0
var last_delivery_sequence := 0
var accepted_projection_count := 0
var rejected_projection_count := 0


func consume_projection(payload: Dictionary) -> Dictionary:
	if str(payload.get("projection_kind", "")) != "government_drought_advisory.project.v1":
		return _rejected("unsupported_projection_kind")
	var next_jurisdiction_ref := str(payload.get("jurisdiction_ref", ""))
	var next_hash := str(payload.get("projection_hash", ""))
	var refs_value: Variant = payload.get("advisory_refs", [])
	var vector_value: Variant = payload.get("source_revision_vector", {})
	if next_jurisdiction_ref.is_empty() or next_hash.is_empty() or typeof(refs_value) != TYPE_ARRAY or typeof(vector_value) != TYPE_DICTIONARY:
		return _rejected("projection_payload_invalid")
	if not jurisdiction_ref.is_empty() and next_jurisdiction_ref != jurisdiction_ref:
		return _rejected("jurisdiction_ref_mismatch")
	var next_refs: Array[String] = []
	for value: Variant in refs_value as Array:
		var advisory_ref := str(value)
		if advisory_ref.is_empty():
			return _rejected("projection_payload_invalid")
		next_refs.append(advisory_ref)
	if next_refs.is_empty():
		return _rejected("projection_payload_invalid")
	var next_vector := (vector_value as Dictionary).duplicate(true)
	for key: Variant in next_vector.keys():
		if str(key).is_empty() or int(next_vector[key]) < 1:
			return _rejected("projection_payload_invalid")
	jurisdiction_ref = next_jurisdiction_ref
	advisory_refs = next_refs
	source_revision_vector = next_vector
	projection_hash = next_hash
	accepted_projection_count += 1
	return {"accepted": true, "authority_mutation": false, "jurisdiction_ref": jurisdiction_ref}


func consume_delivery(payload: Dictionary) -> Dictionary:
	var next_epoch := int(payload.get("connection_epoch", 0))
	var next_sequence := int(payload.get("delivery_sequence", 0))
	if next_epoch < 1 or next_epoch < connection_epoch:
		return _rejected("mirror_sequence_stale")
	if next_epoch > connection_epoch:
		connection_epoch = next_epoch
		last_delivery_sequence = 0
	if next_sequence != last_delivery_sequence + 1:
		return _rejected("mirror_sequence_invalid")
	var result := consume_projection(payload)
	if not bool(result.get("accepted", false)):
		return result
	last_delivery_sequence = next_sequence
	return result


func clear_projection() -> void:
	jurisdiction_ref = ""
	advisory_refs.clear()
	source_revision_vector.clear()
	projection_hash = ""
	connection_epoch = 0
	last_delivery_sequence = 0


func _rejected(error_code: String) -> Dictionary:
	rejected_projection_count += 1
	return {"accepted": false, "authority_mutation": false, "error_code": error_code}
