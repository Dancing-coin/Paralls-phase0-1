extends Node

const CharacterControllerPortRef = preload("res://scripts/character/CharacterControllerPort.gd")
const CharacterControlModeRef = preload("res://scripts/character/CharacterControlMode.gd")
const CharacterShellSyncRef = preload("res://scripts/player/Phase0CharacterShellSync.gd")
const LocomotionControlStateRef = preload("res://scripts/player/Phase0LocomotionControlState.gd")
const ProgramControllerAdapterRef = preload("res://scripts/character/ProgramControllerAdapter.gd")
const ProgramControlStateRef = preload("res://scripts/player/Phase0ProgramControlState.gd")
const ViewAnchorResolverRef = preload("res://scripts/player/Phase0ViewAnchorResolver.gd")

@export var character_c_sync_enabled := true
@export var hide_player_visual_shell := true
@export var player_root_motion_enabled := true

@onready var player: CharacterBody3D = get_parent() as CharacterBody3D

var current_intent_frame: Dictionary = {}
var desired_facing_yaw := 0.0
var sword_swing_pressed := false
var shield_block_pressed := false
var character_shell_sync = CharacterShellSyncRef.new()
var locomotion_control_state = LocomotionControlStateRef.new()
var program_control_state = ProgramControlStateRef.new()
var view_anchor_resolver = ViewAnchorResolverRef.new()

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

func cycle_gait_mode() -> void:
	locomotion_control_state.cycle_gait_mode()

func toggle_crouch_mode() -> void:
	locomotion_control_state.toggle_crouch_mode()

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
	_trigger_character_c_action(action_name)

func _get_main_demo() -> Node:
	return get_tree().current_scene

func set_character_c_sync_enabled(enabled: bool) -> void:
	character_c_sync_enabled = enabled
	if not enabled:
		_clear_character_c_sync()

func set_human_intent_frame(frame: Dictionary) -> void:
	current_intent_frame = CharacterControllerPortRef.normalize_intent_frame(frame)
	desired_facing_yaw = CharacterControllerPortRef.get_desired_facing_yaw(current_intent_frame, player.global_rotation.y)

func build_program_intent_frame(candidate: Dictionary) -> Dictionary:
	return ProgramControllerAdapterRef.build_intent_frame("char_c", candidate)

func set_forced_player_motion(world_direction: Vector3, wants_run: bool = false) -> void:
	var _program_frame := build_program_intent_frame(
		{
			"move_local": Vector2(world_direction.x, -world_direction.z).limit_length(1.0),
			"look_local": Vector2.ZERO,
			"stance": locomotion_control_state.resolve_stance_name(),
			"gait": "run" if wants_run else "walk",
			"action": "locomotion",
		}
	)
	program_control_state.set_forced_player_motion(world_direction, wants_run)
	if player and player.has_method("set_forced_control"):
		var local_x: float = program_control_state.forced_move_direction.dot(player.global_basis.x)
		var local_y: float = program_control_state.forced_move_direction.dot(-player.global_basis.z)
		player.set_forced_control(Vector2(local_x, local_y), wants_run)

func clear_forced_player_motion() -> void:
	program_control_state.clear_forced_player_motion()
	if player and player.has_method("clear_forced_control"):
		player.clear_forced_control()

func trigger_forced_jump(jump_type: String) -> void:
	var _program_frame := build_program_intent_frame(
		{
			"look_local": Vector2.ZERO,
			"stance": locomotion_control_state.resolve_stance_name(),
			"action": "jump_%s" % jump_type,
		}
	)
	program_control_state.queue_forced_jump(jump_type)

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

	var planar_velocity: Vector3 = player.get_planar_velocity() if player and player.has_method("get_planar_velocity") else Vector3.ZERO
	var look_target := _resolve_player_look_target()
	character_shell_sync.sync_from_player_shell_pose(
		character_c,
		player.get_body_position() if player and player.has_method("get_body_position") else Vector3.ZERO,
		planar_velocity,
		look_target,
		player.is_grounded_state() if player and player.has_method("is_grounded_state") else false,
		player.get_motion_state() if player and player.has_method("get_motion_state") else {},
	)

func _sync_character_c_control_frame(delta: float) -> void:
	var character_c := _get_character_c()

	var move_direction := _resolve_player_move_direction()
	var wants_run := _should_run(move_direction)
	var look_target := _resolve_player_look_target()
	var jump_type := _resolve_jump_type(move_direction, wants_run)
	var queued_forced_jump: String = program_control_state.consume_forced_jump_request()
	if queued_forced_jump != "" and player and player.has_method("queue_forced_jump"):
		player.queue_forced_jump(queued_forced_jump)
		locomotion_control_state.current_jump_type = queued_forced_jump
		jump_type = queued_forced_jump
	if player and player.has_method("set_jump_variant_profile"):
		player.set_jump_variant_profile(jump_type if jump_type != "none" else "default")
	if jump_type != "none" and locomotion_control_state.locomotion_stance_mode == locomotion_control_state.STANCE_CROUCH:
		locomotion_control_state.set_crouch_enabled(false)
	var stance_name: String = locomotion_control_state.resolve_stance_name()
	var gait_name: String = locomotion_control_state.resolve_gait_name(move_direction, wants_run)
	character_shell_sync.sync_player_control_frame(
		character_c,
		player.get_body_position() if player and player.has_method("get_body_position") else Vector3.ZERO,
		move_direction,
		look_target,
		player.is_grounded_state() if player and player.has_method("is_grounded_state") else false,
		wants_run,
		gait_name,
		stance_name,
		jump_type,
		delta,
	)

