extends Node3D

const ActorPerceptionSamplerRef = preload("res://scripts/character/ActorPerceptionSampler.gd")
const ActorPerceptionTargetResolverRef = preload("res://scripts/character/ActorPerceptionTargetResolver.gd")
const CharacterActorSchemaRef = preload("res://scripts/character/CharacterActorSchema.gd")
const CharacterLocomotionExecutionModeRef = preload("res://scripts/character/CharacterLocomotionExecutionMode.gd")
const CharacterRuntimeStateRef = preload("res://scripts/character/CharacterRuntimeState.gd")

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
@export var perception_range_m := 28.0
@export var perception_forward_threshold := 0.2
@export var actor_notice_cooldown_ms := 650
@export var actor_arrival_distance := 18.0
@export var idle_role_state := "idle"
@export var dialogue_role_state := "speak"
@export var attention_role_state := "alert"
@export var focus_role_state := "observe"
@export var interaction_role_state := "inspect"
@export_node_path("Node") var character_visual_fact_emitter_path := NodePath("VisualFactEmitter/CharacterVisualFactEmitter")
@export_node_path("Node") var spatial_access_fact_emitter_path := NodePath("VisualFactEmitter/SpatialAccessFactEmitter")
@export_node_path("Node") var role_state_fact_emitter_path := NodePath("RoleStateFactEmitter")
@export_node_path("Node") var physiology_state_fact_emitter_path := NodePath("PhysiologyStateFactEmitter")
@export_node_path("Node") var role_asset_scene_path := NodePath("VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/KnightRoleSkin")
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
const FOCUS_ANCHOR_LOCAL_OFFSET := Vector3(0.0, 1.55, 0.0)

@onready var visual_root: Node3D = $VisualRoot
@onready var role_asset_root: Node3D = $VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot
@onready var role_asset_scene: Node = _resolve_role_asset_scene()
@onready var runtime_feedback: Node = $CharacterRuntimeFeedback
@onready var perception_cone_debug: MeshInstance3D = $PerceptionConeDebug
# Keep runtime_state constructed via the host ref rather than a typed onready binding.
@onready var runtime_state = CharacterRuntimeStateRef.new()

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
var action_override_state := ""
var action_override_timer := 0.0
var player_shell_active := false
var player_control_move_direction := Vector3.ZERO
var player_control_wants_run := false
var focus_attention_timer := 0.0
var focus_attention_visual_timer := 0.0
var focus_attention_posture_timer := 0.0
var last_root_motion_world_delta := Vector3.ZERO
var last_locomotion_status_signature := ""
var last_role_state_fact := ""
var last_player_root_motion_log_ms := 0
var last_patrol_root_motion_log_ms := 0
var _perception_sampler = ActorPerceptionSamplerRef.new()
var _perception_target_resolver = ActorPerceptionTargetResolverRef.new()
var _last_notice_target := ""
var _last_notice_ts := 0
var _active_contact_target_actor_id := ""
var actor_local_perception_enabled := true
var _fallback_role_asset_scene: Node
var _manifest_role_asset_scene: Node

const ROOT_MOTION_LOG_COOLDOWN_MS := 250

func _ready() -> void:
	home_position = global_position
	current_look_target = global_position - global_basis.z
	_fallback_role_asset_scene = role_asset_scene
	if perception_cone_debug:
		perception_cone_debug.position = FOCUS_ANCHOR_LOCAL_OFFSET
	_configure_actor_local_perception()
	_configure_actor_local_emitters()
	_apply_asset_mode()
	_normalize_patrol_points()
	_apply_visual_config()
	_tick_runtime_feedback(0.0)
	var bus := _get_bus()
	if bus:
		bus.dialogue_received.connect(_on_dialogue_received)
		bus.siming_output_received.connect(_on_siming_output_received)
		if bus.has_signal("character_agent_execution_received"):
			bus.character_agent_execution_received.connect(_on_character_agent_execution_received)
		if bus.has_signal("focus_state_received"):
			bus.focus_state_received.connect(_on_focus_state_received)
		if bus.has_signal("character_runtime_state_delta_received"):
			bus.character_runtime_state_delta_received.connect(_on_character_runtime_state_delta_received)
		if bus.has_signal("character_runtime_state_snapshot_received"):
			bus.character_runtime_state_snapshot_received.connect(_on_character_runtime_state_snapshot_received)

func _resolve_role_asset_scene() -> Node:
	var configured := get_node_or_null(role_asset_scene_path)
	if configured != null:
		return configured
	if role_asset_root == null:
		return null
	var legacy_skin := role_asset_root.get_node_or_null("KnightRoleSkin")
	if legacy_skin != null:
		return legacy_skin
	for child in role_asset_root.get_children():
		if child is Node:
			return child as Node
	return null

