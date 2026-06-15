extends Node3D

const CharacterActorSchemaRef = preload("res://scripts/character/CharacterActorSchema.gd")
const CharacterLocomotionExecutionModeRef = preload("res://scripts/character/CharacterLocomotionExecutionMode.gd")
const CharacterPresentationInputRef = preload("res://scripts/character/CharacterPresentationInput.gd")

enum LocomotionState {
	IDLE,
	WALK,
	ATTEND,
}

enum DriverMode {
	AI,
	PLAYER,
}

@export var actor_id := "char_a"
@export var patrol_enabled := true
@export var patrol_points: Array[Vector3] = [Vector3.ZERO]
@export var move_speed := 0.55
@export var move_accel := 2.8
@export var move_decel := 3.2
@export var hold_duration := 1.1
@export var patrol_wait_duration := 0.45
@export var turn_speed := 4.5
@export var sway_amount := 0.035
@export var sway_speed := 2.4
@export var dialogue_lean_amount := 0.14
@export var attention_recoil_amount := 0.18
@export var posture_recover_speed := 5.0
@export var driver_mode := DriverMode.AI
@export var player_shell_visual_offset := Vector3(0.0, 0.0, 0.0)
@export var reacts_to_player_focus := false
@export var idle_role_state := "idle"
@export var dialogue_role_state := "speak"
@export var attention_role_state := "alert"
@export var focus_role_state := "observe"
@export var interaction_role_state := "inspect"
@export_node_path("Node") var role_state_fact_emitter_path := NodePath("RoleStateFactEmitter")
@export_node_path("Node") var physiology_state_fact_emitter_path := NodePath("PhysiologyStateFactEmitter")
@export var player_walk_speed_threshold := 0.08
@export var player_run_speed_threshold := 6.4
@export var use_root_motion_patrol := true
@export var embodied_interaction_distance := 3.0

const CHARACTER_ACTOR_STATUS_ACCEPTED := "accepted_by_actor_adapter"
const CHARACTER_ACTOR_STATUS_RECOVERING_APPROACH := "recovering_approach"
const CHARACTER_ACTOR_STATUS_RECOVERING_TURN := "recovering_turn"
const CHARACTER_ACTOR_STATUS_TARGET_NOT_VISIBLE := "embodied_target_not_visible"
const CHARACTER_ACTOR_STATUS_OUT_OF_RANGE := "embodied_out_of_range"
const CHARACTER_ACTOR_STATUS_SUBMITTED_TO_AUTHORITY := "submitted_to_authority"
const CHARACTER_ACTOR_STATUS_FAILED := "failed"
const CHARACTER_ACTOR_FAILURE_TARGET_NOT_VISIBLE := "target_not_visible"
const CHARACTER_ACTOR_FAILURE_TARGET_OUT_OF_RANGE := "target_out_of_range"
const CHARACTER_ACTOR_FAILURE_TARGET_UNREACHABLE := "target_unreachable"
const CHARACTER_ACTOR_FAILURE_TARGET_NOT_PERCEIVED := "target_not_perceived"

@onready var visual_root: Node3D = $VisualRoot
@onready var role_asset_root: Node3D = $VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot
@onready var role_asset_scene: Node = $VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/KnightRoleSkin
@onready var runtime_feedback: Node = $CharacterRuntimeFeedback

var home_position := Vector3.ZERO
var locomotion_state: int = LocomotionState.IDLE
var hold_timer := 0.0
var sway_time := 0.0
var current_look_target := Vector3.ZERO
var has_look_target := false
var patrol_index := 0
var current_velocity := Vector3.ZERO
var posture_offset := Vector3.ZERO
var posture_target := Vector3.ZERO
var external_move_target := Vector3.ZERO
var has_external_move_target := false
var external_look_target := Vector3.ZERO
var has_external_look_target := false
var requested_action := ""
var action_override_state := ""
var action_override_timer := 0.0
var player_shell_velocity := Vector3.ZERO
var player_shell_grounded := true
var player_shell_active := false
var player_motion_state: Dictionary = {}
var player_presentation_input: Dictionary = {}
var player_control_move_direction := Vector3.ZERO
var player_control_wants_run := false
var player_stance := "stand"
var player_gait := "walk"
var player_jump_type := "none"
var focus_attention_timer := 0.0
var focus_attention_visual_timer := 0.0
var focus_attention_posture_timer := 0.0
var runtime_focus_target := ""
var runtime_attention_source := ""
var runtime_nearby_actor_refs: Array[String] = []
var runtime_nearby_object_refs: Array[String] = []
var runtime_nearby_environment_refs: Array[String] = []
var runtime_conversation_candidate_refs: Array[String] = []
var runtime_engagement_pressure := ""
var runtime_privacy_risk_hint := ""
var last_root_motion_world_delta := Vector3.ZERO
var last_locomotion_status_signature := ""
var last_role_state_fact := ""
var last_physiology_state_fact := ""
var active_command_type := ""
var active_command_priority := 0

func _ready() -> void:
	home_position = global_position
	current_look_target = global_position - global_basis.z
	_apply_asset_mode()
	_normalize_patrol_points()
	_apply_visual_config()
	_tick_runtime_feedback(0.0)
	var bus := _get_bus()
	if bus:
		bus.dialogue_received.connect(_on_dialogue_received)
		bus.siming_output_received.connect(_on_siming_output_received)
		if bus.has_signal("character_agent_output_received"):
			bus.character_agent_output_received.connect(_on_character_agent_output_received)
		if bus.has_signal("focus_state_received"):
			bus.focus_state_received.connect(_on_focus_state_received)
		if bus.has_signal("character_runtime_state_delta_received"):
			bus.character_runtime_state_delta_received.connect(_on_character_runtime_state_delta_received)
		if bus.has_signal("character_runtime_state_snapshot_received"):
			bus.character_runtime_state_snapshot_received.connect(_on_character_runtime_state_snapshot_received)

