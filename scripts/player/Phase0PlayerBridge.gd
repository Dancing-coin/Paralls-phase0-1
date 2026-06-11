extends Node

@export var dialogue_action := "phase0_submit_dialogue"
@export var interact_action := "phase0_interact"
@export var guard_pose_action := "phase0_knight_guard_pose"
@export var observe_pose_action := "phase0_knight_observe_pose"
@export var speak_pose_action := "phase0_knight_speak_pose"
@export var inspect_pose_action := "phase0_knight_inspect_pose"
@export var alert_pose_action := "phase0_knight_alert_pose"
@export var ambient_pose_action := "phase0_knight_ambient_pose"
@export var gait_cycle_action := "phase0_cycle_walk_mode"
@export var crouch_toggle_action := "phase0_toggle_crouch"
@export var character_c_sync_enabled := true
@export var hide_player_visual_shell := true
@export var player_root_motion_enabled := true

@onready var embodiment: Node = $"../Phase0Embodiment"
@onready var player: CharacterBody3D = get_parent() as CharacterBody3D

var forced_move_direction := Vector3.ZERO
var forced_run_state := false
var forced_jump_request := ""
var locomotion_gait_mode := 1
var locomotion_stance_mode := 0
var current_jump_type := "none"
var current_intent_frame: Dictionary = {}
var desired_facing_yaw := 0.0

const STANCE_STAND := 0
const STANCE_CROUCH := 1
const GAIT_CYCLE := ["amble", "walk", "brisk_walk"]

# The player-controlled role shell now lives under the same CharacterBase root.
# Phase0InputBridge still maps local controls into the visible knight child.

func _ready() -> void:
	if hide_player_visual_shell:
		_set_player_visual_shell_visible(false)

func _physics_process(_delta: float) -> void:
	if player_root_motion_enabled:
		if not character_c_sync_enabled:
			_clear_character_c_sync()
		return
	if not character_c_sync_enabled:
		_clear_character_c_sync()
		return
	_sync_character_c_from_player()

func _unhandled_input(event: InputEvent) -> void:
	var main_demo := _get_main_demo()
	if main_demo == null:
		return

	if event.is_action_pressed(gait_cycle_action):
		_cycle_gait_mode()

	if event.is_action_pressed(crouch_toggle_action):
		_toggle_crouch_mode()

	if event.is_action_pressed(dialogue_action) and main_demo.has_method("submit_dialogue"):
		if embodiment and embodiment.has_method("trigger_dialogue_feedback"):
			embodiment.trigger_dialogue_feedback()
		_trigger_character_c_action("speak")
		main_demo.submit_dialogue()

	if event.is_action_pressed(interact_action) and main_demo.has_method("submit_interaction"):
		if embodiment and embodiment.has_method("trigger_interact_feedback"):
			embodiment.trigger_interact_feedback()
		_trigger_character_c_action("inspect")
		main_demo.submit_interaction()

	if event.is_action_pressed(guard_pose_action):
		_trigger_character_c_action("guard")
	if event.is_action_pressed(observe_pose_action):
		_trigger_character_c_action("observe")
	if event.is_action_pressed(speak_pose_action):
		_trigger_character_c_action("speak")
	if event.is_action_pressed(inspect_pose_action):
		_trigger_character_c_action("inspect")
	if event.is_action_pressed(alert_pose_action):
		_trigger_character_c_action("alert")
	if event.is_action_pressed(ambient_pose_action):
		_trigger_character_c_action("ambient")

func trigger_dialogue() -> void:
	var main_demo := _get_main_demo()
	if embodiment and embodiment.has_method("trigger_dialogue_feedback"):
		embodiment.trigger_dialogue_feedback()
	_trigger_character_c_action("speak")
	if main_demo and main_demo.has_method("submit_dialogue"):
		main_demo.submit_dialogue()

func trigger_interaction() -> void:
	var main_demo := _get_main_demo()
	if embodiment and embodiment.has_method("trigger_interact_feedback"):
		embodiment.trigger_interact_feedback()
	_trigger_character_c_action("inspect")
	if main_demo and main_demo.has_method("submit_interaction"):
		main_demo.submit_interaction()

func _get_main_demo() -> Node:
	return get_tree().current_scene

func set_character_c_sync_enabled(enabled: bool) -> void:
	character_c_sync_enabled = enabled
	if not enabled:
		_clear_character_c_sync()

func set_human_intent_frame(frame: Dictionary) -> void:
	current_intent_frame = frame.duplicate(true)
	desired_facing_yaw = float(current_intent_frame.get("desired_facing_yaw", player.global_rotation.y))

func set_forced_player_motion(world_direction: Vector3, wants_run: bool = false) -> void:
	forced_move_direction = Vector3(world_direction.x, 0.0, world_direction.z)
	if forced_move_direction.length() > 1.0:
		forced_move_direction = forced_move_direction.normalized()
	forced_run_state = wants_run

