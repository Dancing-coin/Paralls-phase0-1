extends RefCounted

class_name CharacterLocomotionExecutionMode


const PHYSICS := "physics"
const ROOT_MOTION := "root_motion"
const HYBRID := "hybrid"


static func is_valid(mode: String) -> bool:
	return mode == PHYSICS or mode == ROOT_MOTION or mode == HYBRID