func _process(delta: float) -> void:
	sway_time += delta * sway_speed
	_update_action_override(delta)
	_apply_idle_sway()
	_update_posture(delta)
	_tick_runtime_feedback(delta)
	_update_hold(delta)
	_update_rotation(delta)
	_update_movement(delta)
	_emit_locomotion_status_if_changed()

func set_driver_mode(next_mode: int) -> void:
	driver_mode = next_mode

func set_move_target(target: Vector3) -> void:
	external_move_target = Vector3(target.x, global_position.y, target.z)
	has_external_move_target = true

func clear_move_target() -> void:
	has_external_move_target = false
	external_move_target = Vector3.ZERO

func set_look_target(target: Vector3) -> void:
	external_look_target = target
	has_external_look_target = true

func clear_look_target() -> void:
	has_external_look_target = false
	external_look_target = Vector3.ZERO

func perform_action(action_name: String) -> void:
	requested_action = action_name
	match action_name:
		"sword_swing":
			if runtime_feedback and runtime_feedback.has_method("show_combat_feedback"):
				runtime_feedback.show_combat_feedback("SWING")
			_tick_runtime_feedback(0.0)
		"shield_block":
			if runtime_feedback and runtime_feedback.has_method("show_combat_feedback"):
				runtime_feedback.show_combat_feedback("BLOCK")
			_tick_runtime_feedback(0.0)
	var next_state := _map_requested_action_to_role_state(action_name)
	if next_state.is_empty():
		return
	_trigger_role_state(next_state, _role_action_duration_for(action_name))

func begin_player_control_frame(world_position: Vector3, move_direction: Vector3, look_target: Vector3, is_grounded: bool, wants_run: bool, gait_name: String, stance_name: String, jump_type: String) -> void:
	driver_mode = DriverMode.PLAYER
	player_shell_active = true
	player_shell_grounded = is_grounded
	player_control_move_direction = Vector3(move_direction.x, 0.0, move_direction.z)
	player_control_wants_run = wants_run
	player_gait = gait_name
	player_stance = stance_name
	player_jump_type = jump_type
	if player_stance == "crouch":
		posture_target = Vector3(0.0, -0.22, 0.02)
	elif hold_timer <= 0.0 and focus_attention_posture_timer <= 0.0:
		posture_target = Vector3.ZERO
	if global_position.distance_to(world_position + player_shell_visual_offset) > 1.0:
		global_position = Vector3(world_position.x, world_position.y, world_position.z) + player_shell_visual_offset
	set_look_target(look_target)

func consume_player_root_motion_request(delta: float) -> Vector3:
	if not player_shell_active:
		return Vector3.ZERO
	if not player_shell_grounded:
		locomotion_state = LocomotionState.ATTEND
		if player_jump_type != "none":
			_set_role_asset_motion_profile("jump", "jump_single_leg" if player_jump_type == "single_leg" else "jump_two_foot")
		if player_jump_type != "none":
			_trigger_role_state("jump", 0.24 if player_jump_type == "single_leg" else 0.32)
			_emit_physiology_state_fact("elevated")
		last_root_motion_world_delta = Vector3.ZERO
		return Vector3.ZERO
	_emit_physiology_state_fact("stable")

	var move_direction: Vector3 = Vector3(player_control_move_direction.x, 0.0, player_control_move_direction.z)
	if move_direction.length() <= 0.001:
		_flush_role_root_motion()
		locomotion_state = LocomotionState.IDLE
		last_root_motion_world_delta = Vector3.ZERO
		if player_stance == "crouch":
			_set_role_asset_motion_profile_if_free(idle_role_state, "crouch_idle")
		else:
			_set_role_asset_motion_profile_if_free(idle_role_state, "default")
		return Vector3.ZERO

	move_direction = move_direction.normalized()
	current_look_target = global_position + move_direction
	has_look_target = true
	locomotion_state = LocomotionState.WALK
	if player_stance != "crouch":
		posture_target = Vector3.ZERO
	if player_stance == "crouch":
		_set_role_asset_motion_profile_if_free("walk", "crouch_walk")
	else:
		_apply_player_locomotion_profile()

	var root_motion_step: Vector3 = _consume_role_root_motion_world_delta()
	if root_motion_step.length() <= 0.0001:
		last_root_motion_world_delta = Vector3.ZERO
		return Vector3.ZERO

	var motion_amount: float = abs(root_motion_step.dot(move_direction))
	if motion_amount <= 0.0001:
		motion_amount = root_motion_step.length()
	if motion_amount <= 0.0001:
		last_root_motion_world_delta = Vector3.ZERO
		return Vector3.ZERO

	var requested_step: Vector3 = move_direction * motion_amount
	current_velocity = requested_step / max(delta, 0.0001)
	last_root_motion_world_delta = requested_step
	_bus_log("player_root_motion_step:%s" % actor_id)
	return requested_step

func apply_player_shell_pose(world_position: Vector3, planar_velocity: Vector3, look_target: Vector3, is_grounded: bool) -> void:
	driver_mode = DriverMode.PLAYER
	player_shell_active = true
	player_motion_state = _normalize_motion_state(_resolve_player_motion_state(planar_velocity, is_grounded))
	var velocity_world_value: Variant = player_motion_state.get("velocity_world", planar_velocity)
	var velocity_world: Vector3 = velocity_world_value if velocity_world_value is Vector3 else planar_velocity
	player_shell_velocity = Vector3(velocity_world.x, 0.0, velocity_world.z)
	player_shell_grounded = bool(player_motion_state.get("grounded", is_grounded))
	player_gait = str(player_motion_state.get("gait_actual", player_gait))
	global_position = Vector3(world_position.x, world_position.y, world_position.z) + player_shell_visual_offset
	set_look_target(look_target)
	player_presentation_input = _normalize_presentation_input(_build_player_presentation_input())
	_push_player_presentation_input()
	_update_player_shell_locomotion()