func clear_forced_player_motion() -> void:
	forced_move_direction = Vector3.ZERO
	forced_run_state = false

func trigger_forced_jump(jump_type: String) -> void:
	forced_jump_request = jump_type

func before_player_shell_move(delta: float) -> void:
	if not player_root_motion_enabled or not character_c_sync_enabled:
		return
	_apply_player_root_motion_drive(delta)

func after_player_shell_move(_delta: float) -> void:
	if not player_root_motion_enabled:
		return
	if not character_c_sync_enabled:
		_clear_character_c_sync()
		return
	_sync_character_c_from_player()

func _sync_character_c_from_player() -> void:
	var character_c := _get_character_c()
	if character_c == null:
		return

	var planar_velocity := Vector3(player.velocity.x, 0.0, player.velocity.z)
	var look_target := _resolve_player_look_target()
	if character_c.has_method("apply_player_shell_pose"):
		character_c.apply_player_shell_pose(player.global_position, planar_velocity, look_target, player.is_on_floor())
		return
	if character_c.has_method("apply_player_shell_frame"):
		character_c.apply_player_shell_frame(player.global_position, planar_velocity, look_target, player.is_on_floor())

func _apply_player_root_motion_drive(delta: float) -> void:
	var character_c := _get_character_c()
	if character_c == null or not character_c.has_method("begin_player_control_frame"):
		return

	var move_direction := _resolve_player_move_direction()
	var wants_run := _should_run(move_direction)
	var look_target := _resolve_player_look_target()
	var jump_type := _resolve_jump_type(move_direction, wants_run)
	if forced_jump_request != "" and player and player.has_method("force_jump_now"):
		if player.force_jump_now(forced_jump_request, move_direction):
			current_jump_type = forced_jump_request
			jump_type = forced_jump_request
		forced_jump_request = ""
	if player and player.has_method("set_jump_variant_profile"):
		player.set_jump_variant_profile(jump_type if jump_type != "none" else "default")
	if jump_type != "none" and locomotion_stance_mode == STANCE_CROUCH:
		locomotion_stance_mode = STANCE_STAND
	var stance_name := _resolve_stance_name()
	var gait_name := _resolve_gait_name(move_direction, wants_run)
	character_c.begin_player_control_frame(player.global_position, move_direction, look_target, player.is_on_floor(), wants_run, gait_name, stance_name, jump_type)

	if not player.is_on_floor():
		return

	var requested_step := Vector3.ZERO
	if character_c.has_method("consume_player_root_motion_request"):
		var step: Variant = character_c.consume_player_root_motion_request(delta)
		if step is Vector3:
			requested_step = step as Vector3

	player.velocity.x = requested_step.x / max(delta, 0.0001)
	player.velocity.z = requested_step.z / max(delta, 0.0001)

func _clear_character_c_sync() -> void:
	var character_c := _get_character_c()
	if character_c and character_c.has_method("clear_player_shell_frame"):
		character_c.clear_player_shell_frame()

func get_control_anchor_position() -> Vector3:
	var character_c := _get_character_c()
	if character_c and character_c.has_method("is_player_shell_active") and character_c.is_player_shell_active():
		if character_c.has_method("get_role_anchor_position"):
			return character_c.get_role_anchor_position()
		if character_c is Node3D:
			return (character_c as Node3D).global_position
	return player.global_position

func get_control_forward() -> Vector3:
	var character_c := _get_character_c()
	if character_c and character_c.has_method("is_player_shell_active") and character_c.is_player_shell_active():
		var look_target := _resolve_player_look_target()
		var forward := look_target - get_control_anchor_position()
		forward.y = 0.0
		if forward.length() > 0.001:
			return forward.normalized()
		if character_c is Node3D:
			return -((character_c as Node3D).global_basis.z).normalized()
	return _resolve_player_forward()

func get_camera() -> Camera3D:
	return _find_camera()

func _resolve_player_look_target() -> Vector3:
	if forced_move_direction.length() > 0.001:
		return player.global_position + forced_move_direction.normalized()
	if not current_intent_frame.is_empty():
		return player.global_position + Vector3.FORWARD.rotated(Vector3.UP, desired_facing_yaw)
	var visual_root := player.find_child("VisualRoot", true, false)
	if visual_root is Node3D:
		return player.global_position - (visual_root as Node3D).global_basis.z
	var camera_holder := player.find_child("CameraHolder", true, false)
	if camera_holder is Node3D:
		return player.global_position - (camera_holder as Node3D).global_basis.z
	var camera := _find_camera()
	if camera is Camera3D:
		return player.global_position - (camera as Camera3D).global_basis.z
	return player.global_position - player.global_basis.z

