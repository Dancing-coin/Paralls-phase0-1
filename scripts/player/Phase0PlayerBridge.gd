extends Node

const CharacterControlModeRef = preload("res://scripts/character/CharacterControlMode.gd")

@export var character_c_sync_enabled := true
@export var hide_player_visual_shell := true
@export var player_root_motion_enabled := true

@onready var player: CharacterBody3D = get_parent() as CharacterBody3D

var forced_move_direction := Vector3.ZERO
var forced_run_state := false
var forced_jump_request := ""
var locomotion_gait_mode := 1
var locomotion_stance_mode := 0
var current_jump_type := "none"
var current_intent_frame: Dictionary = {}
var desired_facing_yaw := 0.0
var sword_swing_pressed := false
var shield_block_pressed := false

const STANCE_STAND := 0
const STANCE_CROUCH := 1
const GAIT_CYCLE := ["amble", "walk", "brisk_walk"]

# The player-controlled role shell now lives under the same CharacterBase root.
# Phase0InputBridge still maps local controls into the visible knight child.

func _ready() -> void:
	_bus_log("phase0_input_bridge_ready:combat_mouse_v3")
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

func cycle_gait_mode() -> void:
	_cycle_gait_mode()

func toggle_crouch_mode() -> void:
	_toggle_crouch_mode()

func trigger_dialogue() -> void:
	var main_demo := _get_main_demo()
	if main_demo != null and main_demo.has_method("submit_dialogue"):
		main_demo.submit_dialogue()

func trigger_interaction() -> void:
	var main_demo := _get_main_demo()
	if main_demo != null and main_demo.has_method("submit_interaction"):
		main_demo.submit_interaction()

func trigger_role_action(action_tag: String) -> void:
	_trigger_character_c_action(action_tag)

func trigger_combat_action(action_tag: String) -> void:
	_trigger_combat_action(action_tag)

func handle_mouse_combat_event(event: InputEventMouseButton) -> void:
	_bus_log("combat_mouse_event:button=%s pressed=%s device=%s" % [event.button_index, str(event.pressed), event.device])
	if event.button_index == MOUSE_BUTTON_LEFT:
		if event.pressed:
			if not sword_swing_pressed:
				_trigger_combat_action("sword_swing")
			sword_swing_pressed = true
		else:
			sword_swing_pressed = false
	elif event.button_index == MOUSE_BUTTON_RIGHT:
		if event.pressed:
			if not shield_block_pressed:
				_trigger_combat_action("shield_block")
			shield_block_pressed = true
		else:
			shield_block_pressed = false

func _trigger_combat_action(action_name: String) -> void:
	_bus_log("player_combat_action:%s" % action_name)
	_trigger_character_c_action(action_name)

func _get_main_demo() -> Node:
	return get_tree().current_scene

func set_character_c_sync_enabled(enabled: bool) -> void:
	character_c_sync_enabled = enabled
	if not enabled:
		_clear_character_c_sync()

func set_human_intent_frame(frame: Dictionary) -> void:
	current_intent_frame = frame.duplicate(true)
	current_intent_frame["control_mode"] = CharacterControlModeRef.HUMAN_CONTROLLED
	desired_facing_yaw = float(current_intent_frame.get("desired_facing_yaw", player.global_rotation.y))

func set_forced_player_motion(world_direction: Vector3, wants_run: bool = false) -> void:
	forced_move_direction = Vector3(world_direction.x, 0.0, world_direction.z)
	if forced_move_direction.length() > 1.0:
		forced_move_direction = forced_move_direction.normalized()
	forced_run_state = wants_run
	if player and player.has_method("set_forced_control"):
		var local_x := forced_move_direction.dot(player.global_basis.x)
		var local_y := forced_move_direction.dot(-player.global_basis.z)
		player.set_forced_control(Vector2(local_x, local_y), wants_run)

func clear_forced_player_motion() -> void:
	forced_move_direction = Vector3.ZERO
	forced_run_state = false
	if player and player.has_method("clear_forced_control"):
		player.clear_forced_control()

func trigger_forced_jump(jump_type: String) -> void:
	forced_jump_request = jump_type

func before_player_shell_move(delta: float) -> void:
	if not player_root_motion_enabled or not character_c_sync_enabled:
		return
	_sync_character_c_control_frame(delta)

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

func _sync_character_c_control_frame(delta: float) -> void:
	var character_c := _get_character_c()
	if character_c == null or not character_c.has_method("begin_player_control_frame"):
		return

	var move_direction := _resolve_player_move_direction()
	var wants_run := _should_run(move_direction)
	var look_target := _resolve_player_look_target()
	var jump_type := _resolve_jump_type(move_direction, wants_run)
	if forced_jump_request != "" and player and player.has_method("queue_forced_jump"):
		player.queue_forced_jump(forced_jump_request)
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
	if character_c.has_method("consume_player_root_motion_request"):
		character_c.consume_player_root_motion_request(delta)

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
		return player.global_position + _forward_from_yaw(desired_facing_yaw)
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
		return _forward_from_yaw(desired_facing_yaw)
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
	var forward := _forward_from_yaw(facing_yaw)
	var right := Vector3.RIGHT.rotated(Vector3.UP, facing_yaw)
	var move_direction := (right * move_local.x) + (forward * move_local.y)
	return move_direction.normalized()

func _forward_from_yaw(yaw: float) -> Vector3:
	return -Vector3.FORWARD.rotated(Vector3.UP, yaw).normalized()

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
	var requested_action := str(current_intent_frame.get("action", ""))
	if player.is_on_floor():
		if requested_action.begins_with("jump") and move_direction.length() > 0.001:
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

func _bus_log(message: String) -> void:
	var bus := get_node_or_null("/root/LocalPresentationBus")
	if bus and bus.has_method("log_debug"):
		bus.log_debug(message)

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
