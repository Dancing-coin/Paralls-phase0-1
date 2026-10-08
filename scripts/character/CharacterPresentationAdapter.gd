extends Node3D

class_name CharacterPresentationAdapter

## Stable presentation contract consumed by CharacterActor.
## Concrete model packages may implement only the capabilities they support.

func configure_role(_actor_id: String) -> void:
	pass

func set_state(_state_name: String) -> void:
	pass

func set_motion_profile(_state_name: String, _profile_name: String) -> void:
	pass

func apply_presentation_input(_input: Dictionary) -> Dictionary:
	return {"accepted": false, "reason": "presentation_input_unsupported"}

func play_semantic_action(_semantic_action_id: String, _state_name: String, _profile_name: String, _playback_speed: float = 1.0, _realization: Dictionary = {}) -> Dictionary:
	return {"playback_accepted": false, "reason": "semantic_action_unsupported"}

func play_qualified_profile(_profile: Dictionary) -> Dictionary:
	return {"accepted": false, "reason": "qualified_profile_unsupported"}

func resolve_motion_realization(_semantic_action_id: String) -> Dictionary:
	return {"accepted": false, "reason": "motion_realization_unsupported"}

func consume_root_motion_delta() -> Vector3:
	return Vector3.ZERO

func reset_root_motion() -> void:
	pass

func get_root_motion_policy() -> String:
	return "hold"

func set_focus_highlight(_is_focused: bool) -> void:
	pass
