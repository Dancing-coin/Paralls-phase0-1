extends RefCounted

class_name Phase0ProgramControlState


var forced_move_direction := Vector3.ZERO
var forced_run_state := false
var forced_jump_request := ""


func set_forced_player_motion(world_direction: Vector3, wants_run: bool) -> void:
	forced_move_direction = Vector3(world_direction.x, 0.0, world_direction.z)
	if forced_move_direction.length() > 1.0:
		forced_move_direction = forced_move_direction.normalized()
	forced_run_state = wants_run


func clear_forced_player_motion() -> void:
	forced_move_direction = Vector3.ZERO
	forced_run_state = false


func queue_forced_jump(jump_type: String) -> void:
	forced_jump_request = jump_type


func consume_forced_jump_request() -> String:
	var next_jump := forced_jump_request
	forced_jump_request = ""
	return next_jump


func has_forced_move_direction() -> bool:
	return forced_move_direction.length() > 0.001
