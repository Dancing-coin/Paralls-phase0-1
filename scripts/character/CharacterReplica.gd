extends CharacterActor
class_name CharacterReplica

signal compatibility_call(diagnostic: Dictionary)

var compatibility_strict_mode := false
var compatibility_call_count := 0
var compatibility_call_diagnostics: Array[Dictionary] = []
const COMPATIBILITY_DIAGNOSTIC_HISTORY_LIMIT := 128


func begin_embodied_control_frame(world_position: Vector3, move_direction: Vector3, look_target: Vector3, is_grounded: bool, wants_run: bool, gait_name: String, stance_name: String, jump_type: String) -> void:
	var intent := CharacterControlIntentRef.normalize({
		"move_direction": move_direction,
		"wants_run": wants_run,
		"gait": gait_name,
		"stance": stance_name,
		"jump_type": jump_type,
		"source_kind": "compatibility",
		"actor_id": actor_id,
	})
	_record_compatibility_call("begin_embodied_control_frame", intent, "CharacterActor.apply_control_intent")
	apply_control_intent(intent, {"world_position": world_position, "look_target": look_target, "is_grounded": is_grounded})


func apply_embodied_pose_sync(world_position: Vector3, planar_velocity: Vector3, look_target: Vector3, is_grounded: bool, player_motion_state: Dictionary = {}) -> void:
	var intent := CharacterControlIntentRef.normalize({
		"move_direction": planar_velocity,
		"wants_run": planar_velocity.length() > player_run_speed_threshold,
		"jump_type": runtime_state.get_player_jump_type(),
		"action_id": runtime_state.get_requested_action(),
		"source_kind": "compatibility",
		"actor_id": actor_id,
	})
	_record_compatibility_call("apply_embodied_pose_sync", intent, "CharacterActor.apply_compatibility_pose_sync")
	apply_compatibility_pose_sync(intent, {"world_position": world_position, "planar_velocity": planar_velocity, "look_target": look_target, "is_grounded": is_grounded, "player_motion_state": player_motion_state})


func clear_embodied_control_frame() -> void:
	_record_compatibility_call("clear_embodied_control_frame", {}, "CharacterActor.clear_embodied_control_frame")
	super.clear_embodied_control_frame()


func consume_player_root_motion_request(delta: float) -> Vector3:
	_record_compatibility_call("consume_player_root_motion_request", {}, "CharacterActor.consume_player_root_motion_request")
	return super.consume_player_root_motion_request(delta)


func perform_action(action_name: String) -> void:
	var intent := CharacterControlIntentRef.normalize({"action_id": action_name, "source_kind": "compatibility", "actor_id": actor_id})
	_record_compatibility_call("perform_action", intent, "CharacterActor.perform_compatibility_action")
	perform_compatibility_action(intent)


func play_reviewed_action_atom(action_tag: String, animation_clip_ref: String, phase: String) -> Dictionary:
	var request := {"action_tag": action_tag, "animation_clip_ref": animation_clip_ref, "phase": phase}
	_record_compatibility_call("play_reviewed_action_atom", request, "CharacterActor.play_compatibility_reviewed_action_atom")
	return play_compatibility_reviewed_action_atom(request)


func restore_reviewed_action_playback() -> void:
	_record_compatibility_call("restore_reviewed_action_playback", {}, "CharacterActor.restore_compatibility_reviewed_action_playback")
	restore_compatibility_reviewed_action_playback()


func apply_presentation_asset_binding(binding: Dictionary) -> bool:
	_record_compatibility_call("apply_presentation_asset_binding", binding, "CharacterActor.apply_compatibility_presentation_asset_binding")
	return apply_compatibility_presentation_asset_binding(binding)


func get_embodied_forward_vector() -> Vector3:
	_record_compatibility_call("get_embodied_forward_vector", {}, "CharacterActor.get_embodied_forward_vector")
	return super.get_embodied_forward_vector()


func is_embodied_control_active() -> bool:
	_record_compatibility_call("is_embodied_control_active", {}, "CharacterActor.is_embodied_control_active")
	return super.is_embodied_control_active()