func _resolve_player_forward() -> Vector3:
	if not current_intent_frame.is_empty():
		return Vector3.FORWARD.rotated(Vector3.UP, desired_facing_yaw).normalized()
	var visual_root := player.find_child("VisualRoot", true, false)
	if visual_root is Node3D:
		return -((visual_root as Node3D).global_basis.z).normalized()
	var camera_holder := player.find_child("CameraHolder", true, false)
	if camera_holder is Node3D:
		return -((camera_holder as Node3D).global_basis.z).normalized()
	var camera := _find_camera()
	if camera:
		return -(camera.global_basis.z).normalized()
	return -(player.global_basis.z).normalized()

func _set_player_visual_shell_visible(is_visible: bool) -> void:
	var visual_root := player.find_child("VisualRoot", true, false)
	if visual_root is Node3D:
		(visual_root as Node3D).visible = is_visible

func _resolve_player_move_direction() -> Vector3:
	if forced_move_direction.length() > 0.001:
		return forced_move_direction
	if player == null:
		return Vector3.ZERO

	var move_local_value: Variant = current_intent_frame.get("move_local", Vector2.ZERO)
	var move_local: Vector2 = move_local_value if move_local_value is Vector2 else Vector2.ZERO
	if move_local.length() <= 0.001:
		return Vector3.ZERO
	var facing_yaw := desired_facing_yaw if not current_intent_frame.is_empty() else player.global_rotation.y
	var forward := Vector3.FORWARD.rotated(Vector3.UP, facing_yaw)
	var right := Vector3.RIGHT.rotated(Vector3.UP, facing_yaw)
	var move_direction := (right * move_local.x) + (forward * move_local.y)
	return move_direction.normalized()

func _cycle_gait_mode() -> void:
	if locomotion_stance_mode == STANCE_CROUCH:
		return
	locomotion_gait_mode = (locomotion_gait_mode + 1) % GAIT_CYCLE.size()

func _toggle_crouch_mode() -> void:
	if locomotion_stance_mode == STANCE_STAND:
		locomotion_stance_mode = STANCE_CROUCH
	else:
		locomotion_stance_mode = STANCE_STAND

func set_gait_mode_by_name(gait_name: String) -> void:
	var idx := GAIT_CYCLE.find(gait_name)
	if idx >= 0:
		locomotion_gait_mode = idx

func set_crouch_enabled(enabled: bool) -> void:
	locomotion_stance_mode = STANCE_CROUCH if enabled else STANCE_STAND

func _should_run(move_direction: Vector3) -> bool:
	var gait_name := str(current_intent_frame.get("gait", ""))
	return (
		locomotion_stance_mode == STANCE_STAND
		and move_direction.length() > 0.001
		and (
			forced_run_state
			or gait_name == "run"
			or (player != null and Input.is_action_pressed(_get_player_action("run_action", &"phase0_run")))
		)
	)

func _resolve_stance_name() -> String:
	return "crouch" if locomotion_stance_mode == STANCE_CROUCH else "stand"

func _resolve_gait_name(move_direction: Vector3, wants_run: bool) -> String:
	if locomotion_stance_mode == STANCE_CROUCH:
		return "crouch_walk" if move_direction.length() > 0.001 else "crouch_idle"
	if move_direction.length() <= 0.001:
		return GAIT_CYCLE[locomotion_gait_mode]
	if wants_run:
		return "run"
	return GAIT_CYCLE[locomotion_gait_mode]

func _resolve_jump_type(move_direction: Vector3, wants_run: bool) -> String:
	if player == null:
		return "none"
	if player.is_on_floor():
		if Input.is_action_just_pressed(_get_player_action("jump_action", &"phase0_jump")) and move_direction.length() > 0.001:
			current_jump_type = "single_leg" if wants_run else "two_foot"
		elif current_jump_type != "none" and abs(player.velocity.y) > 0.001:
			return current_jump_type
		elif current_jump_type != "none":
			current_jump_type = "none"
	else:
		if current_jump_type == "none" and move_direction.length() > 0.001:
			current_jump_type = "single_leg" if wants_run else "two_foot"
	return current_jump_type

func can_trigger_movement_jump() -> bool:
	return _resolve_player_move_direction().length() > 0.001

func _get_character_c() -> Node:
	if player == null:
		return null
	return player.get_node_or_null("CharacterReplica")

func _trigger_character_c_action(action_name: String) -> void:
	var character_c := _get_character_c()
	if character_c and character_c.has_method("perform_action"):
		character_c.perform_action(action_name)

func _find_camera() -> Camera3D:
	var found := player.find_child("Camera3D", true, false)
	if found is Camera3D:
		return found as Camera3D
	return null

func _get_player_action(property_name: StringName, fallback: StringName) -> StringName:
	if player == null:
		return fallback
	var value: Variant = player.get(property_name)
	if value is StringName:
		return value as StringName
	if value is String:
		return StringName(value)
	return fallback