func apply_player_shell_frame(world_position: Vector3, planar_velocity: Vector3, look_target: Vector3, is_grounded: bool) -> void:
	apply_player_shell_pose(world_position, planar_velocity, look_target, is_grounded)

func clear_player_shell_frame() -> void:
	player_shell_active = false
	driver_mode = DriverMode.AI
	player_shell_velocity = Vector3.ZERO
	player_shell_grounded = true
	player_motion_state = {}
	player_presentation_input = {}
	player_control_move_direction = Vector3.ZERO
	player_control_wants_run = false
	player_stance = "stand"
	player_gait = "walk"
	player_jump_type = "none"
	current_velocity = Vector3.ZERO
	action_override_state = ""
	action_override_timer = 0.0
	last_root_motion_world_delta = Vector3.ZERO
	last_locomotion_status_signature = ""
	clear_move_target()
	clear_look_target()
	if locomotion_state == LocomotionState.WALK or locomotion_state == LocomotionState.ATTEND:
		locomotion_state = LocomotionState.IDLE
		_set_role_asset_state(idle_role_state)

func is_player_shell_active() -> bool:
	return player_shell_active

func get_role_anchor_position() -> Vector3:
	return global_position

func get_visual_forward() -> Vector3:
	if role_asset_scene is Node3D:
		return -((role_asset_scene as Node3D).global_basis.z).normalized()
	return -(global_basis.z).normalized()

func apply_dialogue(payload: Dictionary) -> void:
	var voice := get_node_or_null("SpatialVoiceController")
	if voice:
		voice.play_stub_voice(payload)
	_pause_and_face(_resolve_player_position())
	_set_dialogue_pose()
	_trigger_role_state(dialogue_role_state, hold_duration)
	_bus_log("dialogue_applied:%s" % actor_id)

func apply_attention(payload: Dictionary) -> void:
	var target_position := _resolve_attention_target(payload)
	_pause_and_face(target_position)
	_set_attention_pose()
	_trigger_role_state(attention_role_state, hold_duration)
	var target_environment_raw: Variant = payload.get("target_environment_id", null)
	if target_environment_raw != null and str(target_environment_raw) != "":
		var target_environment_id := str(target_environment_raw)
		_bus_log("attention_target_environment:%s:%s" % [actor_id, target_environment_id])
	_bus_log("attention_applied:%s" % actor_id)

func _on_dialogue_received(payload: Dictionary) -> void:
	if payload.get("actor_id", "") == actor_id:
		apply_dialogue(payload)

func _on_siming_output_received(payload: Dictionary) -> void:
	if payload.get("target_actor_id", "") == actor_id:
		apply_attention(payload)

func _on_character_agent_output_received(payload: Dictionary) -> void:
	if str(payload.get("actor_id", "")) != actor_id:
		return

	var next_command_type := str(payload.get("command_type", "") or "")
	if not _can_interrupt_current_action(next_command_type):
		_emit_character_actor_status(CHARACTER_ACTOR_STATUS_FAILED, payload, "interrupted_by_higher_priority")
		return
	active_command_type = next_command_type
	active_command_priority = _command_priority(next_command_type)
	_emit_character_actor_status(CHARACTER_ACTOR_STATUS_ACCEPTED, payload)

	match next_command_type:
		"look_at", "observe":
			_emit_character_actor_status(CHARACTER_ACTOR_STATUS_RECOVERING_TURN, payload)
			apply_attention(payload)
		"go_to", "approach":
			var target_position := _command_target_position(payload)
			set_move_target(target_position)
			set_look_target(target_position)
			_emit_character_actor_status(CHARACTER_ACTOR_STATUS_RECOVERING_APPROACH, payload)
		"interact":
			_handle_interact_goal_command(payload)
		"speak":
			_apply_embodied_speak(payload)
		_:
			return

	var role_state := str(payload.get("role_state_hint", "") or "")
	if not role_state.is_empty():
		_trigger_role_state(role_state, hold_duration)

	var physiology_hint := str(payload.get("physiology_hint", "") or "")
	if not physiology_hint.is_empty():
		_emit_physiology_state_fact(physiology_hint)
	if next_command_type == "interact":
		return
	if next_command_type == "speak":
		return
	_clear_completed_command()

func _handle_interact_goal_command(payload: Dictionary) -> void:
	# Agent target_id is a request, not authority.
	var target_node := _command_target_node(payload)
	var failure_reason := _resolve_embodied_target_failure_reason(payload, target_node)
	if failure_reason == CHARACTER_ACTOR_FAILURE_TARGET_OUT_OF_RANGE and target_node != null:
		set_move_target(target_node.global_position)
		set_look_target(target_node.global_position)
		_emit_character_actor_status(CHARACTER_ACTOR_STATUS_RECOVERING_APPROACH, payload, failure_reason)
		return
	if failure_reason == CHARACTER_ACTOR_FAILURE_TARGET_NOT_VISIBLE and target_node != null:
		set_look_target(target_node.global_position)
		_emit_character_actor_status(CHARACTER_ACTOR_STATUS_TARGET_NOT_VISIBLE, payload, failure_reason)
		_emit_character_actor_status(CHARACTER_ACTOR_STATUS_RECOVERING_TURN, payload, failure_reason)
		return
	if not failure_reason.is_empty():
		_emit_character_actor_status(CHARACTER_ACTOR_STATUS_FAILED, payload, failure_reason)
		return
	var interact_target := _command_target_position(payload)
	set_look_target(interact_target)
	perform_action("interact")
	_emit_character_actor_status(CHARACTER_ACTOR_STATUS_SUBMITTED_TO_AUTHORITY, payload)
	_clear_completed_command()

