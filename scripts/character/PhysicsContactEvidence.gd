extends RefCounted
class_name PhysicsContactEvidence
static func create(command: Dictionary, body: CharacterBody3D, action_instance: Dictionary, collision: KinematicCollision3D = null) -> Dictionary:
	var collider_ref := ""
	var point := Vector3.ZERO
	var normal := Vector3.UP
	if collision != null:
		collider_ref = str(collision.get_collider_id())
		point = collision.get_position()
		normal = collision.get_normal()
	var digest := "%s:%s:%s:%s" % [command.get("physics_tick", -1), body.get_instance_id(), collider_ref, action_instance.get("action_instance_id", "")]
	return {"evidence_id": "contact:%s" % digest, "physics_tick": command.get("physics_tick", -1), "body_revision": body.get_instance_id(), "grounded": body.is_on_floor(), "support_ref": collider_ref if body.is_on_floor() else "", "collider_ref": collider_ref, "contact_point": point, "contact_normal": normal, "motion_command_digest": digest, "action_instance_id": action_instance.get("action_instance_id", ""), "marker_id": action_instance.get("marker_id", ""), "local_only": true}