func _process(delta: float) -> void:
	sway_time += delta * sway_speed
	_update_action_override(delta)
	_apply_idle_sway()
	_update_posture(delta)
	_tick_runtime_feedback(delta)
	_sample_actor_local_perception()
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
	_active_contact_target_actor_id = ""

func set_look_target(target: Vector3) -> void:
	external_look_target = target
	has_external_look_target = true

func clear_look_target() -> void:
	has_external_look_target = false
	external_look_target = Vector3.ZERO

func set_visual_shell_visible(is_visible: bool) -> void:
	if visual_root:
		visual_root.visible = is_visible

func set_perception_debug_visible(is_visible: bool) -> void:
	if perception_cone_debug and perception_cone_debug.has_method("set_debug_visible"):
		perception_cone_debug.set_debug_visible(is_visible)

func configure_perception_debug(range_m: float, half_fov_degrees: float) -> void:
	if perception_cone_debug and perception_cone_debug.has_method("set_parameters"):
		perception_cone_debug.set_parameters(range_m, half_fov_degrees)

func get_focus_anchor_position() -> Vector3:
	return global_position + FOCUS_ANCHOR_LOCAL_OFFSET

func perform_action(action_name: String) -> void:
	runtime_state.set_requested_action(action_name)
	match action_name:
		"sword_swing":
			if runtime_feedback and runtime_feedback.has_method("show_combat_feedback"):
				runtime_feedback.show_combat_feedback("SWING")
			_tick_runtime_feedback(0.0)
		"shield_block":
			if runtime_feedback and runtime_feedback.has_method("show_combat_feedback"):
				runtime_feedback.show_combat_feedback("BLOCK")
			_tick_runtime_feedback(0.0)
	var next_state: String = runtime_state.map_requested_action_to_role_state(
		action_name,
		dialogue_role_state,
		interaction_role_state,
		focus_role_state,
		attention_role_state,
	)
	if next_state.is_empty():
		return
	_trigger_role_state(next_state, _role_action_duration_for(action_name))


func play_reviewed_action_atom(action_tag: String, animation_clip_ref: String, phase: String) -> Dictionary:
	if role_asset_scene == null or not role_asset_scene.has_method("play_reviewed_action_atom"):
		return {"accepted": false, "played_clip": ""}
	var result: Variant = role_asset_scene.call("play_reviewed_action_atom", action_tag, animation_clip_ref, phase)
	return result if result is Dictionary else {"accepted": false, "played_clip": ""}


func restore_reviewed_action_playback() -> void:
	if role_asset_scene != null and role_asset_scene.has_method("restore_reviewed_action_playback"):
		role_asset_scene.call("restore_reviewed_action_playback")


func begin_right_hand_reach(anchor_world_position: Vector3, tolerance_m: float) -> Dictionary:
	if role_asset_scene == null or not role_asset_scene.has_method("begin_right_hand_reach"):
		return {"available": false, "distance_m": INF, "error_code": "ik_chain_unavailable"}
	var result: Variant = role_asset_scene.call("begin_right_hand_reach", anchor_world_position, tolerance_m)
	return result if result is Dictionary else {"available": false, "distance_m": INF, "error_code": "ik_chain_unavailable"}


func begin_right_hand_modifier_reach(anchor_world_position: Vector3, tolerance_m: float) -> Dictionary:
	if role_asset_scene == null or not role_asset_scene.has_method("begin_right_hand_modifier_reach"):
		return {"available": false, "distance_m": INF, "error_code": "ik_chain_unavailable"}
	var result: Variant = role_asset_scene.call("begin_right_hand_modifier_reach", anchor_world_position, tolerance_m)
	return result if result is Dictionary else {"available": false, "distance_m": INF, "error_code": "ik_chain_unavailable"}


func begin_archive_door_reach_modifier(anchor_world_position: Vector3, tolerance_m: float) -> Dictionary:
	if role_asset_scene == null or not role_asset_scene.has_method("begin_archive_door_reach_modifier"):
		return {"available": false, "distance_m": INF, "error_code": "ik_chain_unavailable"}
	var result: Variant = role_asset_scene.call("begin_archive_door_reach_modifier", anchor_world_position, tolerance_m)
	return result if result is Dictionary else {"available": false, "distance_m": INF, "error_code": "ik_chain_unavailable"}


func clear_right_hand_reach() -> void:
	if role_asset_scene != null and role_asset_scene.has_method("clear_right_hand_reach"):
		role_asset_scene.call("clear_right_hand_reach")


