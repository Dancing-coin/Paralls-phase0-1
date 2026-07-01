extends RefCounted

class_name CharacterRuntimeState

const CharacterActorSchemaRef = preload("res://scripts/character/CharacterActorSchema.gd")
const AgentControllerAdapterRef = preload("res://scripts/character/AgentControllerAdapter.gd")
const CharacterControllerPortRef = preload("res://scripts/character/CharacterControllerPort.gd")
const CharacterPresentationInputRef = preload("res://scripts/character/CharacterPresentationInput.gd")

var player_motion_state: Dictionary = {}
var player_shell_velocity: Vector3 = Vector3.ZERO
var player_shell_grounded := true
var player_stance := "stand"
var player_gait := "walk"
var player_jump_type := "none"
var requested_action := ""
var last_physiology_state_fact := ""
var agent_presentation_input: Dictionary = {}
var runtime_focus_target := ""
var runtime_attention_source := ""
var runtime_nearby_actor_refs: Array[String] = []
var runtime_nearby_object_refs: Array[String] = []
var runtime_nearby_environment_refs: Array[String] = []
var runtime_conversation_candidate_refs: Array[String] = []
var runtime_engagement_pressure := ""
var runtime_privacy_risk_hint := ""
var active_command_type := ""
var active_command_priority := 0


func stage_player_shell_pose(
	next_motion_state: Dictionary,
	next_presentation_input: Dictionary,
	next_stance: String,
	next_gait: String,
	next_jump_type: String,
) -> Dictionary:
	player_motion_state = next_motion_state.duplicate(true)
	player_shell_velocity = CharacterActorSchemaRef.get_velocity_world(next_motion_state)
	player_shell_grounded = CharacterActorSchemaRef.is_grounded(next_motion_state, true)
	player_stance = next_stance
	player_gait = next_gait
	player_jump_type = next_jump_type
	return next_presentation_input.duplicate(true)


func clear_player_shell_pose() -> void:
	player_motion_state = {}
	player_shell_velocity = Vector3.ZERO
	player_shell_grounded = true
	player_stance = "stand"
	player_gait = "walk"
	player_jump_type = "none"


func get_player_shell_velocity() -> Vector3:
	return player_shell_velocity


func is_player_shell_grounded() -> bool:
	return player_shell_grounded


func get_player_stance() -> String:
	return player_stance


func get_player_gait() -> String:
	return player_gait


func get_player_jump_type() -> String:
	return player_jump_type


func set_requested_action(action_name: String) -> void:
	requested_action = action_name


func get_requested_action() -> String:
	return requested_action


func set_last_physiology_state_fact(strain_band: String) -> void:
	last_physiology_state_fact = strain_band


func get_last_physiology_state_fact() -> String:
	return last_physiology_state_fact


func resolve_player_locomotion_state(
	move_x: float,
	move_y: float,
	planar_speed: float,
	player_walk_speed_threshold: float,
	player_run_speed_threshold: float,
) -> Dictionary:
	var has_move_input: bool = abs(move_x) > 0.001 or abs(move_y) > 0.001
	if not player_shell_grounded:
		return {
			"locomotion_state": "attend",
			"motion_profile": "jump_single_leg" if player_jump_type == "single_leg" else "jump_two_foot",
			"role_state": "jump" if player_jump_type != "none" else "",
			"role_state_duration": 0.24 if player_jump_type == "single_leg" else 0.32,
			"physiology_hint": "elevated" if player_jump_type != "none" else "",
			"clear_root_motion": false,
			"reset_posture": false,
		}
	if player_stance == "crouch" and has_move_input:
		return {
			"locomotion_state": "walk",
			"motion_profile": "crouch_walk",
			"role_state": "",
			"role_state_duration": 0.0,
			"physiology_hint": "stable",
			"clear_root_motion": false,
			"reset_posture": false,
		}
	if player_stance == "crouch":
		return {
			"locomotion_state": "idle",
			"motion_profile": "crouch_idle",
			"role_state": "",
			"role_state_duration": 0.0,
			"physiology_hint": "stable",
			"clear_root_motion": true,
			"reset_posture": false,
		}
	if has_move_input:
		return {
			"locomotion_state": "walk",
			"motion_profile": "player_gait",
			"role_state": "",
			"role_state_duration": 0.0,
			"physiology_hint": "stable",
			"clear_root_motion": false,
			"reset_posture": true,
		}
	if planar_speed > player_run_speed_threshold:
		return {
			"locomotion_state": "walk",
			"motion_profile": "run",
			"role_state": "",
			"role_state_duration": 0.0,
			"physiology_hint": "stable",
			"clear_root_motion": false,
			"reset_posture": true,
		}
	if planar_speed > player_walk_speed_threshold:
		return {
			"locomotion_state": "walk",
			"motion_profile": "walk",
			"role_state": "",
			"role_state_duration": 0.0,
			"physiology_hint": "stable",
			"clear_root_motion": false,
			"reset_posture": true,
		}
	return {
		"locomotion_state": "idle",
		"motion_profile": "default",
		"role_state": "",
		"role_state_duration": 0.0,
		"physiology_hint": "stable",
		"clear_root_motion": true,
		"reset_posture": false,
	}