func _apply_embodied_speak(payload: Dictionary) -> void:
	# CharacterAgent / DialogueService owns text; CharacterActor only embodies it.
	_emit_character_actor_status(CHARACTER_ACTOR_STATUS_RECOVERING_TURN, payload)
	apply_dialogue(
		{
			"actor_id": actor_id,
			"content": str(payload.get("dialogue_text", "") or ""),
			"target_actor_id": str(payload.get("target_actor_id", "") or ""),
		}
	)
	_clear_completed_command()

func _command_priority(command_type: String) -> int:
	match command_type:
		"interact":
			return 5
		"speak":
			return 4
		"observe", "look_at":
			return 3
		"approach", "go_to":
			return 2
		"idle":
			return 1
		_:
			return 0

func _can_interrupt_current_action(next_command_type: String) -> bool:
	if active_command_type.is_empty():
		return true
	return _command_priority(next_command_type) >= active_command_priority

func _clear_completed_command() -> void:
	active_command_type = ""
	active_command_priority = 0

func _emit_character_actor_status(status: String, command_payload: Dictionary, failure_reason: String = "") -> void:
	var payload := {
		"actor_id": actor_id,
		"command_status": status,
		"command_type": str(command_payload.get("command_type", "") or ""),
		"target_actor_id": str(command_payload.get("target_actor_id", "") or ""),
		"target_object_id": str(command_payload.get("target_object_id", "") or ""),
		"target_environment_id": str(command_payload.get("target_environment_id", "") or ""),
		"failure_reason": failure_reason,
		"causation_id": str(command_payload.get("causation_id", "") or ""),
		"correlation_id": str(command_payload.get("correlation_id", "") or ""),
	}
	var bus := _get_bus()
	if bus and bus.has_signal("character_actor_status_emitted"):
		bus.emit_signal("character_actor_status_emitted", payload)
	_bus_log("character_actor_status:%s:%s:%s" % [actor_id, status, failure_reason])

func _resolve_embodied_target_failure_reason(payload: Dictionary, target_node: Node3D) -> String:
	if target_node == null:
		return CHARACTER_ACTOR_FAILURE_TARGET_NOT_PERCEIVED
	if global_position.distance_to(target_node.global_position) > embodied_interaction_distance:
		return CHARACTER_ACTOR_FAILURE_TARGET_OUT_OF_RANGE
	if not _has_line_of_sight_to_target(target_node):
		return CHARACTER_ACTOR_FAILURE_TARGET_NOT_VISIBLE
	if not _is_target_reachable(target_node):
		return CHARACTER_ACTOR_FAILURE_TARGET_UNREACHABLE
	return ""

func _has_line_of_sight_to_target(target_node: Node3D) -> bool:
	if target_node == null or not target_node.is_inside_tree():
		return false
	if not is_inside_tree() or get_world_3d() == null:
		return false
	var from_position := global_position + Vector3.UP * 1.4
	var to_position := target_node.global_position + Vector3.UP * 0.8
	var query := PhysicsRayQueryParameters3D.create(from_position, to_position)
	query.exclude = [self]
	var hit := get_world_3d().direct_space_state.intersect_ray(query)
	if hit.is_empty():
		return true
	var collider: Variant = hit.get("collider", null)
	if collider == target_node:
		return true
	if collider is Node:
		return target_node.is_ancestor_of(collider as Node)
	return false

func _is_target_reachable(target_node: Node3D) -> bool:
	if target_node == null or not target_node.is_inside_tree():
		return false
	return global_position.distance_to(target_node.global_position) <= embodied_interaction_distance

func _on_focus_state_received(payload: Dictionary) -> void:
	if not reacts_to_player_focus:
		return
	if str(payload.get("actor_id", "")) != "char_c":
		return
	if str(payload.get("target_actor_id", "")) != actor_id:
		return

	_bus_log("focus_state_applied:%s" % actor_id)
	_focus_on_player_attention()

func _on_character_runtime_state_snapshot_received(payload: Dictionary) -> void:
	if str(payload.get("actor_id", "")) != actor_id:
		return
	_apply_runtime_state_payload(payload)

func _on_character_runtime_state_delta_received(payload: Dictionary) -> void:
	if str(payload.get("actor_id", "")) != actor_id:
		return
	_apply_runtime_state_payload(payload)

func _get_bus() -> Node:
	return get_node_or_null("/root/LocalPresentationBus")

func _get_bridge() -> Node:
	return get_node_or_null("/root/BackendBridge")

func _is_backend_open() -> bool:
	var bridge := _get_bridge()
	if bridge == null:
		return false
	if bridge.has_method("is_backend_open"):
		return bool(bridge.is_backend_open())
	return false

func _bus_log(message: String) -> void:
	var bus := _get_bus()
	if bus and bus.has_method("log_debug"):
		bus.log_debug(message)

func _get_role_state_fact_emitter() -> Node:
	return get_node_or_null(role_state_fact_emitter_path)

func _emit_role_state_fact(next_state: String) -> void:
	if next_state.is_empty() or next_state == last_role_state_fact:
		return
	if not _is_backend_open():
		return
	var role_state_fact_emitter := _get_role_state_fact_emitter()
	if role_state_fact_emitter == null:
		return
	if role_state_fact_emitter.get("actor_id") != actor_id:
		role_state_fact_emitter.set("actor_id", actor_id)
	if not role_state_fact_emitter.has_method("emit_role_state_transition"):
		return
	var emitted: Variant = role_state_fact_emitter.emit_role_state_transition(next_state)
	if bool(emitted):
		last_role_state_fact = next_state

func _get_physiology_state_fact_emitter() -> Node:
	return get_node_or_null(physiology_state_fact_emitter_path)