func measure_right_hand_to_anchor(anchor_world_position: Vector3) -> Dictionary:
	if role_asset_scene == null or not role_asset_scene.has_method("measure_right_hand_to_anchor"):
		return {"available": false, "distance_m": INF, "error_code": "ik_chain_unavailable"}
	var result: Variant = role_asset_scene.call("measure_right_hand_to_anchor", anchor_world_position)
	return result if result is Dictionary else {"available": false, "distance_m": INF, "error_code": "ik_chain_unavailable"}

func begin_embodied_control_frame(world_position: Vector3, move_direction: Vector3, look_target: Vector3, is_grounded: bool, wants_run: bool, gait_name: String, stance_name: String, jump_type: String) -> void:
	driver_mode = DriverMode.PLAYER
	player_shell_active = true
	player_control_move_direction = Vector3(move_direction.x, 0.0, move_direction.z)
	player_control_wants_run = wants_run
	if stance_name == "crouch":
		posture_target = Vector3(0.0, -0.22, 0.02)
	elif hold_timer <= 0.0 and focus_attention_posture_timer <= 0.0:
		posture_target = Vector3.ZERO
	if global_position.distance_to(world_position + player_shell_visual_offset) > 1.0:
		global_position = Vector3(world_position.x, world_position.y, world_position.z) + player_shell_visual_offset
	set_look_target(look_target)

func consume_player_root_motion_request(delta: float) -> Vector3:
	if not player_shell_active:
		return Vector3.ZERO
	if not runtime_state.is_player_shell_grounded():
		locomotion_state = LocomotionState.ATTEND
		if runtime_state.get_player_jump_type() != "none":
			_set_role_asset_motion_profile("jump", "jump_single_leg" if runtime_state.get_player_jump_type() == "single_leg" else "jump_two_foot")
		if runtime_state.get_player_jump_type() != "none":
			_trigger_role_state("jump", 0.24 if runtime_state.get_player_jump_type() == "single_leg" else 0.32)
			_emit_physiology_state_fact("elevated")
		last_root_motion_world_delta = Vector3.ZERO
		return Vector3.ZERO
	_emit_physiology_state_fact("stable")

	var move_direction: Vector3 = Vector3(player_control_move_direction.x, 0.0, player_control_move_direction.z)
	if move_direction.length() <= 0.001:
		_flush_role_root_motion()
		locomotion_state = LocomotionState.IDLE
		last_root_motion_world_delta = Vector3.ZERO
		if runtime_state.get_player_stance() == "crouch":
			_set_role_asset_motion_profile_if_free(idle_role_state, "crouch_idle")
		else:
			_set_role_asset_motion_profile_if_free(idle_role_state, "default")
		return Vector3.ZERO

	move_direction = move_direction.normalized()
	current_look_target = global_position + move_direction
	has_look_target = true
	locomotion_state = LocomotionState.WALK
	if runtime_state.get_player_stance() != "crouch":
		posture_target = Vector3.ZERO
	if runtime_state.get_player_stance() == "crouch":
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
	_log_root_motion_step("player_root_motion_step", true)
	return requested_step

func apply_embodied_pose_sync(world_position: Vector3, planar_velocity: Vector3, look_target: Vector3, is_grounded: bool, player_motion_state: Dictionary = {}) -> void:
	driver_mode = DriverMode.PLAYER
	player_shell_active = true
	var current_stance: String = runtime_state.get_player_stance()
	var current_gait: String = runtime_state.get_player_gait()
	var current_jump: String = runtime_state.get_player_jump_type()
	# Historical contract note for static architecture guards:
	# var player_presentation_input := runtime_state.stage_player_shell_pose(
	var player_presentation_input: Dictionary = runtime_state.stage_player_shell_pose(
		_normalize_motion_state(_resolve_player_motion_state(player_motion_state, planar_velocity, is_grounded)),
		_build_player_presentation_input(),
		current_stance,
		current_gait,
		current_jump,
	)
	global_position = Vector3(world_position.x, world_position.y, world_position.z) + player_shell_visual_offset
	set_look_target(look_target)
	_push_presentation_input(player_presentation_input)
	_update_player_shell_locomotion()

func clear_embodied_control_frame() -> void:
	player_shell_active = false
	driver_mode = DriverMode.AI
	runtime_state.clear_player_shell_pose()
	player_control_move_direction = Vector3.ZERO
	player_control_wants_run = false
	current_velocity = Vector3.ZERO
	action_override_state = ""
	action_override_timer = 0.0
	last_root_motion_world_delta = Vector3.ZERO
	last_locomotion_status_signature = ""
	runtime_state.clear_active_command()
	clear_move_target()
	clear_look_target()
	if locomotion_state == LocomotionState.WALK or locomotion_state == LocomotionState.ATTEND:
		locomotion_state = LocomotionState.IDLE
		_set_role_asset_state(idle_role_state)

func is_embodied_control_active() -> bool:
	return player_shell_active