func resolve_player_gait_motion_profile() -> String:
	match player_gait:
		"amble":
			return "amble"
		"brisk_walk":
			return "brisk_walk"
		"run":
			return "run"
		_:
			return "walk"


func get_locomotion_decision_state(locomotion_decision: Dictionary) -> String:
	return str(locomotion_decision.get("locomotion_state", "idle"))


func should_clear_root_motion(locomotion_decision: Dictionary) -> bool:
	return bool(locomotion_decision.get("clear_root_motion", false))


func should_reset_posture(locomotion_decision: Dictionary) -> bool:
	return bool(locomotion_decision.get("reset_posture", false))


func get_locomotion_decision_motion_profile(locomotion_decision: Dictionary) -> String:
	return str(locomotion_decision.get("motion_profile", "default"))


func get_locomotion_decision_role_state(locomotion_decision: Dictionary) -> String:
	return str(locomotion_decision.get("role_state", ""))


func get_locomotion_decision_role_state_duration(locomotion_decision: Dictionary) -> float:
	return float(locomotion_decision.get("role_state_duration", 0.0))


func get_locomotion_decision_physiology_hint(locomotion_decision: Dictionary) -> String:
	return str(locomotion_decision.get("physiology_hint", ""))


func set_agent_presentation_input(next_input: Dictionary) -> void:
	agent_presentation_input = next_input.duplicate(true)


func get_agent_presentation_input() -> Dictionary:
	return agent_presentation_input


func build_player_presentation_input(
	action_override_state: String,
) -> Dictionary:
	return CharacterPresentationInputRef.from_player_runtime_state(
		player_motion_state,
		runtime_focus_target,
		requested_action,
		action_override_state,
		last_physiology_state_fact,
		active_command_type,
	)


func resolve_player_presentation_motion_fields() -> Dictionary:
	return {
		"move_local": CharacterActorSchemaRef.get_move_local_actual(player_motion_state),
		"velocity_world": CharacterActorSchemaRef.get_velocity_world(player_motion_state) if player_motion_state.has("velocity_world") else player_shell_velocity,
		"gait_actual": CharacterActorSchemaRef.get_gait_actual(player_motion_state),
	}


func get_motion_fields_move_local(motion_fields: Dictionary) -> Vector2:
	var move_local_value: Variant = motion_fields.get("move_local", Vector2.ZERO)
	return move_local_value if move_local_value is Vector2 else Vector2.ZERO


func get_motion_fields_velocity_world(motion_fields: Dictionary) -> Vector3:
	var velocity_world_value: Variant = motion_fields.get("velocity_world", player_shell_velocity)
	return velocity_world_value if velocity_world_value is Vector3 else player_shell_velocity


func build_agent_presentation_input(
	presentation_plan: Dictionary,
	intent_frame: Dictionary
) -> Dictionary:
	var normalized_intent_frame := CharacterControllerPortRef.normalize_intent_frame(intent_frame)
	var requested_action := get_intent_frame_action_name(normalized_intent_frame)
	return CharacterPresentationInputRef.from_agent_execution_plan(presentation_plan, requested_action)


func stage_agent_execution(presentation_plan: Dictionary, intent_frame: Dictionary) -> Dictionary:
	var normalized := build_agent_presentation_input(presentation_plan, intent_frame)
	set_agent_presentation_input(normalized)
	return normalized


