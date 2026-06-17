extends RefCounted

class_name Phase0CharacterShellSync


func sync_from_player_shell_pose(character_c: Node, world_position: Vector3, planar_velocity: Vector3, look_target: Vector3, is_grounded: bool, player_motion_state: Dictionary) -> void:
	if character_c == null:
		return
	if character_c.has_method("apply_embodied_pose_sync"):
		character_c.apply_embodied_pose_sync(world_position, planar_velocity, look_target, is_grounded, player_motion_state)
		return


func sync_player_control_frame(
	character_c: Node,
	world_position: Vector3,
	move_direction: Vector3,
	look_target: Vector3,
	is_grounded: bool,
	wants_run: bool,
	gait_name: String,
	stance_name: String,
	jump_type: String,
	delta: float,
) -> void:
	if character_c == null:
		return
	if character_c.has_method("begin_embodied_control_frame"):
		character_c.begin_embodied_control_frame(world_position, move_direction, look_target, is_grounded, wants_run, gait_name, stance_name, jump_type)
	else:
		return
	if character_c.has_method("consume_player_root_motion_request"):
		character_c.consume_player_root_motion_request(delta)


func clear_character_shell_frame(character_c: Node) -> void:
	if character_c and character_c.has_method("clear_embodied_control_frame"):
		character_c.clear_embodied_control_frame()