func _clear_character_c_sync() -> void:
	var character_c := _get_character_c()
	character_shell_sync.clear_character_shell_frame(character_c)

func get_control_anchor_position() -> Vector3:
	var character_c := _get_character_c()
	return view_anchor_resolver.resolve_control_anchor_position(player, character_c)

func get_control_forward() -> Vector3:
	var character_c := _get_character_c()
	return view_anchor_resolver.resolve_control_forward(
		player,
		character_c,
		_resolve_player_look_target(),
		get_control_anchor_position(),
		_resolve_player_forward(),
	)

func get_camera() -> Camera3D:
	return _find_camera()

func _resolve_player_look_target() -> Vector3:
	return view_anchor_resolver.resolve_player_look_target(
		player,
		program_control_state,
		current_intent_frame,
		desired_facing_yaw,
		Callable(self, "_find_camera"),
	)

func _resolve_player_forward() -> Vector3:
	return view_anchor_resolver.resolve_player_forward(
		player,
		current_intent_frame,
		desired_facing_yaw,
		Callable(self, "_find_camera"),
	)

func _set_player_visual_shell_visible(is_visible: bool) -> void:
	var character_c := _get_character_c()
	if character_c and character_c.has_method("set_visual_shell_visible"):
		character_c.set_visual_shell_visible(is_visible)

func _resolve_player_move_direction() -> Vector3:
	if program_control_state.has_forced_move_direction():
		return program_control_state.forced_move_direction
	if player == null:
		return Vector3.ZERO

	var normalized_frame := CharacterControllerPortRef.normalize_intent_frame(current_intent_frame)
	var move_local := CharacterControllerPortRef.get_move_local(normalized_frame)
	if move_local.length() <= 0.001:
		return Vector3.ZERO
	var facing_yaw := CharacterControllerPortRef.get_desired_facing_yaw(normalized_frame, player.global_rotation.y)
	var forward: Vector3 = view_anchor_resolver._forward_from_yaw(facing_yaw)
	var right := Vector3.RIGHT.rotated(Vector3.UP, facing_yaw)
	var move_direction: Vector3 = (right * move_local.x) + (forward * move_local.y)
	return move_direction.normalized()

func set_gait_mode_by_name(gait_name: String) -> void:
	locomotion_control_state.set_gait_mode_by_name(gait_name)

func set_crouch_enabled(enabled: bool) -> void:
	locomotion_control_state.set_crouch_enabled(enabled)

func _should_run(move_direction: Vector3) -> bool:
	var normalized_frame := CharacterControllerPortRef.normalize_intent_frame(current_intent_frame)
	var gait_name := CharacterControllerPortRef.get_gait_name(normalized_frame)
	return (
		locomotion_control_state.locomotion_stance_mode == locomotion_control_state.STANCE_STAND
		and move_direction.length() > 0.001
		and (
			program_control_state.forced_run_state
			or gait_name == "run"
		)
	)

func _resolve_jump_type(move_direction: Vector3, wants_run: bool) -> String:
	if player == null:
		return "none"
	var normalized_frame := CharacterControllerPortRef.normalize_intent_frame(current_intent_frame)
	var requested_action := CharacterControllerPortRef.get_action_name(normalized_frame)
	return locomotion_control_state.resolve_jump_type(
		player.is_grounded_state() if player and player.has_method("is_grounded_state") else false,
		move_direction,
		wants_run,
		requested_action,
		player.get_vertical_velocity() if player and player.has_method("get_vertical_velocity") else 0.0,
	)

func can_trigger_movement_jump() -> bool:
	return _resolve_player_move_direction().length() > 0.001

func _get_character_c() -> Node:
	if player and player.has_method("get_character_replica"):
		return player.get_character_replica()
	return null

func _trigger_character_c_action(action_name: String) -> void:
	var character_c := _get_character_c()
	if character_c and character_c.has_method("perform_action"):
		character_c.perform_action(action_name)

func _find_camera() -> Camera3D:
	return view_anchor_resolver.find_camera(player)

func _get_player_action(property_name: StringName, fallback: StringName) -> StringName:
	if player and player.has_method("get_action_binding"):
		var value: Variant = player.get_action_binding(property_name, fallback)
		if value is StringName:
			return value as StringName
		if value is String:
			return StringName(value)
	return fallback