func _emit_physiology_state_fact(strain_band: String) -> void:
	if strain_band.is_empty() or strain_band == last_physiology_state_fact:
		return
	if not _is_backend_open():
		return
	var physiology_state_fact_emitter := _get_physiology_state_fact_emitter()
	if physiology_state_fact_emitter == null:
		return
	if physiology_state_fact_emitter.get("actor_id") != actor_id:
		physiology_state_fact_emitter.set("actor_id", actor_id)
	if not physiology_state_fact_emitter.has_method("emit_breathing_strain_fact"):
		return
	var emitted: Variant = physiology_state_fact_emitter.emit_breathing_strain_fact(strain_band)
	if bool(emitted):
		last_physiology_state_fact = strain_band

func set_focus_highlight(is_focused: bool) -> void:
	var environment_attention := runtime_nearby_environment_refs.size() > 0 and runtime_attention_source == "visual_fact"
	var highlighted := is_focused or focus_attention_visual_timer > 0.0 or runtime_attention_source == "focus_state" or runtime_attention_source == "visual_fact" or environment_attention
	_set_role_asset_focus(highlighted)
	_tick_runtime_feedback(0.0)

func _apply_idle_sway() -> void:
	if visual_root:
		var offset_y := sin(sway_time) * sway_amount
		visual_root.position = Vector3(posture_offset.x, offset_y + posture_offset.y, posture_offset.z)

func _update_posture(delta: float) -> void:
	posture_offset = posture_offset.lerp(posture_target, clamp(posture_recover_speed * delta, 0.0, 1.0))
	if focus_attention_visual_timer > 0.0:
		focus_attention_visual_timer = max(focus_attention_visual_timer - delta, 0.0)
		set_focus_highlight(false)
	if focus_attention_posture_timer > 0.0:
		focus_attention_posture_timer = max(focus_attention_posture_timer - delta, 0.0)

	if hold_timer <= 0.0 and focus_attention_posture_timer <= 0.0 and posture_target.length() > 0.001:
		posture_target = Vector3.ZERO

func _update_hold(delta: float) -> void:
	if hold_timer > 0.0:
		hold_timer = max(hold_timer - delta, 0.0)
		locomotion_state = LocomotionState.ATTEND
	elif locomotion_state == LocomotionState.ATTEND:
		if focus_attention_timer > 0.0:
			focus_attention_timer = max(focus_attention_timer - delta, 0.0)
		else:
			locomotion_state = LocomotionState.IDLE
			_set_role_asset_state_if_free(idle_role_state)

func _update_movement(delta: float) -> void:
	if driver_mode == DriverMode.PLAYER and player_shell_active:
		current_velocity = player_shell_velocity
		return

	if hold_timer > 0.0:
		_flush_role_root_motion()
		current_velocity = current_velocity.move_toward(Vector3.ZERO, move_decel * delta)
		return

	if has_external_move_target:
		_move_toward_target(external_move_target, delta, true)
		return

	if not patrol_enabled or patrol_points.size() <= 1:
		_flush_role_root_motion()
		current_velocity = current_velocity.move_toward(Vector3.ZERO, move_decel * delta)
		return

	var target: Vector3 = home_position + patrol_points[patrol_index]
	_move_toward_patrol_target(target, delta)

func _move_toward_patrol_target(target: Vector3, delta: float) -> void:
	var to_target: Vector3 = target - global_position
	to_target.y = 0.0
	if to_target.length() < 0.05:
		patrol_index = (patrol_index + 1) % patrol_points.size()
		locomotion_state = LocomotionState.IDLE
		hold_timer = max(hold_timer, patrol_wait_duration)
		current_velocity = current_velocity.move_toward(Vector3.ZERO, move_decel * delta)
		return

	_move_toward_target(target, delta, false)

func _move_toward_target(target: Vector3, delta: float, clear_on_arrival: bool) -> void:
	var to_target: Vector3 = target - global_position
	to_target.y = 0.0
	if to_target.length() < 0.05:
		if clear_on_arrival:
			clear_move_target()
		_flush_role_root_motion()
		locomotion_state = LocomotionState.IDLE
		current_velocity = current_velocity.move_toward(Vector3.ZERO, move_decel * delta)
		_set_role_asset_state_if_free(idle_role_state)
		return

	var move_direction: Vector3 = to_target.normalized()
	current_look_target = global_position + move_direction
	has_look_target = true
	locomotion_state = LocomotionState.WALK
	posture_target = Vector3.ZERO
	_set_role_asset_motion_profile_if_free("walk", "walk")
	var root_motion_step: Vector3 = _consume_role_root_motion_world_delta()
	if root_motion_step.length() > 0.0001:
		var motion_amount: float = abs(root_motion_step.dot(move_direction))
		if motion_amount <= 0.0001:
			motion_amount = root_motion_step.length()
		if motion_amount > 0.0001:
			var world_step: Vector3 = move_direction * motion_amount
			if world_step.length() > to_target.length():
				world_step = move_direction * to_target.length()
			global_position += world_step
			current_velocity = world_step / max(delta, 0.0001)
			last_root_motion_world_delta = world_step
			_bus_log("patrol_root_motion_step:%s" % actor_id)
			return

	current_velocity = current_velocity.move_toward(move_direction * move_speed, move_accel * delta)
	var step: Vector3 = current_velocity * delta
	if step.length() > to_target.length():
		step = move_direction * to_target.length()

	global_position += step
	last_root_motion_world_delta = step

