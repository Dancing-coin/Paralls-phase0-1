extends RefCounted

class_name CharacterPresentationInput


const PRESENTATION_INPUT_KEYS := {
	"motion_state": true,
	"focus_state": true,
	"action_state": true,
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
		"equipment_state": candidate.get("equipment_state", {}),
		"expression_hint": candidate.get("expression_hint", ""),
		"physiology_hint": candidate.get("physiology_hint", ""),
		"speech_state": candidate.get("speech_state", {}),
	}
