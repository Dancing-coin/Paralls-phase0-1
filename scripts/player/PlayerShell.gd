extends CharacterBody3D

@export_group("Input actions")
@export var move_forward_action: StringName = &"phase0_move_forward"
@export var move_backward_action: StringName = &"phase0_move_backward"
@export var move_left_action: StringName = &"phase0_move_left"
@export var move_right_action: StringName = &"phase0_move_right"
@export var run_action: StringName = &"phase0_run"
@export var jump_action: StringName = &"phase0_jump"
@export var mouse_mode_action: StringName = &"phase0_mouse_mode"
@export var cam_zoom_in_action: StringName = &"phase0_camera_zoom_in"
@export var cam_zoom_out_action: StringName = &"phase0_camera_zoom_out"

@export_group("Movement")
@export var walk_speed: float = 5.0
@export var run_speed: float = 9.0
@export var acceleration: float = 18.0
@export var deceleration: float = 20.0
@export var jump_height: float = 3.0
@export var jump_time_to_peak: float = 0.35
@export var jump_time_to_descent: float = 0.29

@export_group("Camera")
@export var mouse_sensitivity: float = 0.004
@export var min_pitch_degrees: float = -65.0
@export var max_pitch_degrees: float = 18.0
@export var zoom_step: float = 0.6
@export var min_spring_length: float = 2.2
@export var max_spring_length: float = 9.0

@onready var visual_root: Node3D = $VisualRoot
@onready var cam_holder: Node3D = $CameraHolder
@onready var spring_arm: SpringArm3D = $CameraHolder/SpringArm3D
@onready var camera: Camera3D = $CameraHolder/SpringArm3D/Camera3D
@onready var external_motion_driver: Node = get_node_or_null("Phase0InputBridge")
@onready var character_motor: Node = get_node_or_null("CharacterMotor")

var base_jump_velocity: float = 0.0
var base_jump_gravity: float = 0.0
var base_fall_gravity: float = 0.0
var jump_velocity: float = 0.0
var jump_gravity: float = 0.0
var fall_gravity: float = 0.0
var current_jump_variant: String = "default"
var current_intent_frame: Dictionary = {}
var motion_state: Dictionary = {}
var look_pitch := 0.0

func _ready() -> void:
	_recalculate_jump_profile()
	Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)
	look_pitch = cam_holder.rotation.x
	cam_holder.rotation.y = 0.0

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed(mouse_mode_action):
		if Input.get_mouse_mode() == Input.MOUSE_MODE_CAPTURED:
			Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
		else:
			Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)
	if event is InputEventMouseMotion and Input.get_mouse_mode() == Input.MOUSE_MODE_CAPTURED:
		var motion := event as InputEventMouseMotion
		rotation.y -= motion.relative.x * mouse_sensitivity
		look_pitch = clamp(
			look_pitch - motion.relative.y * mouse_sensitivity,
			deg_to_rad(min_pitch_degrees),
			deg_to_rad(max_pitch_degrees)
		)
		cam_holder.rotation.x = look_pitch
		cam_holder.rotation.y = 0.0
	if event.is_action_pressed(cam_zoom_in_action):
		spring_arm.spring_length = max(min_spring_length, spring_arm.spring_length - zoom_step)
	if event.is_action_pressed(cam_zoom_out_action):
		spring_arm.spring_length = min(max_spring_length, spring_arm.spring_length + zoom_step)

func _physics_process(delta: float) -> void:
	current_intent_frame = _build_human_intent_frame()
	if external_motion_driver and external_motion_driver.has_method("set_human_intent_frame"):
		external_motion_driver.set_human_intent_frame(current_intent_frame)

	_apply_gravity(delta)
	if external_motion_driver and external_motion_driver.has_method("before_player_shell_move"):
		external_motion_driver.before_player_shell_move(delta)
	else:
		_apply_direct_input_motion(delta)

	move_and_slide()
	_publish_motion_state()

	if external_motion_driver and external_motion_driver.has_method("after_player_shell_move"):
		external_motion_driver.after_player_shell_move(delta)

func _apply_gravity(delta: float) -> void:
	if is_on_floor():
		if velocity.y < 0.0:
			velocity.y = 0.0
		return
	if velocity.y >= 0.0:
		velocity.y -= jump_gravity * delta
	else:
		velocity.y -= fall_gravity * delta