func _update_player_shell_locomotion() -> void:
	var move_x := float(player_presentation_input.get("move_x", 0.0))
	var move_y := float(player_presentation_input.get("move_y", 0.0))
	var planar_speed := float(player_presentation_input.get("speed", player_shell_velocity.length()))
	var has_move_input: bool = abs(move_x) > 0.001 or abs(move_y) > 0.001
	if not player_shell_grounded:
		locomotion_state = LocomotionState.ATTEND
		if player_jump_type != "none":
			_set_role_asset_motion_profile("jump", "jump_single_leg" if player_jump_type == "single_leg" else "jump_two_foot")
		if player_jump_type != "none":
			_trigger_role_state("jump", 0.24 if player_jump_type == "single_leg" else 0.32)
			_emit_physiology_state_fact("elevated")
	elif player_stance == "crouch" and has_move_input:
		locomotion_state = LocomotionState.WALK
		_set_role_asset_motion_profile_if_free("walk", "crouch_walk")
	elif player_stance == "crouch":
		_flush_role_root_motion()
		locomotion_state = LocomotionState.IDLE
		_set_role_asset_motion_profile_if_free(idle_role_state, "crouch_idle")
	elif has_move_input:
		locomotion_state = LocomotionState.WALK
		posture_target = Vector3.ZERO
		_apply_player_locomotion_profile()
	elif planar_speed > player_run_speed_threshold:
		locomotion_state = LocomotionState.WALK
		posture_target = Vector3.ZERO
		_set_role_asset_motion_profile_if_free("run", "run")
	elif planar_speed > player_walk_speed_threshold:
		locomotion_state = LocomotionState.WALK
		posture_target = Vector3.ZERO
		_set_role_asset_motion_profile_if_free("walk", "walk")
	else:
		_flush_role_root_motion()
		locomotion_state = LocomotionState.IDLE
		_set_role_asset_motion_profile_if_free(idle_role_state, "default")
	if player_shell_grounded:
		_emit_physiology_state_fact("stable")

func _resolve_player_motion_state(planar_velocity: Vector3, is_grounded: bool) -> Dictionary:
	var parent_node := get_parent()
	if parent_node != null:
		var motion_state_value: Variant = parent_node.get("motion_state")
		if motion_state_value is Dictionary and not (motion_state_value as Dictionary).is_empty():
			return _normalize_motion_state((motion_state_value as Dictionary).duplicate(true))
	return {
		"position": global_position,
		"velocity_world": planar_velocity,
		"move_local_actual": Vector2.ZERO,
		"gait_actual": "run" if planar_velocity.length() > player_run_speed_threshold else "walk",
		"grounded": is_grounded,
	}

func _build_player_presentation_input() -> Dictionary:
	var move_local_value: Variant = player_motion_state.get("move_local_actual", Vector2.ZERO)
	var move_local: Vector2 = move_local_value if move_local_value is Vector2 else Vector2.ZERO
	var velocity_world_value: Variant = player_motion_state.get("velocity_world", player_shell_velocity)
	var velocity_world: Vector3 = velocity_world_value if velocity_world_value is Vector3 else player_shell_velocity
	var presentation_contract := CharacterPresentationInputRef.normalize(
		{
			"motion_state": player_motion_state.duplicate(true),
			"focus_state": {
				"target_id": runtime_focus_target,
			},
			"action_state": {
				"requested_action": requested_action,
				"override_state": action_override_state,
			},
			"equipment_state": {},
			"physiology_hint": last_physiology_state_fact,
			"speech_state": {
				"active_command_type": active_command_type,
			},
		}
	)
	presentation_contract["move_x"] = move_local.x
	presentation_contract["move_y"] = move_local.y
	presentation_contract["speed"] = velocity_world.length()
	presentation_contract["gait"] = str(player_motion_state.get("gait_actual", player_gait))
	return presentation_contract

func _push_player_presentation_input() -> void:
	if role_asset_scene and role_asset_scene.has_method("apply_presentation_input"):
		role_asset_scene.apply_presentation_input(player_presentation_input)

func _normalize_motion_state(candidate: Dictionary) -> Dictionary:
	return CharacterActorSchemaRef.normalize_motion_state(candidate)

func _normalize_presentation_input(candidate: Dictionary) -> Dictionary:
	var normalized := CharacterPresentationInputRef.normalize(candidate)
	normalized["move_x"] = float(candidate.get("move_x", 0.0))
	normalized["move_y"] = float(candidate.get("move_y", 0.0))
	normalized["speed"] = float(candidate.get("speed", 0.0))
	normalized["gait"] = str(candidate.get("gait", "walk"))
	return normalized

func _update_rotation(delta: float) -> void:
	if has_external_look_target:
		current_look_target = external_look_target
		has_look_target = true

	if not has_look_target:
		return

	var look_target: Vector3 = Vector3(current_look_target.x, global_position.y, current_look_target.z)
	if look_target.is_equal_approx(global_position):
		return

	var desired_basis: Basis = Basis.looking_at((look_target - global_position).normalized(), Vector3.UP)
	global_basis = global_basis.slerp(desired_basis, clamp(turn_speed * delta, 0.0, 1.0))

func _pause_and_face(target_position: Vector3) -> void:
	hold_timer = hold_duration
	current_look_target = target_position
	has_look_target = true
	current_velocity = Vector3.ZERO
	locomotion_state = LocomotionState.ATTEND

func _focus_on_player_attention() -> void:
	focus_attention_timer = max(focus_attention_timer, 0.7)
	focus_attention_visual_timer = max(focus_attention_visual_timer, 0.9)
	focus_attention_posture_timer = max(focus_attention_posture_timer, 0.9)
	current_look_target = _resolve_player_position()
	has_look_target = true
	current_velocity = Vector3.ZERO
	locomotion_state = LocomotionState.ATTEND
	posture_target = Vector3(0.0, attention_recoil_amount * 0.22, -dialogue_lean_amount * 0.55)
	set_focus_highlight(true)
	_trigger_role_state(focus_role_state, 0.9)
	_bus_log("focus_attention:%s" % actor_id)

