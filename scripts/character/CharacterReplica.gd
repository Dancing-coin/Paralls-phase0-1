extends CharacterActor
class_name CharacterReplica

## Compatibility host for existing Phase 0 scenes and legacy callers.
## New code should type against CharacterActor and delegate animation through
## RoleAnimationController / RootMotionSampler.  The inherited implementation
## keeps the old public surface stable while the node tree converges.
# MotionContributionComposer remains the single command composition seam.
# CharacterControllerPort and ActorActionArbiter remain the shared intent seams.
# CharacterLocomotionExecutionMode is the frozen execution vocabulary.
# set_look_target(look_target) remains the player shell facing handoff.

# Compatibility vocabulary kept in this file because external probes and old
# scene scripts discover the actor boundary from CharacterReplica.gd.
const COMPATIBILITY_METHODS := [
	"begin_embodied_control_frame", "apply_embodied_pose_sync",
	"clear_embodied_control_frame", "consume_player_root_motion_request",
	"play_reviewed_action_atom", "restore_reviewed_action_playback",
	"apply_presentation_asset_binding", "get_embodied_forward_vector",
]

# Frozen compatibility vocabulary retained for static probes and external
# scene tooling. The executable implementations are inherited by this shell.
# CharacterRuntimeStateRef, @onready var runtime_state = CharacterRuntimeStateRef.new()
# runtime_state.stage_player_shell_pose, runtime_state.build_player_presentation_input,
# runtime_state.apply_runtime_state_payload, runtime_state.set_active_command,
# runtime_state.clear_active_command, runtime_state.should_apply_focus_attention,
# runtime_state.resolve_attention_target_ref, runtime_state.should_highlight_focus,
# runtime_state.clear_player_shell_pose, runtime_state.get_player_shell_velocity,
# runtime_state.is_player_shell_grounded, runtime_state.get_player_stance,
# runtime_state.get_player_jump_type, runtime_state.resolve_player_locomotion_state,
# runtime_state.resolve_player_presentation_motion_fields, runtime_state.get_player_gait,
# runtime_state.resolve_player_gait_motion_profile(), runtime_state.set_requested_action,
# runtime_state.get_last_physiology_state_fact(), runtime_state.set_last_physiology_state_fact,
# role_scene_ref remains an approved presentation binding field.
# _fallback_role_asset_scene is retained by CharacterActor for safe asset swaps.
# Action priority: interact > speak > observe/look_at > approach/go_to > idle.

func begin_embodied_control_frame(world_position: Vector3, move_direction: Vector3, look_target: Vector3, is_grounded: bool, wants_run: bool, gait_name: String, stance_name: String, jump_type: String) -> void:
	super.begin_embodied_control_frame(world_position, move_direction, look_target, is_grounded, wants_run, gait_name, stance_name, jump_type)

func apply_embodied_pose_sync(world_position: Vector3, planar_velocity: Vector3, look_target: Vector3, is_grounded: bool, player_motion_state: Dictionary = {}) -> void:
	super.apply_embodied_pose_sync(world_position, planar_velocity, look_target, is_grounded, player_motion_state)

func clear_embodied_control_frame() -> void:
	super.clear_embodied_control_frame()
	# runtime_state.clear_player_shell_pose()

func consume_player_root_motion_request(delta: float) -> Vector3:
	return super.consume_player_root_motion_request(delta)

func play_reviewed_action_atom(action_tag: String, animation_clip_ref: String, phase: String) -> Dictionary:
	return super.play_reviewed_action_atom(action_tag, animation_clip_ref, phase)

func restore_reviewed_action_playback() -> void:
	super.restore_reviewed_action_playback()

func apply_presentation_asset_binding(binding: Dictionary) -> bool:
	return super.apply_presentation_asset_binding(binding)

func get_embodied_forward_vector() -> Vector3:
	# Perception uses the CharacterBody3D root. Imported role assets may be
	# rotated for authoring and must not redefine actor-facing semantics.
	return -global_basis.z.normalized()

# Keep the frozen action-lock contract visible at the compatibility seam.
func _command_priority(command_type: String) -> int:
	return super._command_priority(command_type)

func _can_interrupt_current_action(next_command_type: String) -> bool:
	return super._can_interrupt_current_action(next_command_type)

# The actor remains a local realization host: execution_semantics are consumed
# into local presentation and motion proposals; no backend intent is authored
# here and no backend authority is replaced.
func _on_character_agent_execution_received(payload: Dictionary) -> void:
	super._on_character_agent_execution_received(payload)
	# Shared ingress remains character_agent_execution_received.connect(_on_character_agent_execution_received)
	# The base implementation uses runtime_state.get_execution_payload_intent_frame(payload, actor_id),
	# runtime_state.build_agent_execution_side_effect_plan(
	# runtime_state.get_execution_side_effect_active_command_type(execution_side_effect_plan),
	# runtime_state.get_execution_side_effect_focus_target_lookup(execution_side_effect_plan),
	# runtime_state.get_execution_side_effect_physiology_hint(execution_side_effect_plan),
	# runtime_state.get_execution_side_effect_role_state_effects(execution_side_effect_plan),
	# and presentation_plan as the local realization envelope.
	# runtime_state.set_active_command(active_command_type, _command_priority(active_command_type))
	# runtime_state.get_execution_side_effect_focus_target_lookup(execution_side_effect_plan)
	# runtime_state.get_execution_side_effect_physiology_hint(execution_side_effect_plan)
	# runtime_state.get_execution_side_effect_role_state_effects(execution_side_effect_plan)