func resolve_focus_target_lookup(focus_target_id: String) -> Dictionary:
	if focus_target_id.begins_with("char_"):
		return {
			"property_name": "actor_id",
			"expected": focus_target_id,
		}
	if focus_target_id.begins_with("obj_"):
		return {
			"property_name": "object_id",
			"expected": focus_target_id,
		}
	if focus_target_id.begins_with("env_"):
		return {
			"property_name": "environment_id",
			"expected": focus_target_id,
		}
	return {}


func build_agent_role_state_effects(
	dialogue_role_state: String,
	interaction_role_state: String,
	focus_role_state: String,
	attention_role_state: String,
) -> Array[Dictionary]:
	var effects: Array[Dictionary] = []
	var contact_phase := CharacterPresentationInputRef.get_contact_phase(agent_presentation_input)
	if contact_phase == "greeting":
		effects.append({
			"source": "contact_phase",
			"state_name": "greeting_nod",
		})
	var expression_hint := CharacterPresentationInputRef.get_expression_hint(agent_presentation_input)
	if not expression_hint.is_empty():
		effects.append({
			"source": "expression_hint",
			"state_name": map_requested_action_to_role_state(
				expression_hint,
				dialogue_role_state,
				interaction_role_state,
				focus_role_state,
				attention_role_state,
			),
		})
	var action_state := CharacterPresentationInputRef.get_action_state(agent_presentation_input)
	var requested_action := CharacterPresentationInputRef.get_requested_action(agent_presentation_input)
	if not requested_action.is_empty():
		effects.append({
			"source": "action_state",
			"state_name": map_requested_action_to_role_state(
				requested_action,
				dialogue_role_state,
				interaction_role_state,
				focus_role_state,
				attention_role_state,
			),
		})
	return effects


func map_requested_action_to_role_state(
	action_name: String,
	dialogue_role_state: String,
	interaction_role_state: String,
	focus_role_state: String,
	attention_role_state: String,
) -> String:
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


func build_agent_execution_side_effect_plan(
	dialogue_role_state: String,
	interaction_role_state: String,
	focus_role_state: String,
	attention_role_state: String,
) -> Dictionary:
	return {
		"focus_target_lookup": resolve_focus_target_lookup(CharacterPresentationInputRef.get_focus_target_id(agent_presentation_input)),
		"contact_phase": CharacterPresentationInputRef.get_contact_phase(agent_presentation_input),
		"execution_semantics": CharacterPresentationInputRef.get_execution_semantics(agent_presentation_input),
		"physiology_hint": CharacterPresentationInputRef.get_physiology_hint(agent_presentation_input),
		"active_command_type": CharacterPresentationInputRef.get_active_command_type(agent_presentation_input),
		"role_state_effects": build_agent_role_state_effects(
			dialogue_role_state,
			interaction_role_state,
			focus_role_state,
			attention_role_state,
		),
	}


func get_execution_side_effect_focus_target_lookup(execution_side_effect_plan: Dictionary) -> Dictionary:
	return get_execution_side_effect_focus_target_lookup_payload(execution_side_effect_plan)


func get_execution_side_effect_physiology_hint(execution_side_effect_plan: Dictionary) -> String:
	return str(get_execution_side_effect_physiology_hint_payload(execution_side_effect_plan))


func get_execution_side_effect_active_command_type(execution_side_effect_plan: Dictionary) -> String:
	return str(get_execution_side_effect_active_command_type_payload(execution_side_effect_plan))


func get_execution_side_effect_contact_phase(execution_side_effect_plan: Dictionary) -> String:
	return str(get_execution_side_effect_contact_phase_payload(execution_side_effect_plan))


func get_execution_side_effect_execution_semantics(execution_side_effect_plan: Dictionary) -> Dictionary:
	var value: Variant = get_execution_side_effect_execution_semantics_payload(execution_side_effect_plan)
	if value is Dictionary:
		return value
	return {}


func get_execution_side_effect_role_state_effects(execution_side_effect_plan: Dictionary) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var value: Variant = get_execution_side_effect_role_state_effects_payload(execution_side_effect_plan)
	if value is Array:
		for entry in value:
			if entry is Dictionary:
				result.append(entry)
	return result


func get_role_state_effect_name(effect: Dictionary) -> String:
	return str(effect.get("state_name", ""))


