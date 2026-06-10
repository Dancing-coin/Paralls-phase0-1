extends CharacterBody3D

@export var move_forward_action := "play_char_move_forward_action"
@export var move_backward_action := "play_char_move_backward_action"
@export var move_left_action := "play_char_move_left_action"
@export var move_right_action := "play_char_move_right_action"
@export var run_action := "play_char_run_action"
@export var jump_action := "play_char_jump_action"
@export var walk_speed := 2.8
@export var brisk_walk_speed := 3.9
@export var run_speed := 5.6
@export var crouch_speed := 1.7
@export var jump_velocity := 5.0
@export var gravity := 12.5
@export var acceleration := 10.0
@export var deceleration := 12.0

@onready var cam_holder: Node3D = $CameraHolder
@onready var phase0_input_bridge: Node = $Phase0InputBridge

var jump_variant_profile := "default"
var _forced_jump_variant := ""
var _forced_jump_direction := Vector3.ZERO


func _physics_process(delta: float) -> void:
	if phase0_input_bridge and phase0_input_bridge.has_method("before_player_shell_move"):
		phase0_input_bridge.before_player_shell_move(delta)

	var move_direction := _resolve_move_direction()
	var speed := _resolve_move_speed(move_direction)
	var target_velocity := move_direction * speed

	velocity.x = move_toward(velocity.x, target_velocity.x, _resolve_horizontal_rate(target_velocity) * delta)
	velocity.z = move_toward(velocity.z, target_velocity.z, _resolve_horizontal_rate(target_velocity) * delta)

	if not is_on_floor():
		velocity.y -= gravity * delta
	elif _should_jump(move_direction):
		velocity.y = jump_velocity

	move_and_slide()

	if phase0_input_bridge and phase0_input_bridge.has_method("after_player_shell_move"):
		phase0_input_bridge.after_player_shell_move(delta)


func set_jump_variant_profile(variant: String) -> void:
	jump_variant_profile = variant


func force_jump_now(variant: String, takeoff_direction: Vector3 = Vector3.ZERO) -> bool:
	if not is_on_floor():
		return false
	_forced_jump_variant = variant
	_forced_jump_direction = Vector3(takeoff_direction.x, 0.0, takeoff_direction.z)
	if _forced_jump_direction.length() > 1.0:
		_forced_jump_direction = _forced_jump_direction.normalized()
	velocity.y = jump_velocity
	if _forced_jump_direction.length() > 0.001:
		var boosted_speed: float = max(run_speed, brisk_walk_speed)
		velocity.x = _forced_jump_direction.x * boosted_speed
		velocity.z = _forced_jump_direction.z * boosted_speed
	return true


func _resolve_move_direction() -> Vector3:
	if phase0_input_bridge and phase0_input_bridge.has_method("get_forced_move_direction"):
		var forced_direction: Vector3 = phase0_input_bridge.get_forced_move_direction()
		if forced_direction.length() > 0.001:
			return Vector3(forced_direction.x, 0.0, forced_direction.z).normalized()

	var input_vector := Input.get_vector(
		move_left_action,
		move_right_action,
		move_forward_action,
		move_backward_action
	)
	if input_vector.length() <= 0.001:
		return Vector3.ZERO

	var local_direction := Vector3(input_vector.x, 0.0, input_vector.y)
	return local_direction.rotated(Vector3.UP, -cam_holder.global_rotation.y).normalized()


func _resolve_move_speed(move_direction: Vector3) -> float:
	if move_direction.length() <= 0.001:
		return 0.0
	if phase0_input_bridge and phase0_input_bridge.has_method("get_current_stance_name"):
		if str(phase0_input_bridge.get_current_stance_name()) == "crouch":
			return crouch_speed
	if phase0_input_bridge and phase0_input_bridge.has_method("is_forced_run_requested"):
		if bool(phase0_input_bridge.is_forced_run_requested()):
			return run_speed
	if Input.is_action_pressed(run_action):
		return run_speed
	if phase0_input_bridge and phase0_input_bridge.has_method("get_current_gait_name"):
		match str(phase0_input_bridge.get_current_gait_name()):
			"amble":
				return walk_speed
			"brisk_walk":
				return brisk_walk_speed
			"run":
				return run_speed
	return brisk_walk_speed


func _resolve_horizontal_rate(target_velocity: Vector3) -> float:
	return acceleration if target_velocity.length() > 0.001 else deceleration


func _should_jump(move_direction: Vector3) -> bool:
	if _forced_jump_variant != "":
		_forced_jump_variant = ""
		if _forced_jump_direction.length() > 0.001:
			var boosted_speed: float = max(run_speed, brisk_walk_speed)
			velocity.x = _forced_jump_direction.x * boosted_speed
			velocity.z = _forced_jump_direction.z * boosted_speed
		_forced_jump_direction = Vector3.ZERO
		return true
	if Input.is_action_just_pressed(jump_action):
		return true
	return false
