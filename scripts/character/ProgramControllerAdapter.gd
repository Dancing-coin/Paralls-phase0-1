extends RefCounted

class_name ProgramControllerAdapter

const CharacterControllerPortRef = preload("res://scripts/character/CharacterControllerPort.gd")
const CharacterControlModeRef = preload("res://scripts/character/CharacterControlMode.gd")


static func build_intent_frame(actor_id: String, candidate: Dictionary) -> Dictionary:
	var next_frame := {
		"actor_id": actor_id,
		"controller_source": "program",
		"control_mode": CharacterControlModeRef.PROGRAM_CONTROLLED,
	}
	for key in candidate.keys():
		next_frame[key] = candidate[key]
	next_frame["actor_id"] = actor_id
	next_frame["controller_source"] = "program"
	next_frame["control_mode"] = CharacterControlModeRef.PROGRAM_CONTROLLED
	return CharacterControllerPortRef.normalize_intent_frame(next_frame)