func get_embodied_anchor_position() -> Vector3:
	return global_position

func get_embodied_forward_vector() -> Vector3:
	return global_basis.z.normalized()

func apply_dialogue(payload: Dictionary) -> void:
	var voice := get_node_or_null("SpatialVoiceController")
	if voice and voice.has_method("play_voice"):
		voice.play_voice(payload)
	_pause_and_face(_resolve_player_position())
	_set_dialogue_pose()
	_trigger_role_state(dialogue_role_state, hold_duration)
	_bus_log("dialogue_applied:%s" % actor_id)

func apply_attention(payload: Dictionary) -> void:
	var target_position := _resolve_attention_target(payload)
	_pause_and_face(target_position)
	_set_attention_pose()
	_trigger_role_state(attention_role_state, hold_duration)
	_bus_log("attention_applied:%s" % actor_id)

func _on_dialogue_received(payload: Dictionary) -> void:
	if runtime_state.is_dialogue_payload_for_actor(payload, actor_id):
		apply_dialogue(payload)

func _on_siming_output_received(payload: Dictionary) -> void:
	if runtime_state.is_siming_output_for_actor(payload, actor_id):
		apply_attention(payload)

func _on_character_agent_execution_received(payload: Dictionary) -> void:
	if not runtime_state.execution_payload_targets_actor(payload, actor_id):
		return
	var presentation_plan: Dictionary = runtime_state.get_execution_payload_presentation_plan(payload)
	var frame: Dictionary = runtime_state.get_execution_payload_intent_frame(payload, actor_id)
	if frame.is_empty():
		return
	runtime_state.stage_agent_execution(presentation_plan, frame)
	var execution_side_effect_plan: Dictionary = runtime_state.build_agent_execution_side_effect_plan(
		dialogue_role_state,
		interaction_role_state,
		focus_role_state,
		attention_role_state,
	)
	var active_command_type: String = runtime_state.get_execution_side_effect_active_command_type(execution_side_effect_plan)
	if active_command_type.is_empty():
		active_command_type = runtime_state.get_intent_frame_action_name(frame)
	runtime_state.set_active_command(active_command_type, _command_priority(active_command_type))
	_push_presentation_input(runtime_state.get_agent_presentation_input())
	var execution_semantics: Dictionary = runtime_state.get_execution_side_effect_execution_semantics(execution_side_effect_plan)
	var target_lookup: Dictionary = runtime_state.get_execution_side_effect_focus_target_lookup(execution_side_effect_plan)
	var target_node := _find_node_by_lookup(target_lookup)
	if target_node != null:
		var movement_intent := runtime_state.get_execution_semantics_movement_intent(execution_semantics)
		_update_autonomous_contact_target(movement_intent, target_node)
		set_look_target(target_node.global_position)
	# Historical contract note for static architecture guards:
	# var physiology_hint := runtime_state.get_execution_side_effect_physiology_hint(execution_side_effect_plan)
	var physiology_hint: String = runtime_state.get_execution_side_effect_physiology_hint(execution_side_effect_plan)
	if not physiology_hint.is_empty():
		_emit_physiology_state_fact(physiology_hint)
	for effect: Dictionary in runtime_state.get_execution_side_effect_role_state_effects(execution_side_effect_plan):
		var state_name: String = runtime_state.get_role_state_effect_name(effect)
		if not state_name.is_empty():
			_trigger_role_state(state_name, hold_duration)
			if state_name == "greeting_nod":
				_bus_log("autonomous_contact:greeting_applied=true:%s" % actor_id)
	_bus_log("character_agent_execution_applied:%s" % actor_id)

func _update_autonomous_contact_target(active_command_type: String, target_node: Node3D) -> void:
	if target_node == null:
		_active_contact_target_actor_id = ""
		return
	var target_actor_id := str(target_node.get("actor_id") or "")
	match active_command_type:
		"approach", "follow_target":
			if not target_actor_id.is_empty():
				_active_contact_target_actor_id = target_actor_id
				set_move_target(target_node.global_position)
				_bus_log("autonomous_contact:approach_started=true:%s:%s" % [actor_id, target_actor_id])
		_:
			if active_command_type != "speak_public" and active_command_type != "speak_private":
				_active_contact_target_actor_id = ""

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
			"content": runtime_state.get_payload_string(payload, "dialogue_text"),
			"target_actor_id": runtime_state.get_payload_string(payload, "target_actor_id"),
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
	if runtime_state.get_active_command_type().is_empty():
		return true
	return _command_priority(next_command_type) >= runtime_state.get_active_command_priority()

func _clear_completed_command() -> void:
	runtime_state.clear_active_command()

