extends Node
class_name CharacterMotor

const CharacterActorSchemaRef = preload("res://scripts/character/CharacterActorSchema.gd")
const CharacterControllerPortRef = preload("res://scripts/character/CharacterControllerPort.gd")
const ContinuousControlLeaseRef = preload("res://scripts/character/ContinuousControlLease.gd")
const ActorActionArbiterRef = preload("res://scripts/character/ActorActionArbiter.gd")
const MotionContributionComposerRef = preload("res://scripts/character/MotionContributionComposer.gd")
const PhysicsContactEvidenceRef = preload("res://scripts/character/PhysicsContactEvidence.gd")

func apply_intent_frame(body: CharacterBody3D, frame: Dictionary, delta: float) -> Dictionary:
	var normalized := CharacterControllerPortRef.normalize_intent_frame(frame)
	var lease := ContinuousControlLeaseRef.create(StringName(normalized.get("controller_source", "program")), &"lease:compat", 0, Engine.get_physics_frames() + 1, CharacterControllerPortRef.get_move_local(normalized), CharacterControllerPortRef.get_desired_facing_yaw(normalized, body.rotation.y))
	var intent_frame := ActorActionArbiterRef.resolve(Engine.get_physics_frames(), [lease], [], {"occupancy": {}})
	var speed := _get_body_float(body, "run_speed", 4.0) if CharacterControllerPortRef.get_gait_name(normalized) == "run" else _get_body_float(body, "walk_speed", 4.0)
	return apply_physics_command(body, MotionContributionComposerRef.compose(intent_frame, {"actor_ref": normalized.get("actor_id", ""), "speed": speed}, delta), delta)

func apply_physics_command(body: CharacterBody3D, command: Dictionary, delta: float) -> Dictionary:
	body.rotation.y = rotate_toward(body.rotation.y, float(command.get("facing_yaw", body.rotation.y)), _get_body_float(body, "facing_turn_speed", 8.0) * delta)
	var desired: Vector3 = command.get("desired_velocity", Vector3.ZERO)
	var planar: Vector3 = desired + command.get("root_delta", Vector3.ZERO) / max(delta, 0.0001) + command.get("impulse", Vector3.ZERO) + command.get("runtime_correction", Vector3.ZERO)
	body.velocity.x = move_toward(body.velocity.x, planar.x, _get_body_float(body, "acceleration", 18.0) * delta)
	body.velocity.z = move_toward(body.velocity.z, planar.z, _get_body_float(body, "acceleration", 18.0) * delta)
	if not body.is_on_floor(): body.velocity.y -= _get_body_float(body, "fall_gravity", 9.8) * delta
	elif body.velocity.y < 0.0: body.velocity.y = 0.0
	body.move_and_slide()
	return CharacterActorSchemaRef.normalize_motion_state({"position": body.global_position, "velocity_world": body.velocity, "facing_yaw": body.rotation.y, "move_local_actual": Vector2(desired.x, desired.z), "gait_actual": "run" if desired.length() > _get_body_float(body, "walk_speed", 4.0) else "walk", "grounded": body.is_on_floor(), "physics_command": command})

func _get_body_float(body: CharacterBody3D, property_name: String, fallback: float) -> float:
	if body and body.has_method("get_numeric_setting"): return float(body.get_numeric_setting(StringName(property_name), fallback))
	return fallback

func apply_facing(body: CharacterBody3D, desired_yaw: float, delta: float) -> void:
	body.rotation.y = rotate_toward(body.rotation.y, desired_yaw, _get_body_float(body, "facing_turn_speed", 8.0) * delta)

func collect_contact_evidence(body: CharacterBody3D, command: Dictionary, action_instances: Array[Dictionary]) -> Array[Dictionary]:
	var evidence: Array[Dictionary] = []
	for index in body.get_slide_collision_count():
		var collision := body.get_slide_collision(index)
		for action in action_instances:
			evidence.append(PhysicsContactEvidenceRef.create(command, body, action, collision))
	return evidence