func _apply_direct_input_motion(delta: float) -> void:
	var move_local: Vector2 = current_intent_frame.get("move_local", Vector2.ZERO)
	if move_local.length() > 0.001:
		var forward := -global_basis.z
		var right := global_basis.x
		var move_direction := ((right * move_local.x) + (forward * move_local.y)).normalized()
		var speed: float = walk_speed
		if str(current_intent_frame.get("gait", "walk")) == "run":
			speed = run_speed
		velocity.x = move_toward(velocity.x, move_direction.x * speed, acceleration * delta)
		velocity.z = move_toward(velocity.z, move_direction.z * speed, acceleration * delta)
	else:
		velocity.x = move_toward(velocity.x, 0.0, deceleration * delta)
		velocity.z = move_toward(velocity.z, 0.0, deceleration * delta)

	if is_on_floor() and Input.is_action_just_pressed(jump_action):
		var jump_variant: String = "two_foot"
		if str(current_intent_frame.get("gait", "walk")) == "run" and move_local.length() > 0.001:
			jump_variant = "single_leg"
		var jump_forward := ((global_basis.x * move_local.x) + (-global_basis.z * move_local.y)).normalized()
		force_jump_now(jump_variant, jump_forward)

func set_jump_variant_profile(variant: String) -> void:
	current_jump_variant = variant
	match variant:
		"single_leg":
			jump_velocity = base_jump_velocity * 1.16
			jump_gravity = base_jump_gravity * 1.05
			fall_gravity = base_fall_gravity * 1.12
		"two_foot":
			jump_velocity = base_jump_velocity
			jump_gravity = base_jump_gravity
			fall_gravity = base_fall_gravity
		_:
			jump_velocity = base_jump_velocity
			jump_gravity = base_jump_gravity
			fall_gravity = base_fall_gravity

func force_jump_now(variant: String, takeoff_direction: Vector3 = Vector3.ZERO) -> bool:
	set_jump_variant_profile(variant)
	if not is_on_floor():
		return false
	velocity.y = jump_velocity
	var planar_direction := Vector3(takeoff_direction.x, 0.0, takeoff_direction.z)
	if planar_direction.length() > 0.001:
		planar_direction = planar_direction.normalized()
		var launch_speed := walk_speed * 1.15
		if variant == "single_leg":
			launch_speed = run_speed * 1.05
		velocity.x = planar_direction.x * launch_speed
		velocity.z = planar_direction.z * launch_speed
	return true

func can_trigger_movement_jump() -> bool:
	if external_motion_driver and external_motion_driver.has_method("can_trigger_movement_jump"):
		return external_motion_driver.can_trigger_movement_jump()
	var input_vector := Input.get_vector(move_left_action, move_right_action, move_forward_action, move_backward_action)
	return input_vector.length() > 0.001

func get_camera() -> Camera3D:
	return camera

func _build_human_intent_frame() -> Dictionary:
	var move_local := Input.get_vector(move_left_action, move_right_action, move_forward_action, move_backward_action)
	var gait := "run" if Input.is_action_pressed(run_action) and move_local.length() > 0.001 else "walk"
	return {
		"controller_source": "human",
		"move_local": move_local,
		"desired_facing_yaw": rotation.y,
		"look_pitch": look_pitch,
		"gait": gait,
		"action": "locomotion" if move_local.length() > 0.001 else "idle",
	}

func _publish_motion_state() -> void:
	# CharacterMotionState placeholder until the motor owns the full payload.
	motion_state = {
		"controller_source": current_intent_frame.get("controller_source", "human"),
		"move_local": current_intent_frame.get("move_local", Vector2.ZERO),
		"desired_facing_yaw": current_intent_frame.get("desired_facing_yaw", rotation.y),
		"look_pitch": current_intent_frame.get("look_pitch", look_pitch),
		"velocity_world": velocity,
		"grounded": is_on_floor(),
	}

func _recalculate_jump_profile() -> void:
	base_jump_velocity = (2.0 * jump_height) / jump_time_to_peak
	base_jump_gravity = (2.0 * jump_height) / (jump_time_to_peak * jump_time_to_peak)
	base_fall_gravity = (2.0 * jump_height) / (jump_time_to_descent * jump_time_to_descent)
	set_jump_variant_profile(current_jump_variant)
