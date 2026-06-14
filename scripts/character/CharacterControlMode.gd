extends RefCounted

class_name CharacterControlMode


const HUMAN_CONTROLLED := "human_controlled"
const AGENT_CONTROLLED := "agent_controlled"
const PROGRAM_CONTROLLED := "program_controlled"

# Control-mode transitions switch controller source only.
# They do not replace the CharacterActor substrate.
const ALLOWED_TRANSITIONS := {
	HUMAN_CONTROLLED: [AGENT_CONTROLLED, PROGRAM_CONTROLLED],
	AGENT_CONTROLLED: [HUMAN_CONTROLLED, PROGRAM_CONTROLLED],
	PROGRAM_CONTROLLED: [HUMAN_CONTROLLED, AGENT_CONTROLLED],
}


static func is_valid(mode: String) -> bool:
	return mode == HUMAN_CONTROLLED or mode == AGENT_CONTROLLED or mode == PROGRAM_CONTROLLED


static func can_transition(from_mode: String, to_mode: String) -> bool:
	if from_mode == to_mode:
		return true
	if not ALLOWED_TRANSITIONS.has(from_mode):
		return false
	return to_mode in ALLOWED_TRANSITIONS[from_mode]
