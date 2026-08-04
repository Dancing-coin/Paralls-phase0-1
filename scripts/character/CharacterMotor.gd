extends Node

class_name CharacterMotor

const CharacterActorSchemaRef = preload("res://scripts/character/CharacterActorSchema.gd")
const CharacterControllerPortRef = preload("res://scripts/character/CharacterControllerPort.gd")

func apply_intent_frame(body: CharacterBody3D, frame: Dictionary, delta: float) -> Dictionary:
	var normalized_frame := CharacterControllerPortRef.normalize_intent_frame(frame)
	var move_local := CharacterControllerPortRef.get_move_local(normalized_frame)
	var gait_name := CharacterControllerPortRef.get_gait_name(normalized_frame)
	var action_name := CharacterControllerPortRef.get_action_name(normalized_frame)
	var desired_facing_yaw := CharacterControllerPortRef.get_desired_facing_yaw(normalized_frame, body.rotation.y)
	var facing_turn_speed := _get_body_float(body, "facing_turn_speed", 8.0)
	body.rotation.y = rotate_toward(body.rotation.y, desired_facing_yaw, facing_turn_speed * delta)
	var forward := -body.global_basis.z
	var right := body.global_basis.x
	var target_planar_velocity := Vector3.ZERO
	if move_local.length() > 0.001:
		var speed_property := "run_speed" if gait_name == "run" else "walk_speed"
		var target_speed := _get_body_float(
			body,
			speed_property,
			4.0
		)
		target_planar_velocity = ((right * move_local.x) + (forward * move_local.y)).normalized() * target_speed

	var accel := _get_body_float(body, "acceleration", 18.0)
	var decel := _get_body_float(body, "deceleration", 20.0)
	var planar_lerp := accel if move_local.length() > 0.001 else decel
	body.velocity.x = move_toward(body.velocity.x, target_planar_velocity.x, planar_lerp * delta)
	body.velocity.z = move_toward(body.velocity.z, target_planar_velocity.z, planar_lerp * delta)
	_apply_vertical_motion(body, action_name, gait_name, move_local, delta)
	body.move_and_slide()
	return CharacterActorSchemaRef.normalize_motion_state(
		{
		"position": body.global_position,
		"velocity_world": body.velocity,
		"facing_yaw": body.rotation.y,
		"move_local_actual": move_local,
		"gait_actual": gait_name,
		"grounded": body.is_on_floor(),
		}
	)


func _apply_vertical_motion(
	body: CharacterBody3D,
	action_name: String,
	gait_name: String,
	move_local: Vector2,
	delta: float
) -> void:
	if body.is_on_floor():
		if body.velocity.y < 0.0:
			body.velocity.y = 0.0
		if action_name.begins_with("jump"):
			var jump_variant := "single_leg" if action_name == "jump_single_leg" else "two_foot"
			if body.has_method("set_jump_variant_profile"):
				body.call("set_jump_variant_profile", jump_variant)
			body.velocity.y = _get_body_float(body, "jump_velocity", 0.0)
			if move_local.length() > 0.001:
				var forward := -body.global_basis.z
				var right := body.global_basis.x
				var launch_direction := ((right * move_local.x) + (forward * move_local.y)).normalized()
				var launch_speed := _get_body_float(body, "walk_speed", 5.0) * 1.15
				if jump_variant == "single_leg" or gait_name == "run":
					launch_speed = _get_body_float(body, "run_speed", 9.0) * 1.05
				body.velocity.x = launch_direction.x * launch_speed
				body.velocity.z = launch_direction.z * launch_speed
		return

	var gravity_property := "jump_gravity" if body.velocity.y >= 0.0 else "fall_gravity"
	var gravity := _get_body_float(
		body,
		gravity_property,
		0.0
	)
	body.velocity.y -= gravity * delta


func _get_body_float(body: CharacterBody3D, property_name: String, fallback: float) -> float:
	if body and body.has_method("get_numeric_setting"):
		var value: Variant = body.get_numeric_setting(StringName(property_name), fallback)
		if value is float:
			return value
		if value is int:
			return float(value)
	return fallback
