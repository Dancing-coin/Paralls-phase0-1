extends RefCounted

class_name SceneAffordanceRegistry

var records: Dictionary = {}
var space_model: Dictionary = {}
var occupancy_snapshot: Dictionary = {}
var grounding_catalog: Dictionary = {}
var current_tick := 0
var occupancy_freshness_ticks := 30
var vla_conflicts: Array[Dictionary] = []


func configure(
	p_space_model: Dictionary,
	p_occupancy_snapshot: Dictionary,
	p_grounding_catalog: Dictionary,
	p_current_tick: int,
	p_occupancy_freshness_ticks: int
) -> void:
	space_model = p_space_model
	occupancy_snapshot = p_occupancy_snapshot
	grounding_catalog = p_grounding_catalog
	current_tick = p_current_tick
	occupancy_freshness_ticks = p_occupancy_freshness_ticks


func register_reviewed_record(record: Dictionary) -> Dictionary:
	var identity_status := _validate_catalog_identity(record)
	if identity_status != "ok":
		return {"status": identity_status}
	var key := _record_key(record)
	records[key] = record.duplicate(true)
	return {"status": "registered", "record_key": key}


func resolve(
	scene_id: String,
	scene_instance_id: String,
	entity_ref: String,
	affordance_id: String,
	expected_binding_revision: int,
	required_anchor_roles: Array[String],
	view: String
) -> Dictionary:
	var cross_scene_candidate := false
	for record_key: String in records.keys():
		var candidate: Dictionary = records[record_key]
		if str(candidate.get("entity_ref", "")) == entity_ref:
			cross_scene_candidate = true
			if str(candidate.get("scene_id", "")) == scene_id and str(candidate.get("scene_instance_id", "")) == scene_instance_id:
				var status := _resolve_record(candidate, affordance_id, expected_binding_revision, required_anchor_roles)
				if status != "available":
					return {"status": status, "record": {}, "projection": {}, "explanation_refs": [status]}
				return {
					"status": "available",
					"record": candidate,
					"projection": _project(candidate, view),
					"explanation_refs": ["binding_revision:%s" % str(candidate.get("binding_revision", ""))],
				}
	if cross_scene_candidate:
		return {"status": "registry_cross_scene_binding_rejected", "record": {}, "projection": {}, "explanation_refs": ["scene_instance_id"]}
	return {"status": "registry_target_unknown", "record": {}, "projection": {}, "explanation_refs": ["entity_ref"]}


func review_vla_candidate(entity_ref: String, candidate_refs: Dictionary) -> Dictionary:
	var record := _find_by_entity(entity_ref)
	if record.is_empty():
		return {"status": "vla_unknown_entity", "entity_ref": entity_ref}
	var result := {
		"status": "vla_conflict_recorded",
		"entity_ref": entity_ref,
		"candidate_refs": candidate_refs.duplicate(true),
		"retained_registry_entity_ref": str(record.get("entity_ref", "")),
	}
	vla_conflicts.append(result)
	return result


func _resolve_record(record: Dictionary, affordance_id: String, expected_binding_revision: int, required_anchor_roles: Array[String]) -> String:
	if int(record.get("binding_revision", 0)) != expected_binding_revision:
		return "registry_binding_stale"
	if not _has_affordance(record, affordance_id):
		return "registry_target_unknown"
	if not _has_anchor_roles(record, required_anchor_roles):
		return "registry_target_unknown"
	if _validate_catalog_identity(record) != "ok":
		return "registry_catalog_identity_mismatch"
	if not _space_model_contains_binding(record):
		return "registry_binding_unhealthy"
	if _occupancy_is_stale(record):
		return "registry_occupancy_stale"
	return "available"


