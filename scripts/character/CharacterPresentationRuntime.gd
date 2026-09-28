extends RefCounted
class_name CharacterPresentationRuntime

var animation_controller: Node

func bind(controller: Node) -> void:
	animation_controller = controller

func apply_presentation_input(input: Dictionary) -> Dictionary:
	if animation_controller == null or not animation_controller.has_method("apply_presentation_state"):
		return {"accepted": false, "state": "idle", "reason": "controller_missing"}
	var motion: Dictionary = input.get("motion_state", {}) if input.get("motion_state", {}) is Dictionary else {}
	var action: Dictionary = input.get("action_state", {}) if input.get("action_state", {}) is Dictionary else {}
	var gait := str(motion.get("gait_actual", "idle"))
	var requested := str(action.get("requested_action", ""))
	return animation_controller.apply_presentation_state({
		"locomotion_intent": gait,
		"action_id": requested,
		"guard_hold": bool(action.get("guard_hold", false)),
		"cancel": bool(action.get("cancel", false)),
		"hold_position": float(action.get("hold_position", 0.34)),
	})