func _emit_character_actor_status(status: String, command_payload: Dictionary, failure_reason: String = "") -> void:
	var payload := {
		"actor_id": actor_id,
		"command_status": status,
		"command_type": runtime_state.get_payload_string(command_payload, "command_type"),
		"target_actor_id": runtime_state.get_payload_string(command_payload, "target_actor_id"),
		"target_object_id": runtime_state.get_payload_string(command_payload, "target_object_id"),
		"target_environment_id": runtime_state.get_payload_string(command_payload, "target_environment_id"),
		"failure_reason": failure_reason,
		"causation_id": runtime_state.get_payload_string(command_payload, "causation_id"),
		"correlation_id": runtime_state.get_payload_string(command_payload, "correlation_id"),
	}
	var bus := _get_bus()
	if bus and bus.has_signal("character_actor_status_emitted"):
		bus.emit_signal("character_actor_status_emitted", payload)

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
	var collider: Variant = runtime_state.get_line_of_sight_hit_collider(hit)
	if collider == target_node:
		return true
	if collider is Node:
		return target_node.is_ancestor_of(collider as Node)
	return false

func _resolve_character_visual_fact_emitter() -> Node:
	if not character_visual_fact_emitter_path.is_empty():
		var local_emitter := get_node_or_null(character_visual_fact_emitter_path)
		if local_emitter != null:
			return local_emitter
	var scene := get_tree().current_scene
	if scene != null:
		return scene.get_node_or_null("VisualFactEmitter/CharacterVisualFactEmitter")
	return null

func _resolve_spatial_access_fact_emitter() -> Node:
	if not spatial_access_fact_emitter_path.is_empty():
		var local_emitter := get_node_or_null(spatial_access_fact_emitter_path)
		if local_emitter != null:
			return local_emitter
	var scene := get_tree().current_scene
	if scene != null:
		return scene.get_node_or_null("VisualFactEmitter/SpatialAccessFactEmitter")
	return null

func _emit_actor_notice_fact(target_actor_id: String) -> bool:
	if target_actor_id.is_empty():
		return false
	var emitter := _resolve_character_visual_fact_emitter()
	if emitter == null:
		return false
	if emitter.has_method("emit_fixed_gaze_on_target"):
		var emitted: Variant = emitter.emit_fixed_gaze_on_target(target_actor_id, "")
		if bool(emitted):
			_bus_log("actor_local_perception:notice_emitted=true:%s:%s" % [actor_id, target_actor_id])
			_bus_log("actor_local_perception:fact_routed=true:%s:%s" % [actor_id, target_actor_id])
			_bus_log("autonomous_contact:notice=true:%s:%s" % [actor_id, target_actor_id])
			return true
	return false

func _emit_arrival_fact(target_actor_id: String, distance_m: float) -> bool:
	if target_actor_id.is_empty():
		return false
	var emitter := _resolve_spatial_access_fact_emitter()
	if emitter == null:
		return false
	if emitter.has_method("emit_actor_approached_actor"):
		var emitted: Variant = emitter.emit_actor_approached_actor(target_actor_id, distance_m)
		if bool(emitted):
			_bus_log("autonomous_contact:arrival_fact=true:%s:%s" % [actor_id, target_actor_id])
		return bool(emitted)
	return false

func _configure_actor_local_perception() -> void:
	_perception_sampler.range_m = perception_range_m
	_perception_sampler.forward_threshold = perception_forward_threshold
	_perception_target_resolver.target_property_names = PackedStringArray([
		"actor_id",
		"object_id",
		"environment_id",
	])

func _configure_actor_local_emitters() -> void:
	var visual_fact_emitter := get_node_or_null("VisualFactEmitter")
	if visual_fact_emitter != null and visual_fact_emitter.get("actor_id") != actor_id:
		visual_fact_emitter.set("actor_id", actor_id)
	var spatial_access_fact_emitter := _resolve_spatial_access_fact_emitter()
	if spatial_access_fact_emitter != null and spatial_access_fact_emitter.get("actor_id") != actor_id:
		spatial_access_fact_emitter.set("actor_id", actor_id)