func _validate_catalog_identity(record: Dictionary) -> String:
	var entity_ref := str(record.get("entity_ref", ""))
	var catalog_refs: Dictionary = record.get("grounding_catalog_refs", {})
	if entity_ref != str(catalog_refs.get("entity_ref", "")):
		return "registry_catalog_identity_mismatch"
	if _string_array(record.get("local_binding", {}).get("collider_refs", [])) != _string_array(catalog_refs.get("collider_refs", [])):
		return "registry_catalog_identity_mismatch"
	var anchor_ids: Array[String] = []
	for anchor: Dictionary in record.get("anchors", []):
		anchor_ids.append(str(anchor.get("anchor_id", "")))
	if anchor_ids != _string_array(catalog_refs.get("anchor_refs", [])):
		return "registry_catalog_identity_mismatch"
	if not _string_array(grounding_catalog.get("entity_refs", [])).has(entity_ref):
		return "registry_catalog_identity_mismatch"
	for collider_ref: String in _string_array(record.get("local_binding", {}).get("collider_refs", [])):
		if not _string_array(grounding_catalog.get("collider_refs", [])).has(collider_ref):
			return "registry_catalog_identity_mismatch"
	for anchor_ref: String in anchor_ids:
		if not _string_array(grounding_catalog.get("anchor_refs", [])).has(anchor_ref):
			return "registry_catalog_identity_mismatch"
	for affordance: Dictionary in record.get("affordances", []):
		if not _string_array(grounding_catalog.get("affordance_refs", [])).has(str(affordance.get("affordance_id", ""))):
			return "registry_catalog_identity_mismatch"
	return "ok"


func _space_model_contains_binding(record: Dictionary) -> bool:
	var element_ids: Array[String] = []
	var refs: Array[String] = []
	for element: Dictionary in space_model.get("elements", []):
		element_ids.append(str(element.get("element_id", "")))
		for ref: String in _string_array(element.get("source_refs", [])):
			refs.append(ref)
	if not element_ids.has(str(record.get("entity_ref", ""))):
		return false
	for collider_ref: String in _string_array(record.get("local_binding", {}).get("collider_refs", [])):
		if not refs.has(collider_ref):
			return false
	for anchor: Dictionary in record.get("anchors", []):
		if not refs.has(str(anchor.get("anchor_id", ""))):
			return false
	var nav_ref := str(record.get("local_binding", {}).get("navigation_footprint_ref", ""))
	return element_ids.has(nav_ref) or refs.has(nav_ref)


func _occupancy_is_stale(record: Dictionary) -> bool:
	var object_states: Dictionary = occupancy_snapshot.get("object_states", {})
	var object_state: Dictionary = object_states.get(str(record.get("entity_ref", "")), {})
	if object_state.is_empty():
		return true
	return current_tick - int(object_state.get("updated_at", 0)) > occupancy_freshness_ticks


func _has_affordance(record: Dictionary, affordance_id: String) -> bool:
	for affordance: Dictionary in record.get("affordances", []):
		if str(affordance.get("affordance_id", "")) == affordance_id:
			return true
	return false


func _has_anchor_roles(record: Dictionary, required_anchor_roles: Array[String]) -> bool:
	var roles: Array[String] = []
	for anchor: Dictionary in record.get("anchors", []):
		roles.append(str(anchor.get("role", "")))
	for role: String in required_anchor_roles:
		if not roles.has(role):
			return false
	return true


func _project(record: Dictionary, view: String) -> Dictionary:
	var projection := {
		"entity_ref": str(record.get("entity_ref", "")),
		"scene_id": str(record.get("scene_id", "")),
		"scene_instance_id": str(record.get("scene_instance_id", "")),
		"binding_revision": int(record.get("binding_revision", 0)),
		"semantic_type": str(record.get("semantic_type", "")),
		"semantic_tags": _string_array(record.get("semantic_tags", [])),
		"affordance_ids": [],
		"anchor_roles": [],
		"visibility_policy": str(record.get("visibility_policy", "")),
	}
	for affordance: Dictionary in record.get("affordances", []):
		projection["affordance_ids"].append(str(affordance.get("affordance_id", "")))
	for anchor: Dictionary in record.get("anchors", []):
		projection["anchor_roles"].append(str(anchor.get("role", "")))
	if view == "controller":
		projection["local_binding"] = record.get("local_binding", {}).duplicate(true)
		projection["anchors"] = record.get("anchors", []).duplicate(true)
	return projection


func _find_by_entity(entity_ref: String) -> Dictionary:
	for record_key: String in records.keys():
		var record: Dictionary = records[record_key]
		if str(record.get("entity_ref", "")) == entity_ref:
			return record
	return {}


func _record_key(record: Dictionary) -> String:
	return "%s|%s|%s" % [
		str(record.get("scene_id", "")),
		str(record.get("scene_instance_id", "")),
		str(record.get("entity_ref", "")),
	]


func _string_array(value: Variant) -> Array[String]:
	var result: Array[String] = []
	if value is Array:
		for item: Variant in value:
			result.append(str(item))
	return result
