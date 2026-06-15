extends CharacterBody3D

const CharacterActorSchemaRef = preload("res://scripts/character/CharacterActorSchema.gd")
const CharacterControlModeRef = preload("res://scripts/character/CharacterControlMode.gd")
const HUMAN_CONTROL_MODE_NAME := "human_controlled"
const HUMAN_CONTROL_MODE := CharacterControlModeRef.HUMAN_CONTROLLED

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
var queued_jump_variant := ""
var queued_jump_move_local := Vector2.ZERO
var forced_move_local := Vector2.ZERO
var forced_run_state := false
var last_left_mouse_pressed := false
var last_right_mouse_pressed := false

func _ready() -> void:
	_recalculate_jump_profile()
	Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)
	look_pitch = cam_holder.rotation.x
	cam_holder.rotation.y = 0.0
	last_left_mouse_pressed = Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT)
	last_right_mouse_pressed = Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT)

func _input(event: InputEvent) -> void:
	_forward_combat_mouse_event(event)
	_forward_shell_action_event(event)

func _process(_delta: float) -> void:
	_poll_mouse_button_debug_state()

func _unhandled_input(event: InputEvent) -> void:
	_forward_combat_mouse_event(event)
	_forward_shell_action_event(event)
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

func _forward_combat_mouse_event(event: InputEvent) -> void:
	if not (event is InputEventMouseButton):
		return
	_bus_log("player_shell_mouse_button:button=%s pressed=%s device=%s" % [event.button_index, str((event as InputEventMouseButton).pressed), (event as InputEventMouseButton).device])
	if external_motion_driver and external_motion_driver.has_method("handle_mouse_combat_event"):
		external_motion_driver.handle_mouse_combat_event(event as InputEventMouseButton)

func _forward_shell_action_event(event: InputEvent) -> void:
	for child_name in ["Phase0InputBridge", "Phase0PlayerCommandRelay"]:
		var target := get_node_or_null(child_name)
		if target and target.has_method("handle_shell_action_event"):
			target.handle_shell_action_event(event)

func _poll_mouse_button_debug_state() -> void:
	var left_pressed := Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT)
	var right_pressed := Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT)
	if left_pressed != last_left_mouse_pressed or right_pressed != last_right_mouse_pressed:
		_bus_log("mouse_button_state:left=%s right=%s" % [str(left_pressed), str(right_pressed)])
	last_left_mouse_pressed = left_pressed
	last_right_mouse_pressed = right_pressed

func _bus_log(message: String) -> void:
	var bus := get_node_or_null("/root/LocalPresentationBus")
	if bus and bus.has_method("log_debug"):
		bus.log_debug(message)

func _physics_process(delta: float) -> void:
	current_intent_frame = _build_human_intent_frame()
	if external_motion_driver and external_motion_driver.has_method("set_human_intent_frame"):
		external_motion_driver.set_human_intent_frame(current_intent_frame)

	if external_motion_driver and external_motion_driver.has_method("before_player_shell_move"):
		external_motion_driver.before_player_shell_move(delta)
	if character_motor and character_motor.has_method("apply_intent_frame"):
		_publish_motion_state(character_motor.apply_intent_frame(self, current_intent_frame, delta))
	else:
		_publish_motion_state({})

	if external_motion_driver and external_motion_driver.has_method("after_player_shell_move"):
		external_motion_driver.after_player_shell_move(delta)

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
	if not is_on_floor():
		return false
	var planar_direction := Vector3(takeoff_direction.x, 0.0, takeoff_direction.z)
	if planar_direction.length() > 0.001:
		planar_direction = planar_direction.normalized()
		queued_jump_move_local = Vector2(planar_direction.dot(global_basis.x), planar_direction.dot(-global_basis.z))
	queued_jump_variant = variant
	return true

func can_trigger_movement_jump() -> bool:
	if external_motion_driver and external_motion_driver.has_method("can_trigger_movement_jump"):
		return external_motion_driver.can_trigger_movement_jump()
	return _current_move_local_input().length() > 0.001

func get_camera() -> Camera3D:
	return camera

func set_forced_control(move_local: Vector2, wants_run: bool) -> void:
	forced_move_local = move_local.limit_length(1.0)
	forced_run_state = wants_run

func clear_forced_control() -> void:
	forced_move_local = Vector2.ZERO
	forced_run_state = false

func queue_forced_jump(variant: String) -> void:
	queued_jump_variant = variant

func _build_human_intent_frame() -> Dictionary:
	var move_local := queued_jump_move_local if queued_jump_move_local.length() > 0.001 else _current_move_local_input()
	var gait := "run" if (forced_run_state or Input.is_action_pressed(run_action)) and move_local.length() > 0.001 else "walk"
	var action := "locomotion" if move_local.length() > 0.001 else "idle"
	if queued_jump_variant != "":
		action = "jump_%s" % queued_jump_variant
	elif is_on_floor() and Input.is_action_just_pressed(jump_action):
		action = "jump_single_leg" if gait == "run" and move_local.length() > 0.001 else "jump_two_foot"
	queued_jump_variant = ""
	queued_jump_move_local = Vector2.ZERO
	return {
		"controller_source": "human",
		"control_mode": HUMAN_CONTROL_MODE,
		"move_local": move_local,
		"desired_facing_yaw": rotation.y,
		"look_pitch": look_pitch,
		"gait": gait,
		"action": action,
	}

func _publish_motion_state(next_motion_state: Dictionary) -> void:
	if not next_motion_state.is_empty():
		motion_state = CharacterActorSchemaRef.normalize_motion_state(next_motion_state)
		return
	motion_state = CharacterActorSchemaRef.normalize_motion_state(
		{
		"position": global_position,
		"velocity_world": velocity,
		"facing_yaw": rotation.y,
		"camera_pitch": look_pitch,
		"move_local_actual": current_intent_frame.get("move_local", Vector2.ZERO),
		"gait_actual": current_intent_frame.get("gait", "walk"),
		"grounded": is_on_floor(),
		}
	)

func _current_move_local_input() -> Vector2:
	if forced_move_local.length() > 0.001:
		return forced_move_local
	var raw_move_local := Input.get_vector(
		move_left_action,
		move_right_action,
		move_forward_action,
		move_backward_action
	)
	return Vector2(raw_move_local.x, -raw_move_local.y)

func _recalculate_jump_profile() -> void:
	base_jump_velocity = (2.0 * jump_height) / jump_time_to_peak
	base_jump_gravity = (2.0 * jump_height) / (jump_time_to_peak * jump_time_to_peak)
	base_fall_gravity = (2.0 * jump_height) / (jump_time_to_descent * jump_time_to_descent)
	set_jump_variant_profile(current_jump_variant)