func _apply_runtime_state_payload(payload: Dictionary) -> void:
	runtime_focus_target = _read_runtime_string(payload, "current_focus_target", runtime_focus_target)
	runtime_attention_source = _read_runtime_string(payload, "current_attention_source", runtime_attention_source)
	if payload.has("nearby_actor_refs"):
		runtime_nearby_actor_refs = _read_runtime_string_array(payload.get("nearby_actor_refs", []))
	if payload.has("nearby_object_refs"):
		runtime_nearby_object_refs = _read_runtime_string_array(payload.get("nearby_object_refs", []))
	if payload.has("nearby_environment_refs"):
		runtime_nearby_environment_refs = _read_runtime_string_array(payload.get("nearby_environment_refs", []))
	if payload.has("conversation_candidate_refs"):
		runtime_conversation_candidate_refs = _read_runtime_string_array(payload.get("conversation_candidate_refs", []))
	runtime_engagement_pressure = _read_runtime_string(payload, "engagement_pressure", runtime_engagement_pressure)
	runtime_privacy_risk_hint = _read_runtime_string(payload, "privacy_risk_hint", runtime_privacy_risk_hint)
	if actor_id == "char_c":
		_bus_log(
			"runtime_state_applied:%s:%s:%s" % [
				actor_id,
				runtime_focus_target,
				runtime_attention_source,
			]
		)

func _read_runtime_string(payload: Dictionary, key: String, current: String) -> String:
	if not payload.has(key):
		return current
	var value: Variant = payload.get(key)
	if value == null:
		return current
	return str(value)

func _read_runtime_string_array(value: Variant) -> Array[String]:
	var result: Array[String] = []
	if value is Array:
		for entry in value:
			if entry == null:
				continue
			result.append(str(entry))
	return result

func _tick_runtime_feedback(delta: float) -> void:
	if runtime_feedback == null or not runtime_feedback.has_method("tick"):
		return
	var source_visual_fact := runtime_attention_source == "visual_fact"
	var environment_attention := source_visual_fact and runtime_nearby_environment_refs.size() > 0
	var attention_active := focus_attention_visual_timer > 0.0 or runtime_conversation_candidate_refs.size() > 0 or source_visual_fact
	runtime_feedback.tick(delta, actor_id, attention_active, environment_attention, source_visual_fact, focus_attention_visual_timer > 0.0)

func _resolve_player_position() -> Vector3:
	var scene := get_tree().current_scene
	if scene:
		var character_c := scene.get_node_or_null("CharacterC")
		if character_c and character_c.has_method("is_player_shell_active") and character_c.is_player_shell_active():
			if character_c.has_method("get_role_anchor_position"):
				return character_c.get_role_anchor_position()
			if character_c is Node3D:
				return (character_c as Node3D).global_position
	var player := get_tree().get_root().find_child("Player", true, false)
	if player is Node3D:
		return (player as Node3D).global_position
	return global_position - global_basis.z

func _resolve_attention_target(payload: Dictionary) -> Vector3:
	var environment_raw: Variant = payload.get("target_environment_id", null)
	if environment_raw != null and str(environment_raw) != "":
		var environment_id := str(environment_raw)
		var environment_node := _find_node_by_property("environment_id", environment_id)
		if environment_node:
			return environment_node.global_position

	var object_id := str(payload.get("target_object_id", ""))
	if object_id != "":
		var object_node := _find_node_by_property("object_id", object_id)
		if object_node:
			return object_node.global_position

	var actor_target := str(payload.get("target_actor_id", ""))
	if actor_target != "":
		var actor_node := _find_node_by_property("actor_id", actor_target)
		if actor_node:
			return actor_node.global_position

	return _resolve_player_position()

func _command_target_position(payload: Dictionary) -> Vector3:
	var target_position_raw: Variant = payload.get("target_position", null)
	if target_position_raw is Array and target_position_raw.size() == 3:
		return Vector3(
			float(target_position_raw[0]),
			float(target_position_raw[1]),
			float(target_position_raw[2])
		)
	return _resolve_attention_target(payload)

func _command_target_node(payload: Dictionary) -> Node3D:
	var object_id := str(payload.get("target_object_id", "") or "")
	if not object_id.is_empty():
		return _find_node_by_property("object_id", object_id)
	var actor_target := str(payload.get("target_actor_id", "") or "")
	if not actor_target.is_empty():
		return _find_node_by_property("actor_id", actor_target)
	var environment_id := str(payload.get("target_environment_id", "") or "")
	if not environment_id.is_empty():
		return _find_node_by_property("environment_id", environment_id)
	return null

func _find_node_by_property(property_name: String, expected: String) -> Node3D:
	var scene := get_tree().current_scene
	if scene == null:
		return null
	return _find_node_by_property_recursive(scene, property_name, expected)

func _find_node_by_property_recursive(node: Node, property_name: String, expected: String) -> Node3D:
	if node is Node3D:
		var value: Variant = node.get(property_name)
		if value != null and str(value) == expected:
			return node as Node3D

	for child in node.get_children():
		var result: Node3D = _find_node_by_property_recursive(child, property_name, expected)
		if result:
			return result
	return null

func _normalize_patrol_points() -> void:
	if patrol_points.is_empty():
		patrol_points = [Vector3.ZERO]
		return

	var normalized: Array[Vector3] = []
	for point in patrol_points:
		normalized.append(Vector3(point.x, 0.0, point.z))
	patrol_points = normalized

func _apply_visual_config() -> void:
	_apply_role_asset_config()

func _set_dialogue_pose() -> void:
	posture_target = Vector3(0.0, 0.0, -dialogue_lean_amount)

func _set_attention_pose() -> void:
	posture_target = Vector3(0.0, attention_recoil_amount * 0.35, attention_recoil_amount)

func _apply_asset_mode() -> void:
	if role_asset_root:
		role_asset_root.visible = true
	if role_asset_scene is Node3D:
		(role_asset_scene as Node3D).visible = true

