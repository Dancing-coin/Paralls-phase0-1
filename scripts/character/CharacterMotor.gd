extends Node
class_name CharacterMotor

const CharacterActorSchemaRef = preload("res://scripts/character/CharacterActorSchema.gd")
const CharacterControllerPortRef = preload("res://scripts/character/CharacterControllerPort.gd")
const ContinuousControlLeaseRef = preload("res://scripts/character/ContinuousControlLease.gd")
const ActorActionArbiterRef = preload("res://scripts/character/ActorActionArbiter.gd")
const MotionContributionComposerRef = preload("res://scripts/character/MotionContributionComposer.gd")
const PhysicsContactEvidenceRef = preload("res://scripts/character/PhysicsContactEvidence.gd")

var body_revision := 0
var last_physics_tick := -1
var last_command_digest := ""

func apply_intent_frame(body: CharacterBody3D, frame: Dictionary, delta: float) -> Dictionary:
	var normalized_frame := CharacterControllerPortRef.normalize_intent_frame(frame)
	var proposal := CharacterControllerPortRef.submit_intent_proposal(normalized_frame, StringName(normalized_frame.get("controller_source", "program")), StringName(normalized_frame.get("control_mode", "program_controlled")))
	var move_local := CharacterControllerPortRef.get_move_local(normalized_frame)
	var world_move := body.global_basis.x * move_local.x - body.global_basis.z * move_local.y
	var lease := ContinuousControlLeaseRef.create(StringName(normalized_frame.get("controller_source", "program")), &"lease:compat", 0, Engine.get_physics_frames() + 1, Vector2(world_move.x, world_move.z), CharacterControllerPortRef.get_desired_facing_yaw(normalized_frame, body.rotation.y))
	var leases: Array[Dictionary] = []
	if bool(proposal.get("accepted", false)):
		lease["priority"] = int(proposal.get("proposal", {}).get("priority", 0))
		leases.append(lease)
	var actions: Array[Dictionary] = []
	var intent_frame := ActorActionArbiterRef.resolve(Engine.get_physics_frames(), leases, actions, {"occupancy": {}})
	var action_name := CharacterControllerPortRef.get_action_name(normalized_frame)
	var speed := _get_body_float(body, "run_speed", 4.0) if CharacterControllerPortRef.get_gait_name(normalized_frame) == "run" else _get_body_float(body, "walk_speed", 4.0)
	return apply_physics_command(body, MotionContributionComposerRef.compose(intent_frame, {"actor_ref": normalized_frame.get("actor_id", ""), "speed": speed, "action_name": action_name}, delta), delta)

func apply_physics_command(body: CharacterBody3D, command: Dictionary, delta: float) -> Dictionary:
	if body == null:
		return {}
	last_physics_tick = int(command.get("physics_tick", Engine.get_physics_frames()))
	last_command_digest = str(command.get("source_digest", ""))
	body.rotation.y = rotate_toward(body.rotation.y, float(command.get("facing_yaw", body.rotation.y)), _get_body_float(body, "facing_turn_speed", 8.0) * delta)
	var desired: Vector3 = command.get("desired_velocity", Vector3.ZERO)
	var planar: Vector3 = desired + (command.get("root_delta", Vector3.ZERO) as Vector3) / max(delta, 0.0001) + command.get("impulse", Vector3.ZERO) + command.get("runtime_correction", Vector3.ZERO)
	body.velocity.x = move_toward(body.velocity.x, planar.x, _get_body_float(body, "acceleration", 18.0) * delta)
	body.velocity.z = move_toward(body.velocity.z, planar.z, _get_body_float(body, "acceleration", 18.0) * delta)
	if not body.is_on_floor(): body.velocity.y -= _get_body_float(body, "fall_gravity", 9.8) * delta
	elif body.velocity.y < 0.0: body.velocity.y = 0.0
	body.move_and_slide()
	body_revision += 1
	command["body_revision"] = body_revision
	var collision_normals: Array[Vector3] = []
	for collision_index in body.get_slide_collision_count():
		collision_normals.append(body.get_slide_collision(collision_index).get_normal())
	var support_required: bool = not command.get("support_requirements", []).is_empty()
	return CharacterActorSchemaRef.normalize_motion_state({"position": body.global_position, "velocity_world": body.velocity, "facing_yaw": body.rotation.y, "move_local_actual": Vector2(desired.x, desired.z), "gait_actual": "run" if desired.length() > _get_body_float(body, "walk_speed", 4.0) else "walk", "grounded": body.is_on_floor(), "support_ref": "floor" if body.is_on_floor() else "", "support_loss": support_required and not body.is_on_floor(), "collision_count": body.get_slide_collision_count(), "collision_normals": collision_normals, "body_revision": body_revision, "physics_tick": last_physics_tick, "physics_command": command})

func _get_body_float(body: CharacterBody3D, property_name: String, fallback: float) -> float:
	if body and body.has_method("get_numeric_setting"): return float(body.get_numeric_setting(StringName(property_name), fallback))
	return fallback

func apply_facing(body: CharacterBody3D, desired_yaw: float, delta: float) -> void:
	body.rotation.y = rotate_toward(body.rotation.y, desired_yaw, _get_body_float(body, "facing_turn_speed", 8.0) * delta)

func collect_contact_evidence(body: CharacterBody3D, command: Dictionary, action_instances: Array[Dictionary]) -> Array[Dictionary]:
	var evidence: Array[Dictionary] = []
	if body == null or body.get_slide_collision_count() <= 0:
		return evidence
	var observed_command := command.duplicate(true)
	observed_command["body_revision"] = body_revision
	if not observed_command.has("physics_tick"):
		observed_command["physics_tick"] = last_physics_tick
	for index in min(body.get_slide_collision_count(), 32):
		var collision := body.get_slide_collision(index)
		for action in action_instances:
			var marker_observed := bool(action.get("marker_observed", false))
			var marker_tick := int(action.get("marker_physics_tick", observed_command.get("physics_tick", -1)))
			if marker_observed and marker_tick != int(observed_command.get("physics_tick", -1)):
				continue
			var record := PhysicsContactEvidenceRef.create(observed_command, body, action, collision)
			if not record.is_empty():
				evidence.append(record)
	return evidence
