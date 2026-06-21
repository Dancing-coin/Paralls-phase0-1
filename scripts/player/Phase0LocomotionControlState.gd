extends RefCounted

class_name Phase0LocomotionControlState


const STANCE_STAND := 0
const STANCE_CROUCH := 1
const GAIT_CYCLE := ["amble", "walk", "brisk_walk"]

var locomotion_gait_mode := 1
var locomotion_stance_mode := 0
var current_jump_type := "none"


func cycle_gait_mode() -> void:
	if locomotion_stance_mode == STANCE_CROUCH:
		return
	locomotion_gait_mode = (locomotion_gait_mode + 1) % GAIT_CYCLE.size()


func toggle_crouch_mode() -> void:
	if locomotion_stance_mode == STANCE_STAND:
		locomotion_stance_mode = STANCE_CROUCH
	else:
		locomotion_stance_mode = STANCE_STAND


func set_gait_mode_by_name(gait_name: String) -> void:
	var idx := GAIT_CYCLE.find(gait_name)
	if idx >= 0:
		locomotion_gait_mode = idx


func set_crouch_enabled(enabled: bool) -> void:
	locomotion_stance_mode = STANCE_CROUCH if enabled else STANCE_STAND


func resolve_stance_name() -> String:
	return "crouch" if locomotion_stance_mode == STANCE_CROUCH else "stand"


func resolve_gait_name(move_direction: Vector3, wants_run: bool) -> String:
	if locomotion_stance_mode == STANCE_CROUCH:
		return "crouch_walk" if move_direction.length() > 0.001 else "crouch_idle"
	if move_direction.length() <= 0.001:
		return GAIT_CYCLE[locomotion_gait_mode]
	if wants_run:
		return "run"
	return GAIT_CYCLE[locomotion_gait_mode]


func resolve_jump_type(
	is_on_floor: bool,
	move_direction: Vector3,
	wants_run: bool,
	requested_action: String,
	vertical_velocity: float,
) -> String:
	if is_on_floor:
		if requested_action.begins_with("jump") and move_direction.length() > 0.001:
			current_jump_type = "single_leg" if wants_run else "two_foot"
		elif current_jump_type != "none" and abs(vertical_velocity) > 0.001:
			return current_jump_type
		elif current_jump_type != "none":
			current_jump_type = "none"
	else:
		if current_jump_type == "none" and move_direction.length() > 0.001:
			current_jump_type = "single_leg" if wants_run else "two_foot"
	return current_jump_type
