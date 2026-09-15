extends RefCounted
class_name PhysicsContactEvidence
static func create(command: Dictionary, body: CharacterBody3D, action_instance: Dictionary, collision: KinematicCollision3D = null) -> Dictionary:
	if collision == null:
		return {}
	var collider_ref := ""
	var point := Vector3.ZERO
	var normal := Vector3.UP
	if collision != null:
		collider_ref = str(collision.get_collider_id())
		point = collision.get_position()
		normal = collision.get_normal()
	var command_digest := str(command.get("source_digest", command.get("command_digest", "")))
	if command_digest.is_empty():
		command_digest = "command:%s" % command.get("physics_tick", -1)
	var body_revision := int(command.get("body_revision", -1))
	var digest := "%s:%s:%s:%s:%s" % [command.get("physics_tick", -1), body_revision, collider_ref, action_instance.get("action_instance_id", ""), command_digest]
	var marker_observed := bool(action_instance.get("marker_observed", false))
	var marker_id := str(action_instance.get("marker_id", "")) if marker_observed else ""
	return {"evidence_id": "contact:%s" % digest, "actor_ref": command.get("actor_ref", ""), "physics_tick": command.get("physics_tick", -1), "body_revision": body_revision, "marker_id": marker_id, "contact_marker_id": marker_id, "marker_observed": marker_observed, "contact_confirmation": false, "action_instance_id": action_instance.get("action_instance_id", ""), "grounded": body.is_on_floor(), "support_ref": collider_ref if body.is_on_floor() else "", "collider_refs": [collider_ref] if not collider_ref.is_empty() else [], "hit_sensor_refs": _bounded_string_refs(action_instance.get("hit_sensor_refs", []), 16), "contact_points": [point], "contact_normals": [normal], "collider_ref": collider_ref, "contact_point": point, "contact_normal": normal, "motion_command_digest": command_digest, "command_digest": command_digest, "evidence_digest": digest, "local_only": true}


static func _bounded_string_refs(value: Variant, limit: int) -> Array[String]:
	var refs: Array[String] = []
	if not (value is Array):
		return refs
	for item: Variant in value:
		var ref := str(item)
		if ref.is_empty() or refs.has(ref):
			continue
		refs.append(ref)
		if refs.size() >= limit:
			break
	return refs


static func join_same_tick(evidence: Array[Dictionary], marker_observations: Array[Dictionary], physics_tick: int) -> Array[Dictionary]:
	var evidence_by_action: Dictionary = {}
	for record: Dictionary in evidence:
		if int(record.get("physics_tick", -1)) != physics_tick:
			continue
		var action_id := str(record.get("action_instance_id", ""))
		if not action_id.is_empty() and not evidence_by_action.has(action_id):
			evidence_by_action[action_id] = record
	var joined: Array[Dictionary] = []
	for marker: Dictionary in marker_observations:
		var marker_tick := int(marker.get("physics_tick", marker.get("marker_physics_tick", -1)))
		if marker_tick != physics_tick:
			continue
		var attempt_id := str(marker.get("action_instance_id", ""))
		if attempt_id.is_empty():
			continue
		var physical: Dictionary = evidence_by_action.get(attempt_id, {})
		joined.append({
			"attempt_id": attempt_id,
			"marker_id": str(marker.get("marker_id", "")),
			"physics_tick": physics_tick,
			"evidence_id": str(physical.get("evidence_id", "")),
			"evidence_status": "supported" if not physical.is_empty() else "uncertain",
			"contact_confirmation": false,
			"local_only": true,
		})
	return joined