func _sample_actor_local_perception() -> void:
	if not actor_local_perception_enabled:
		return
	var scene := get_tree().current_scene
	if scene == null:
		return
	var targets := _perception_target_resolver.resolve_targets(scene, self)
	if targets.is_empty():
		return
	var visible := _perception_sampler.sample_visible_targets(
		get_focus_anchor_position(),
		get_embodied_forward_vector(),
		targets,
		self,
		Callable(self, "_get_perception_target_position"),
		Callable(self, "_has_line_of_sight_to_target")
	)
	if visible.is_empty():
		return
	var actor_target := _first_visible_actor_target(visible)
	if actor_target == null:
		return
	var target_actor_id := str(actor_target.get("actor_id") or "")
	if target_actor_id.is_empty():
		return
	var target_position := _get_perception_target_position(actor_target)
	var distance_m := get_focus_anchor_position().distance_to(target_position)
	var now_ms := Time.get_ticks_msec()
	if target_actor_id == _last_notice_target and now_ms - _last_notice_ts < actor_notice_cooldown_ms:
		return
	_last_notice_target = target_actor_id
	_last_notice_ts = now_ms
	var notice_emitted := _emit_actor_notice_fact(target_actor_id)
	if notice_emitted:
		_bus_log("actor_local_perception:character_runtime_seen=true:%s" % actor_id)
	if distance_m <= actor_arrival_distance:
		_emit_arrival_fact(target_actor_id, distance_m)

func set_actor_local_perception_enabled(is_enabled: bool) -> void:
	actor_local_perception_enabled = is_enabled

func _first_visible_actor_target(candidates: Array[Node3D]) -> Node3D:
	for candidate: Node3D in candidates:
		var candidate_actor_id := str(candidate.get("actor_id") or "")
		if candidate_actor_id.is_empty() or candidate_actor_id == actor_id:
			continue
		return candidate
	return null

func _get_perception_target_position(candidate: Node3D) -> Vector3:
	if candidate == null:
		return Vector3.ZERO
	if candidate.has_method("get_focus_anchor_position"):
		var focus_anchor: Variant = candidate.get_focus_anchor_position()
		if focus_anchor is Vector3:
			return focus_anchor
	return candidate.global_position

func _is_target_reachable(target_node: Node3D) -> bool:
	if target_node == null or not target_node.is_inside_tree():
		return false
	return global_position.distance_to(target_node.global_position) <= embodied_interaction_distance

func _on_focus_state_received(payload: Dictionary) -> void:
	if not runtime_state.should_apply_focus_attention(payload, actor_id, reacts_to_player_focus):
		return

	_bus_log("focus_state_applied:%s" % actor_id)
	_focus_on_player_attention()

func _on_character_runtime_state_snapshot_received(payload: Dictionary) -> void:
	if not runtime_state.is_runtime_state_payload_for_actor(payload, actor_id):
		return
	_apply_runtime_state_payload(payload)

func _on_character_runtime_state_delta_received(payload: Dictionary) -> void:
	if not runtime_state.is_runtime_state_payload_for_actor(payload, actor_id):
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
	if runtime_state.should_sync_emitter_actor_id(role_state_fact_emitter, actor_id):
		role_state_fact_emitter.set("actor_id", actor_id)
	if not role_state_fact_emitter.has_method("emit_role_state_transition"):
		return
	var emitted: Variant = role_state_fact_emitter.emit_role_state_transition(next_state)
	if bool(emitted):
		last_role_state_fact = next_state

func _get_physiology_state_fact_emitter() -> Node:
	return get_node_or_null(physiology_state_fact_emitter_path)

func _emit_physiology_state_fact(strain_band: String) -> void:
	if strain_band.is_empty() or strain_band == runtime_state.get_last_physiology_state_fact():
		return
	if not _is_backend_open():
		return
	var physiology_state_fact_emitter := _get_physiology_state_fact_emitter()
	if physiology_state_fact_emitter == null:
		return
	if runtime_state.should_sync_emitter_actor_id(physiology_state_fact_emitter, actor_id):
		physiology_state_fact_emitter.set("actor_id", actor_id)
	if not physiology_state_fact_emitter.has_method("emit_breathing_strain_fact"):
		return
	var emitted: Variant = physiology_state_fact_emitter.emit_breathing_strain_fact(strain_band)
	if bool(emitted):
		runtime_state.set_last_physiology_state_fact(strain_band)

func set_focus_highlight(is_focused: bool) -> void:
	var runtime_attention_source: String = runtime_state.get_runtime_attention_source()
	var highlighted: bool = runtime_state.should_highlight_focus(
		is_focused,
		focus_attention_visual_timer,
		runtime_attention_source,
		runtime_state.get_runtime_nearby_environment_refs(),
	)
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
		current_velocity = runtime_state.get_player_shell_velocity()
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
		if clear_on_arrival and _active_contact_target_actor_id != "":
			_emit_arrival_fact(_active_contact_target_actor_id, 0.0)
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
			_log_root_motion_step("patrol_root_motion_step", false)
			return

	current_velocity = current_velocity.move_toward(move_direction * move_speed, move_accel * delta)
	var step: Vector3 = current_velocity * delta
	if step.length() > to_target.length():
		step = move_direction * to_target.length()

	global_position += step
	last_root_motion_world_delta = step
	if not clear_on_arrival and use_root_motion_patrol and role_asset_scene != null and role_asset_scene.has_method("consume_root_motion_delta"):
		_log_root_motion_step("patrol_root_motion_step", false)