func get_target_lookup_property_name(lookup: Dictionary) -> String:
	return str(get_target_lookup_property_name_payload(lookup))


func get_target_lookup_expected(lookup: Dictionary) -> String:
	return str(get_target_lookup_expected_payload(lookup))


func get_execution_side_effect_focus_target_lookup_payload(execution_side_effect_plan: Dictionary) -> Variant:
	return execution_side_effect_plan.get("focus_target_lookup", {})


func get_execution_side_effect_physiology_hint_payload(execution_side_effect_plan: Dictionary) -> Variant:
	return execution_side_effect_plan.get("physiology_hint", "")


func get_execution_side_effect_active_command_type_payload(execution_side_effect_plan: Dictionary) -> Variant:
	return execution_side_effect_plan.get("active_command_type", "")


func get_execution_side_effect_contact_phase_payload(execution_side_effect_plan: Dictionary) -> Variant:
	return execution_side_effect_plan.get("contact_phase", "")


func get_execution_side_effect_execution_semantics_payload(execution_side_effect_plan: Dictionary) -> Variant:
	return execution_side_effect_plan.get("execution_semantics", {})


func get_execution_side_effect_role_state_effects_payload(execution_side_effect_plan: Dictionary) -> Variant:
	return execution_side_effect_plan.get("role_state_effects", [])


func get_target_lookup_property_name_payload(lookup: Dictionary) -> Variant:
	return lookup.get("property_name", "")


func get_target_lookup_expected_payload(lookup: Dictionary) -> Variant:
	return lookup.get("expected", "")


func get_command_target_position(payload: Dictionary) -> Variant:
	return payload.get("target_position", null)


func get_payload_string(payload: Dictionary, key: String, fallback: String = "") -> String:
	var value: Variant = payload.get(key, fallback)
	if value == null:
		return fallback
	return str(value)


func get_payload_actor_id(payload: Dictionary) -> String:
	return str(payload.get("actor_id", ""))


func get_payload_target_actor_id(payload: Dictionary) -> String:
	return str(payload.get("target_actor_id", "") or "")


func get_payload_target_object_id(payload: Dictionary) -> String:
	return str(payload.get("target_object_id", "") or "")


func get_payload_target_environment_id(payload: Dictionary) -> String:
	return str(payload.get("target_environment_id", "") or "")


func is_dialogue_payload_for_actor(payload: Dictionary, current_actor_id: String) -> bool:
	return get_payload_actor_id(payload) == current_actor_id


func is_siming_output_for_actor(payload: Dictionary, current_actor_id: String) -> bool:
	return get_payload_target_actor_id(payload) == current_actor_id


func is_runtime_state_payload_for_actor(payload: Dictionary, current_actor_id: String) -> bool:
	return get_payload_actor_id(payload) == current_actor_id


func should_sync_emitter_actor_id(emitter: Node, current_actor_id: String) -> bool:
	if emitter == null:
		return false
	return emitter.get("actor_id") != current_actor_id


func get_line_of_sight_hit_collider(hit: Dictionary) -> Variant:
	return hit.get("collider", null)


func execution_payload_targets_actor(payload: Dictionary, current_actor_id: String) -> bool:
	return get_payload_actor_id(payload) == current_actor_id


func build_agent_intent_frame(actor_id: String, first_frame: Dictionary) -> Dictionary:
	return CharacterControllerPortRef.normalize_intent_frame(
		AgentControllerAdapterRef.build_intent_frame(actor_id, first_frame)
	)


func get_execution_payload_actor_control_frames(payload: Dictionary) -> Array:
	var value: Variant = payload.get("actor_control_frames", [])
	if value is Array:
		return value
	return []


func get_execution_payload_first_frame_from_payload(payload: Dictionary) -> Dictionary:
	return get_execution_payload_first_frame(get_execution_payload_actor_control_frames(payload))


func get_execution_payload_intent_frame(payload: Dictionary, actor_id: String) -> Dictionary:
	var first_frame := get_execution_payload_first_frame_from_payload(payload)
	if first_frame.is_empty():
		return {}
	return build_agent_intent_frame(actor_id, first_frame)


