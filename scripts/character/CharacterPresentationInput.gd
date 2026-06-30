extends RefCounted

class_name CharacterPresentationInput


const PRESENTATION_INPUT_KEYS := {
	"motion_state": true,
	"focus_state": true,
	"action_state": true,
	"contact_phase": true,
	"execution_semantics": true,
	"equipment_state": true,
	"expression_hint": true,
	"physiology_hint": true,
	"speech_state": true,
}


static func normalize(candidate: Dictionary) -> Dictionary:
	return {
		"motion_state": candidate.get("motion_state", {}),
		"focus_state": candidate.get("focus_state", {}),
		"action_state": candidate.get("action_state", {}),
		"contact_phase": candidate.get("contact_phase", ""),
		"execution_semantics": candidate.get("execution_semantics", {}),
		"equipment_state": candidate.get("equipment_state", {}),
		"expression_hint": candidate.get("expression_hint", ""),
		"physiology_hint": candidate.get("physiology_hint", ""),
		"speech_state": candidate.get("speech_state", {}),
	}


static func get_motion_state(contract: Dictionary) -> Dictionary:
	return normalize(contract).get("motion_state", {})


static func get_motion_move_local_actual(contract: Dictionary) -> Vector2:
	var motion_state := get_motion_state(contract)
	var value: Variant = motion_state.get("move_local_actual", Vector2.ZERO)
	return value if value is Vector2 else Vector2.ZERO


static func get_motion_velocity_world(contract: Dictionary) -> Vector3:
	var motion_state := get_motion_state(contract)
	var value: Variant = motion_state.get("velocity_world", Vector3.ZERO)
	return value if value is Vector3 else Vector3.ZERO


static func get_motion_gait_actual(contract: Dictionary) -> String:
	var motion_state := get_motion_state(contract)
	return str(motion_state.get("gait_actual", "walk"))


static func get_focus_state(contract: Dictionary) -> Dictionary:
	return normalize(contract).get("focus_state", {})


static func get_focus_target_id(contract: Dictionary) -> String:
	return str(get_focus_state(contract).get("target_id", ""))


static func get_action_state(contract: Dictionary) -> Dictionary:
	return normalize(contract).get("action_state", {})


static func get_requested_action(contract: Dictionary) -> String:
	return str(get_action_state(contract).get("requested_action", ""))


static func get_action_gait_hint(contract: Dictionary, fallback: String = "") -> String:
	return str(get_action_state(contract).get("gait_hint", fallback))


static func get_contact_phase(contract: Dictionary) -> String:
	return str(normalize(contract).get("contact_phase", ""))


static func get_execution_semantics(contract: Dictionary) -> Dictionary:
	return normalize(contract).get("execution_semantics", {})


static func get_equipment_state(contract: Dictionary) -> Dictionary:
	return normalize(contract).get("equipment_state", {})


static func get_equipment_gait_hint(contract: Dictionary) -> String:
	return str(get_equipment_state(contract).get("gait_hint", ""))


static func get_speech_state(contract: Dictionary) -> Dictionary:
	return normalize(contract).get("speech_state", {})


static func get_active_command_type(contract: Dictionary) -> String:
	return str(get_speech_state(contract).get("active_command_type", ""))


static func get_expression_hint(contract: Dictionary) -> String:
	return str(normalize(contract).get("expression_hint", ""))


static func get_physiology_hint(contract: Dictionary) -> String:
	return str(normalize(contract).get("physiology_hint", ""))


static func from_player_runtime_state(
	player_motion_state: Dictionary,
	runtime_focus_target: String,
	requested_action: String,
	action_override_state: String,
	last_physiology_state_fact: String,
	active_command_type: String,
) -> Dictionary:
	return normalize(
		{
			"motion_state": player_motion_state.duplicate(true),
			"focus_state": {
				"target_id": runtime_focus_target,
			},
			"action_state": {
				"requested_action": requested_action,
				"override_state": action_override_state,
			},
			"contact_phase": "",
			"execution_semantics": {},
			"equipment_state": {},
			"physiology_hint": last_physiology_state_fact,
			"speech_state": {
				"active_command_type": active_command_type,
			},
		}
	)


static func from_agent_execution_plan(presentation_plan: Dictionary, requested_action: String) -> Dictionary:
	var target_ref := str(presentation_plan.get("target_ref", ""))
	var speech_state: Dictionary = presentation_plan.get("speech_state", {})
	var action_state: Dictionary = presentation_plan.get("action_state", {})
	var focus_state: Dictionary = presentation_plan.get("focus_state", {})
	if focus_state.is_empty() and not target_ref.is_empty():
		focus_state = {
			"target_id": target_ref,
		}
	if action_state.is_empty():
		action_state = {
			"requested_action": requested_action,
			"override_state": "",
		}
	return normalize(
		{
			"motion_state": presentation_plan.get("motion_state", {}),
			"focus_state": focus_state,
			"action_state": action_state,
			"contact_phase": presentation_plan.get("contact_phase", ""),
			"execution_semantics": presentation_plan.get("execution_semantics", {}),
			"equipment_state": presentation_plan.get("equipment_state", {}),
			"expression_hint": presentation_plan.get("expression_hint", ""),
			"physiology_hint": presentation_plan.get("physiology_hint", ""),
			"speech_state": speech_state,
		}
	)
