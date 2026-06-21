extends RefCounted

class_name Phase0ViewAnchorResolver

const CharacterControllerPortRef = preload("res://scripts/character/CharacterControllerPort.gd")


func resolve_player_look_target(
	player: CharacterBody3D,
	program_control_state,
	current_intent_frame: Dictionary,
	desired_facing_yaw: float,
	find_camera_callable: Callable,
) -> Vector3:
	if program_control_state.has_forced_move_direction():
		return player.global_position + program_control_state.forced_move_direction.normalized()
	var normalized_frame := CharacterControllerPortRef.normalize_intent_frame(current_intent_frame)
	if _has_explicit_forward_intent(normalized_frame):
		return player.global_position + _forward_from_yaw(
			CharacterControllerPortRef.get_desired_facing_yaw(normalized_frame, desired_facing_yaw)
		)
	var character_c := _get_character_replica(player)
	if character_c is Node:
		if (character_c as Node).has_method("get_embodied_forward_vector"):
			var actor_forward: Variant = (character_c as Node).get_embodied_forward_vector()
			if actor_forward is Vector3 and (actor_forward as Vector3).length() > 0.001:
				return player.global_position + (actor_forward as Vector3).normalized()
	if player.has_method("get_visual_forward"):
		var wrapper_forward: Variant = player.get_visual_forward()
		if wrapper_forward is Vector3 and (wrapper_forward as Vector3).length() > 0.001:
			return player.global_position + (wrapper_forward as Vector3).normalized()
	var camera_holder := player.get_node_or_null("CameraHolder")
	if camera_holder is Node3D:
		return player.global_position - (camera_holder as Node3D).global_basis.z
	var camera_result: Variant = find_camera_callable.call()
	if camera_result is Camera3D:
		return player.global_position - (camera_result as Camera3D).global_basis.z
	return player.global_position - player.global_basis.z


func resolve_player_forward(
	player: CharacterBody3D,
	current_intent_frame: Dictionary,
	desired_facing_yaw: float,
	find_camera_callable: Callable,
) -> Vector3:
	var normalized_frame := CharacterControllerPortRef.normalize_intent_frame(current_intent_frame)
	if _has_explicit_forward_intent(normalized_frame):
		return _forward_from_yaw(
			CharacterControllerPortRef.get_desired_facing_yaw(normalized_frame, desired_facing_yaw)
		)
	var character_c := _get_character_replica(player)
	if character_c is Node:
		if (character_c as Node).has_method("get_embodied_forward_vector"):
			var actor_forward: Variant = (character_c as Node).get_embodied_forward_vector()
			if actor_forward is Vector3 and (actor_forward as Vector3).length() > 0.001:
				return (actor_forward as Vector3).normalized()
	if player.has_method("get_visual_forward"):
		var wrapper_forward: Variant = player.get_visual_forward()
		if wrapper_forward is Vector3 and (wrapper_forward as Vector3).length() > 0.001:
			return (wrapper_forward as Vector3).normalized()
	var camera_holder := player.get_node_or_null("CameraHolder")
	if camera_holder is Node3D:
		return -((camera_holder as Node3D).global_basis.z).normalized()
	var camera_result: Variant = find_camera_callable.call()
	if camera_result is Camera3D:
		return -(camera_result as Camera3D).global_basis.z.normalized()
	return -(player.global_basis.z).normalized()


func resolve_control_anchor_position(player: CharacterBody3D, character_c: Node) -> Vector3:
	if character_c and character_c.has_method("is_embodied_control_active") and character_c.is_embodied_control_active():
		if character_c.has_method("get_embodied_anchor_position"):
			return character_c.get_embodied_anchor_position()
		if character_c is Node3D:
			return (character_c as Node3D).global_position
	return player.global_position


func resolve_control_forward(player: CharacterBody3D, character_c: Node, look_target: Vector3, control_anchor_position: Vector3, fallback_forward: Vector3) -> Vector3:
	if character_c and character_c.has_method("is_embodied_control_active") and character_c.is_embodied_control_active():
		var forward: Vector3 = look_target - control_anchor_position
		forward.y = 0.0
		if forward.length() > 0.001:
			return forward.normalized()
		if character_c is Node3D:
			return -((character_c as Node3D).global_basis.z).normalized()
	return fallback_forward


func find_camera(player: CharacterBody3D) -> Camera3D:
	if player.has_method("get_camera"):
		var player_camera: Variant = player.get_camera()
		if player_camera is Camera3D:
			return player_camera as Camera3D
	var found := player.find_child("Camera3D", true, false)
	if found is Camera3D:
		return found as Camera3D
	return null


func _get_character_replica(player: CharacterBody3D) -> Node:
	if player.has_method("get_character_replica"):
		return player.get_character_replica()
	return null


func _forward_from_yaw(yaw: float) -> Vector3:
	return -Vector3.FORWARD.rotated(Vector3.UP, yaw).normalized()


func _has_explicit_forward_intent(normalized_frame: Dictionary) -> bool:
	return not CharacterControllerPortRef.get_actor_id(normalized_frame).is_empty()