func get_embodied_anchor_position() -> Vector3:
	_record_compatibility_call("get_embodied_anchor_position", {}, "CharacterActor.get_embodied_anchor_position")
	return super.get_embodied_anchor_position()


func set_visual_shell_visible(is_visible: bool) -> void:
	_record_compatibility_call("set_visual_shell_visible", {}, "CharacterActor.set_visual_shell_visible")
	super.set_visual_shell_visible(is_visible)


func begin_right_hand_reach(anchor_world_position: Vector3, tolerance_m: float) -> Dictionary:
	_record_compatibility_call("begin_right_hand_reach", {}, "CharacterActor.begin_right_hand_reach")
	return super.begin_right_hand_reach(anchor_world_position, tolerance_m)


func begin_right_hand_modifier_reach(anchor_world_position: Vector3, tolerance_m: float) -> Dictionary:
	_record_compatibility_call("begin_right_hand_modifier_reach", {}, "CharacterActor.begin_right_hand_modifier_reach")
	return super.begin_right_hand_modifier_reach(anchor_world_position, tolerance_m)


func begin_archive_door_reach_modifier(anchor_world_position: Vector3, tolerance_m: float) -> Dictionary:
	_record_compatibility_call("begin_archive_door_reach_modifier", {}, "CharacterActor.begin_archive_door_reach_modifier")
	return super.begin_archive_door_reach_modifier(anchor_world_position, tolerance_m)


func clear_right_hand_reach() -> void:
	_record_compatibility_call("clear_right_hand_reach", {}, "CharacterActor.clear_right_hand_reach")
	super.clear_right_hand_reach()


func measure_right_hand_to_anchor(anchor_world_position: Vector3) -> Dictionary:
	_record_compatibility_call("measure_right_hand_to_anchor", {}, "CharacterActor.measure_right_hand_to_anchor")
	return super.measure_right_hand_to_anchor(anchor_world_position)


func _record_compatibility_call(method: String, intent: Dictionary, forwarded_to: String) -> void:
	if compatibility_strict_mode:
		assert(_forbidden_shell_operations().is_empty(), "CharacterReplica compatibility shell owns forbidden runtime behavior")
	var caller_path := "unknown"
	for frame in get_stack():
		var source := str(frame.get("source", ""))
		if not source.is_empty() and not source.ends_with("/CharacterReplica.gd"):
			caller_path = source
			break
	var diagnostic := {
		"event": "compatibility_call",
		"caller_path": caller_path,
		"method": method,
		"actor_id": actor_id,
		"source_kind": "compatibility",
		"intent_digest": CharacterControlIntentRef.digest(intent),
		"forwarded_to": forwarded_to,
	}
	compatibility_call_count += 1
	compatibility_call_diagnostics.append(diagnostic)
	if compatibility_call_diagnostics.size() > COMPATIBILITY_DIAGNOSTIC_HISTORY_LIMIT:
		compatibility_call_diagnostics.pop_front()
	compatibility_call.emit(diagnostic)


func _forbidden_shell_operations(source_override: String = "") -> Array[String]:
	var source := source_override if not source_override.is_empty() else FileAccess.get_file_as_string("res://scripts/character/CharacterReplica.gd")
	var forbidden := RegEx.new()
	forbidden.compile("\\b(?:global_position|global_transform|position|transform|velocity)(?:\\.[xyz])?\\s*[+\\-*/]?=|\\bset_(?:global_position|global_transform|position|transform|velocity)\\s*\\(|move_and_slide\\s*\\(|\\b(?:animation_player|animation_state_playback|animation_tree|playback)\\.(?:play|travel|seek|set)\\s*\\(|\\b(?:animation_player|animation_tree|playback)\\[[^]]+\\]\\s*=|\\b(?:role_asset_scene|role_skin)\\.(?:set_state|set_motion_profile|play_reviewed_action_atom|restore_reviewed_action_playback)\\s*\\(|\\b(?:append_authority_event|submit_action_attempt|_emit_[A-Za-z_]*fact)\\s*\\(")
	var violations: Array[String] = []
	for line in source.split("\n"):
		if not line.strip_edges().begins_with("#") and forbidden.search(line) != null:
			violations.append(line)
	return violations