func get_execution_payload_first_frame(actor_control_frames: Array) -> Dictionary:
	if actor_control_frames.is_empty():
		return {}
	var first_frame: Variant = actor_control_frames[0]
	if first_frame is Dictionary:
		return first_frame
	return {}


func get_execution_payload_presentation_plan(payload: Dictionary) -> Dictionary:
	var value: Variant = payload.get("presentation_plan", {})
	if value is Dictionary:
		return value
	return {}


func get_runtime_nearby_actor_refs_payload(payload: Dictionary) -> Variant:
	return payload.get("nearby_actor_refs", [])


func get_runtime_nearby_object_refs_payload(payload: Dictionary) -> Variant:
	return payload.get("nearby_object_refs", [])


func get_runtime_nearby_environment_refs_payload(payload: Dictionary) -> Variant:
	return payload.get("nearby_environment_refs", [])


func get_runtime_conversation_candidate_refs_payload(payload: Dictionary) -> Variant:
	return payload.get("conversation_candidate_refs", [])


func apply_runtime_state_payload(payload: Dictionary) -> void:
	runtime_focus_target = _read_runtime_string(payload, "current_focus_target", runtime_focus_target)
	runtime_attention_source = _read_runtime_string(payload, "current_attention_source", runtime_attention_source)
	if payload.has("nearby_actor_refs"):
		runtime_nearby_actor_refs = _read_runtime_string_array(get_runtime_nearby_actor_refs_payload(payload))
	if payload.has("nearby_object_refs"):
		runtime_nearby_object_refs = _read_runtime_string_array(get_runtime_nearby_object_refs_payload(payload))
	if payload.has("nearby_environment_refs"):
		runtime_nearby_environment_refs = _read_runtime_string_array(get_runtime_nearby_environment_refs_payload(payload))
	if payload.has("conversation_candidate_refs"):
		runtime_conversation_candidate_refs = _read_runtime_string_array(get_runtime_conversation_candidate_refs_payload(payload))
	runtime_engagement_pressure = _read_runtime_string(payload, "engagement_pressure", runtime_engagement_pressure)
	runtime_privacy_risk_hint = _read_runtime_string(payload, "privacy_risk_hint", runtime_privacy_risk_hint)


func set_active_command(command_type: String, priority: int) -> void:
	active_command_type = command_type
	active_command_priority = priority


func clear_active_command() -> void:
	active_command_type = ""
	active_command_priority = 0


func get_intent_frame_action_name(intent_frame: Dictionary) -> String:
	return CharacterControllerPortRef.get_action_name(intent_frame)


func get_active_command_type() -> String:
	return active_command_type


func get_active_command_priority() -> int:
	return active_command_priority


func get_runtime_focus_target() -> String:
	return runtime_focus_target


func get_runtime_attention_source() -> String:
	return runtime_attention_source


func get_runtime_nearby_environment_refs() -> Array[String]:
	return runtime_nearby_environment_refs


func get_runtime_conversation_candidate_refs() -> Array[String]:
	return runtime_conversation_candidate_refs


func get_execution_semantics_movement_intent(execution_semantics: Dictionary) -> String:
	return str(execution_semantics.get("movement_intent", ""))


func should_apply_focus_attention(payload: Dictionary, current_actor_id: String, reacts_to_player_focus: bool) -> bool:
	if not reacts_to_player_focus:
		return false
	if get_payload_actor_id(payload) != "char_c":
		return false
	return get_payload_target_actor_id(payload) == current_actor_id


func resolve_attention_target_ref(payload: Dictionary) -> String:
	var target_environment_id := get_payload_target_environment_id(payload)
	if target_environment_id != "":
		return target_environment_id
	var target_object_id := get_payload_target_object_id(payload)
	if target_object_id != "":
		return target_object_id
	return get_payload_target_actor_id(payload)


func should_highlight_focus(
	is_focused: bool,
	focus_attention_visual_timer: float,
	runtime_attention_source_value: String,
	runtime_nearby_environment_refs_value: Array[String],
) -> bool:
	var environment_attention: bool = (
		runtime_nearby_environment_refs_value.size() > 0
		and runtime_attention_source_value == "visual_fact"
	)
	return (
		is_focused
		or focus_attention_visual_timer > 0.0
		or runtime_attention_source_value == "focus_state"
		or runtime_attention_source_value == "visual_fact"
		or environment_attention
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
