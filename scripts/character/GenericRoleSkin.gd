extends Node3D

class_name GenericRoleSkin

var actor_id := ""
var current_state := "idle"
var current_motion_profile := "default"
var current_action := ""
var focused := false
var presentation_input: Dictionary = {}

@onready var visual: Node3D = $GreyboxHumanoidVisual


func configure_role(next_actor_id: String) -> void:
	actor_id = next_actor_id
	if visual != null and visual.has_method("configure_visuals"):
		visual.configure_visuals(
			next_actor_id,
			_color_for_actor(next_actor_id),
			Color(0.78, 0.68, 0.58, 1.0),
			Color(0.18, 0.52, 0.82, 1.0),
			Color(1.0, 0.82, 0.25, 1.0)
		)


func set_state(next_state: String) -> void:
	current_state = next_state if not next_state.is_empty() else "idle"
	_apply_state_pose()


func set_motion_profile(state_name: String, profile_name: String) -> void:
	current_motion_profile = profile_name if not profile_name.is_empty() else "default"
	set_state(state_name)


func set_focus_highlight(is_focused: bool) -> void:
	focused = is_focused
	if visual != null and visual.has_method("set_focus_highlight"):
		visual.set_focus_highlight(is_focused)


func apply_presentation_input(next_input: Dictionary) -> void:
	presentation_input = next_input.duplicate(true)
	var requested_action := str(next_input.get("requested_action", ""))
	if not requested_action.is_empty():
		current_action = requested_action
		set_state(_state_for_action(requested_action))


func play_reviewed_action_atom(action_tag: String, animation_clip_ref: String, phase: String) -> Dictionary:
	current_action = action_tag
	set_state(_state_for_action(action_tag))
	return {
		"accepted": true,
		"presentation_mode": "generic_fallback",
		"action_tag": action_tag,
		"animation_clip_ref": animation_clip_ref,
		"phase": phase,
	}


func restore_reviewed_action_playback() -> void:
	current_action = ""
	set_state("idle")


func consume_root_motion_delta() -> Vector3:
	return Vector3.ZERO


func reset_root_motion() -> void:
	pass


func get_current_clip_name() -> String:
	return "generic:%s" % current_state


func get_current_motion_profile_name() -> String:
	return current_motion_profile


func begin_right_hand_reach(_anchor_world_position: Vector3, _tolerance_m: float) -> Dictionary:
	return {"accepted": false, "reason": "generic_fallback_has_no_skeleton"}


func begin_right_hand_modifier_reach(_anchor_world_position: Vector3, _tolerance_m: float) -> Dictionary:
	return {"accepted": false, "reason": "generic_fallback_has_no_skeleton"}


func begin_archive_door_reach_modifier(_anchor_world_position: Vector3, _tolerance_m: float) -> Dictionary:
	return {"accepted": false, "reason": "generic_fallback_has_no_skeleton"}


func clear_right_hand_reach() -> void:
	pass


func measure_right_hand_to_anchor(_anchor_world_position: Vector3) -> Dictionary:
	return {"accepted": false, "reason": "generic_fallback_has_no_skeleton"}


func apply_asset_binding(_binding: Dictionary) -> void:
	pass


func _apply_state_pose() -> void:
	if visual == null:
		return
	visual.rotation = Vector3.ZERO
	visual.scale = Vector3.ONE
	match current_state:
		"observe", "focus":
			visual.rotation.y = 0.18
		"alert":
			visual.rotation.z = -0.08
		"inspect", "interact", "speak":
			visual.position.y = 0.05
		"jump":
			visual.position.y = 0.2
		_:
			visual.position.y = 0.0


func _state_for_action(action_tag: String) -> String:
	match action_tag:
		"observe", "focus", "listen": return "observe"
		"speak", "dialogue": return "speak"
		"inspect", "interact", "read", "reach", "open", "close": return "inspect"
		"alert", "pursue", "attack": return "alert"
		"jump": return "jump"
		_: return "idle"


func _color_for_actor(next_actor_id: String) -> Color:
	match next_actor_id:
		"char_a": return Color(0.18, 0.45, 0.78, 1.0)
		"char_b": return Color(0.74, 0.26, 0.22, 1.0)
		"char_c": return Color(0.22, 0.65, 0.38, 1.0)
		_: return Color(0.48, 0.5, 0.56, 1.0)