func _apply_role_asset_config() -> void:
	if role_asset_scene and role_asset_scene.has_method("configure_role"):
		role_asset_scene.configure_role(actor_id)
	_set_role_asset_motion_profile(idle_role_state, "default")
	_flush_role_root_motion()

func _set_role_asset_state(state_name: String) -> void:
	if role_asset_scene and role_asset_scene.has_method("set_state"):
		role_asset_scene.set_state(state_name)

func _set_role_asset_motion_profile(state_name: String, profile_name: String) -> void:
	if role_asset_scene and role_asset_scene.has_method("set_motion_profile"):
		role_asset_scene.set_motion_profile(state_name, profile_name)
		return
	_set_role_asset_state(state_name)

func _set_role_asset_focus(is_focused: bool) -> void:
	if role_asset_scene and role_asset_scene.has_method("set_focus_highlight"):
		role_asset_scene.set_focus_highlight(is_focused)
		return
	var plush_mesh := role_asset_scene.get_node_or_null("KnightScene/KnightArmature/Skeleton3D/head") if role_asset_scene else null
	if plush_mesh is MeshInstance3D:
		var mat := StandardMaterial3D.new()
		mat.albedo_color = Color(0.95, 0.85, 0.35, 1.0) if is_focused else Color(1.0, 1.0, 1.0, 1.0)
		(plush_mesh as MeshInstance3D).material_overlay = mat

func _update_action_override(delta: float) -> void:
	if action_override_timer <= 0.0:
		return
	action_override_timer = max(action_override_timer - delta, 0.0)
	if action_override_timer <= 0.0:
		action_override_state = ""

func _trigger_role_state(state_name: String, duration: float) -> void:
	if state_name.is_empty():
		return
	_emit_role_state_fact(state_name)
	action_override_state = state_name
	action_override_timer = max(duration, 0.05)
	_set_role_asset_motion_profile(state_name, "default")

func _set_role_asset_state_if_free(state_name: String) -> void:
	if _is_action_override_active():
		return
	_set_role_asset_state(state_name)

func _set_role_asset_motion_profile_if_free(state_name: String, profile_name: String) -> void:
	if _is_action_override_active():
		return
	_set_role_asset_motion_profile(state_name, profile_name)

func _is_action_override_active() -> bool:
	return not action_override_state.is_empty() and action_override_timer > 0.0

func _map_requested_action_to_role_state(action_name: String) -> String:
	match action_name:
		"dialogue", "talk", "speak":
			return dialogue_role_state
		"inspect", "interact":
			return interaction_role_state
		"observe", "focus":
			return focus_role_state
		"alert":
			return attention_role_state
		"jump":
			return "jump"
		"sword_swing":
			return "sword_swing"
		"shield_block":
			return "shield_block"
		_:
			return action_name

func _role_action_duration_for(action_name: String) -> float:
	match action_name:
		"dialogue", "talk", "speak":
			return 0.72
		"inspect", "interact":
			return 0.72
		"observe", "focus":
			return 0.9
		"alert":
			return 0.8
		"jump":
			return 0.32
		"sword_swing":
			return 0.48
		"shield_block":
			return 0.58
		_:
			return hold_duration

func _consume_role_root_motion_world_delta() -> Vector3:
	if not use_root_motion_patrol:
		return Vector3.ZERO
	if role_asset_scene == null or not role_asset_scene.has_method("consume_root_motion_delta"):
		return Vector3.ZERO
	var local_delta: Variant = role_asset_scene.consume_root_motion_delta()
	if not (local_delta is Vector3):
		return Vector3.ZERO
	var local_motion := local_delta as Vector3
	local_motion.y = 0.0
	if local_motion.length() <= 0.0001:
		return Vector3.ZERO
	var world_motion := global_basis * local_motion
	world_motion.y = 0.0
	return world_motion

func _flush_role_root_motion() -> void:
	if role_asset_scene and role_asset_scene.has_method("reset_root_motion"):
		role_asset_scene.reset_root_motion()

func get_locomotion_status() -> Dictionary:
	return {
		"execution_mode": CharacterLocomotionExecutionModeRef.PHYSICS,
		"stance": player_stance,
		"gait": player_gait,
		"jump_type": player_jump_type,
		"clip": _get_current_role_clip_name(),
		"profile": _get_current_role_profile_name(),
		"root_motion_active": last_root_motion_world_delta.length() > 0.0001,
	}

func _emit_locomotion_status_if_changed() -> void:
	if actor_id != "char_c":
		return
	var status := get_locomotion_status()
	var signature := "%s|%s|%s|%s|%s|%s" % [
		status["stance"],
		status["gait"],
		status["jump_type"],
		status["clip"],
		status["profile"],
		status["root_motion_active"],
	]
	if signature == last_locomotion_status_signature:
		return
	last_locomotion_status_signature = signature
	_bus_log(
		"locomotion_state:stance=%s gait=%s jump=%s clip=%s profile=%s rm=%s" % [
			status["stance"],
			status["gait"],
			status["jump_type"],
			status["clip"],
			status["profile"],
			"active" if status["root_motion_active"] else "inactive",
		]
	)

func _apply_player_locomotion_profile() -> void:
	match player_gait:
		"amble":
			_set_role_asset_motion_profile_if_free("walk", "amble")
		"brisk_walk":
			_set_role_asset_motion_profile_if_free("walk", "brisk_walk")
		"run":
			_set_role_asset_motion_profile_if_free("run", "run")
		_:
			_set_role_asset_motion_profile_if_free("walk", "walk")

func _get_current_role_clip_name() -> String:
	if role_asset_scene and role_asset_scene.has_method("get_current_clip_name"):
		return str(role_asset_scene.get_current_clip_name())
	return ""

func _get_current_role_profile_name() -> String:
	if role_asset_scene and role_asset_scene.has_method("get_current_motion_profile_name"):
		return str(role_asset_scene.get_current_motion_profile_name())
	return "default"