func _update_player_shell_locomotion() -> void:
	var motion_fields: Dictionary = runtime_state.resolve_player_presentation_motion_fields()
	var move_local: Vector2 = runtime_state.get_motion_fields_move_local(motion_fields)
	var velocity_world: Vector3 = runtime_state.get_motion_fields_velocity_world(motion_fields)
	var move_x := move_local.x
	var move_y := move_local.y
	var planar_speed := velocity_world.length()
	var locomotion_decision: Dictionary = runtime_state.resolve_player_locomotion_state(
		move_x,
		move_y,
		planar_speed,
		player_walk_speed_threshold,
		player_run_speed_threshold,
	)
	match runtime_state.get_locomotion_decision_state(locomotion_decision):
		"attend":
			locomotion_state = LocomotionState.ATTEND
		"walk":
			locomotion_state = LocomotionState.WALK
		_:
			locomotion_state = LocomotionState.IDLE
	if runtime_state.should_clear_root_motion(locomotion_decision):
		_flush_role_root_motion()
	if runtime_state.should_reset_posture(locomotion_decision):
		posture_target = Vector3.ZERO
	var motion_profile: String = runtime_state.get_locomotion_decision_motion_profile(locomotion_decision)
	match motion_profile:
		"jump_single_leg", "jump_two_foot":
			_set_role_asset_motion_profile("jump", motion_profile)
		"crouch_walk":
			_set_role_asset_motion_profile_if_free("walk", "crouch_walk")
		"crouch_idle":
			_set_role_asset_motion_profile_if_free(idle_role_state, "crouch_idle")
		"run":
			_set_role_asset_motion_profile_if_free("run", "run")
		"walk":
			_set_role_asset_motion_profile_if_free("walk", "walk")
		"default":
			_set_role_asset_motion_profile_if_free(idle_role_state, "default")
		"player_gait":
			_apply_player_locomotion_profile()
	var role_state: String = runtime_state.get_locomotion_decision_role_state(locomotion_decision)
	if not role_state.is_empty():
		_trigger_role_state(role_state, runtime_state.get_locomotion_decision_role_state_duration(locomotion_decision))
	var physiology_hint: String = runtime_state.get_locomotion_decision_physiology_hint(locomotion_decision)
	if not physiology_hint.is_empty():
		_emit_physiology_state_fact(physiology_hint)

func _resolve_player_motion_state(player_motion_state: Dictionary, planar_velocity: Vector3, is_grounded: bool) -> Dictionary:
	if not player_motion_state.is_empty():
		return _normalize_motion_state(player_motion_state.duplicate(true))
	return {
		"position": global_position,
		"velocity_world": planar_velocity,
		"move_local_actual": Vector2.ZERO,
		"gait_actual": "run" if planar_velocity.length() > player_run_speed_threshold else "walk",
		"grounded": is_grounded,
	}

func _build_player_presentation_input() -> Dictionary:
	return runtime_state.build_player_presentation_input(
		action_override_state,
	)

func _push_presentation_input(presentation_input: Dictionary) -> void:
	if role_asset_scene and role_asset_scene.has_method("apply_presentation_input"):
		role_asset_scene.apply_presentation_input(presentation_input)

func _normalize_motion_state(candidate: Dictionary) -> Dictionary:
	return CharacterActorSchemaRef.normalize_motion_state(candidate)

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
	runtime_state.apply_runtime_state_payload(payload)

func _tick_runtime_feedback(delta: float) -> void:
	if runtime_feedback == null or not runtime_feedback.has_method("tick"):
		return
	var source_visual_fact: bool = runtime_state.get_runtime_attention_source() == "visual_fact"
	var environment_attention: bool = source_visual_fact and runtime_state.get_runtime_nearby_environment_refs().size() > 0
	var attention_active: bool = focus_attention_visual_timer > 0.0 or runtime_state.get_runtime_conversation_candidate_refs().size() > 0 or source_visual_fact
	runtime_feedback.tick(delta, actor_id, attention_active, environment_attention, source_visual_fact, focus_attention_visual_timer > 0.0)

func _resolve_player_position() -> Vector3:
	return global_position - global_basis.z

func _resolve_attention_target(payload: Dictionary) -> Vector3:
	var target_ref: String = runtime_state.resolve_attention_target_ref(payload)
	if target_ref.begins_with("env_"):
		var environment_node := _find_node_by_property("environment_id", target_ref)
		if environment_node:
			return environment_node.global_position
	if target_ref.begins_with("obj_"):
		var object_node := _find_node_by_property("object_id", target_ref)
		if object_node:
			return object_node.global_position
	if target_ref.begins_with("char_"):
		var actor_node := _find_node_by_property("actor_id", target_ref)
		if actor_node:
			return actor_node.global_position

	return _resolve_player_position()