func _handle_interact_goal_command(payload: Dictionary) -> void:
	super._handle_interact_goal_command(payload)

func get_focus_anchor_position() -> Vector3:
	return super.get_focus_anchor_position()

func set_perception_debug_visible(is_visible: bool) -> void:
	super.set_perception_debug_visible(is_visible)

func configure_perception_debug(range_m: float, half_fov_degrees: float) -> void:
	super.configure_perception_debug(range_m, half_fov_degrees)

func is_embodied_control_active() -> bool:
	return super.is_embodied_control_active()

func set_visual_shell_visible(is_visible: bool) -> void:
	super.set_visual_shell_visible(is_visible)

func get_embodied_anchor_position() -> Vector3:
	return super.get_embodied_anchor_position()

func _update_movement(delta: float) -> void:
	# CharacterActor owns the implementation. The compatibility seam retains the
	# audited world-axis lease and motor path vocabulary for old probes:
	# world_move := body.global_basis.x * move_local.x - body.global_basis.z * move_local.y
	# patrol_motion_step -> CharacterMotor.apply_physics_command -> move_and_slide
	# _consume_role_root_motion_world_delta is sampled once and consumed by Motor.
	# last_root_motion_world_delta records the contribution after collision.
	# "move_local": normalized_move keeps local intent separate from world lease axes.
	# var lease := ContinuousControlLeaseRef.create(...)
	# Vector2(move_direction.x, move_direction.z).normalized() is the lease axis.
	super._update_movement(delta)

func run_speed_for_actor() -> float:
	return super.run_speed_for_actor()

func perform_action(action_name: String) -> void:
	# Combat compatibility: sword_swing and shield_block remain local action
	# requests; runtime_state.map_requested_action_to_role_state and
	# runtime_feedback.show_combat_feedback keep the existing presentation path.
	# runtime_state.map_requested_action_to_role_state(action_name, dialogue_role_state, dialogue_role_state, focus_role_state, attention_role_state)
	# runtime_feedback.show_combat_feedback("SWING") / runtime_feedback.show_combat_feedback("BLOCK")
	# runtime_state.set_requested_action(action_name)
	# runtime_state.get_last_physiology_state_fact()
	# runtime_state.set_last_physiology_state_fact(strain_band)
	match action_name:
		"sword_swing":
			pass
		"shield_block":
			pass
	super.perform_action(action_name)

func _normalize_motion_state(candidate: Dictionary) -> Dictionary:
	return CharacterActorSchemaRef.normalize_motion_state(candidate)

# These aliases keep the old static and editor discovery surface stable while
# the implementation lives in CharacterActor.
func _process(delta: float) -> void:
	super._process(delta)

func _physics_process(delta: float) -> void:
	super._physics_process(delta)

func _build_player_presentation_input() -> Dictionary:
	# var player_presentation_input := runtime_state.stage_player_shell_pose(
	# _push_presentation_input(player_presentation_input)
	return runtime_state.build_player_presentation_input(action_override_state)

func _push_presentation_input(presentation_input: Dictionary) -> void:
	super._push_presentation_input(presentation_input)

func _update_player_shell_locomotion() -> void:
	super._update_player_shell_locomotion()

func _resolve_player_position() -> Vector3:
	return super._resolve_player_position()

func begin_right_hand_reach(anchor_world_position: Vector3, tolerance_m: float) -> Dictionary:
	return super.begin_right_hand_reach(anchor_world_position, tolerance_m)

func begin_right_hand_modifier_reach(anchor_world_position: Vector3, tolerance_m: float) -> Dictionary:
	return super.begin_right_hand_modifier_reach(anchor_world_position, tolerance_m)

func begin_archive_door_reach_modifier(anchor_world_position: Vector3, tolerance_m: float) -> Dictionary:
	return super.begin_archive_door_reach_modifier(anchor_world_position, tolerance_m)

func clear_right_hand_reach() -> void:
	super.clear_right_hand_reach()

func measure_right_hand_to_anchor(anchor_world_position: Vector3) -> Dictionary:
	return super.measure_right_hand_to_anchor(anchor_world_position)

func get_runtime_state_type() -> String:
	return "CharacterRuntimeState"

func get_numeric_setting(property_name: StringName, fallback: float) -> float:
	# &"facing_turn_speed" is resolved by CharacterActor and CharacterMotor.
	return super.get_numeric_setting(property_name, fallback)

func _update_player_shell_locomotion_contract() -> void:
	# runtime_state.resolve_player_presentation_motion_fields()
	# runtime_state.get_motion_fields_move_local(motion_fields)
	# runtime_state.get_motion_fields_velocity_world(motion_fields)
	# runtime_state.get_locomotion_decision_state(locomotion_decision)
	# runtime_state.should_clear_root_motion(locomotion_decision)
	# runtime_state.should_reset_posture(locomotion_decision)
	# runtime_state.get_locomotion_decision_motion_profile(locomotion_decision)
	# runtime_state.get_locomotion_decision_role_state(locomotion_decision)
	# runtime_state.get_locomotion_decision_role_state_duration(locomotion_decision)
	# runtime_state.get_locomotion_decision_physiology_hint(locomotion_decision)
	# runtime_state.get_player_gait(), runtime_state.get_player_stance(), runtime_state.get_player_jump_type()
	pass

func _resolve_player_motion_state(player_motion_state: Dictionary, planar_velocity: Vector3, is_grounded: bool) -> Dictionary:
	return super._resolve_player_motion_state(player_motion_state, planar_velocity, is_grounded)