func _command_target_position(payload: Dictionary) -> Vector3:
	var target_position_raw: Variant = runtime_state.get_command_target_position(payload)
	if target_position_raw is Array and target_position_raw.size() == 3:
		return Vector3(
			float(target_position_raw[0]),
			float(target_position_raw[1]),
			float(target_position_raw[2])
		)
	return _resolve_attention_target(payload)

func _command_target_node(payload: Dictionary) -> Node3D:
	var object_id: String = runtime_state.get_payload_string(payload, "target_object_id")
	if not object_id.is_empty():
		return _find_node_by_property("object_id", object_id)
	var actor_target: String = runtime_state.get_payload_string(payload, "target_actor_id")
	if not actor_target.is_empty():
		return _find_node_by_property("actor_id", actor_target)
	var environment_id: String = runtime_state.get_payload_string(payload, "target_environment_id")
	if not environment_id.is_empty():
		return _find_node_by_property("environment_id", environment_id)
	return null

func _find_node_by_property(property_name: String, expected: String) -> Node3D:
	var scene := get_tree().current_scene
	if scene == null:
		return null
	return _find_node_by_property_recursive(scene, property_name, expected)


func _find_node_by_lookup(lookup: Dictionary) -> Node3D:
	var property_name: String = runtime_state.get_target_lookup_property_name(lookup)
	var expected: String = runtime_state.get_target_lookup_expected(lookup)
	if property_name.is_empty() or expected.is_empty():
		return null
	return _find_node_by_property(property_name, expected)

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

func apply_presentation_asset_binding(binding: Dictionary) -> bool:
	if str(binding.get("actor_id", "")) != actor_id:
		return false
	if str(binding.get("binding_status", "")) != "approved":
		return false
	var visual_assets: Variant = binding.get("visual_assets", {})
	if not (visual_assets is Dictionary):
		return false
	var role_scene_ref := str((visual_assets as Dictionary).get("role_scene_ref", ""))
	if not role_scene_ref.is_empty() and not _mount_manifest_role_scene(role_scene_ref):
		return false
	if role_asset_scene != null and role_asset_scene.has_method("apply_asset_binding"):
		role_asset_scene.apply_asset_binding(binding)
	_apply_role_asset_config()
	_bus_log("presentation_asset_binding_applied:%s" % actor_id)
	return true

func _mount_manifest_role_scene(role_scene_ref: String) -> bool:
	if not role_scene_ref.begins_with("res://") or role_asset_root == null:
		return false
	var resource := load(role_scene_ref)
	if not (resource is PackedScene):
		return false
	var mounted := (resource as PackedScene).instantiate()
	if not (mounted is Node):
		return false
	if _manifest_role_asset_scene != null:
		_manifest_role_asset_scene.queue_free()
	role_asset_root.add_child(mounted)
	_manifest_role_asset_scene = mounted as Node
	if _fallback_role_asset_scene is Node3D:
		(_fallback_role_asset_scene as Node3D).visible = false
	role_asset_scene = _manifest_role_asset_scene
	if role_asset_scene is Node3D:
		(role_asset_scene as Node3D).visible = true
	return true

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
		"stance": runtime_state.get_player_stance(),
		"gait": runtime_state.get_player_gait(),
		"jump_type": runtime_state.get_player_jump_type(),
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


func _log_root_motion_step(marker: String, is_player_step: bool) -> void:
	var now_ms := Time.get_ticks_msec()
	if is_player_step:
		if now_ms - last_player_root_motion_log_ms < ROOT_MOTION_LOG_COOLDOWN_MS:
			return
		last_player_root_motion_log_ms = now_ms
	else:
		if now_ms - last_patrol_root_motion_log_ms < ROOT_MOTION_LOG_COOLDOWN_MS:
			return
		last_patrol_root_motion_log_ms = now_ms
	_bus_log("%s:%s" % [marker, actor_id])

func _apply_player_locomotion_profile() -> void:
	var motion_profile: String = runtime_state.resolve_player_gait_motion_profile()
	if motion_profile == "run":
		_set_role_asset_motion_profile_if_free("run", motion_profile)
		return
	_set_role_asset_motion_profile_if_free("walk", motion_profile)

func _get_current_role_clip_name() -> String:
	if role_asset_scene and role_asset_scene.has_method("get_current_clip_name"):
		return str(role_asset_scene.get_current_clip_name())
	return ""

func _get_current_role_profile_name() -> String:
	if role_asset_scene and role_asset_scene.has_method("get_current_motion_profile_name"):
		return str(role_asset_scene.get_current_motion_profile_name())
	return "default"
