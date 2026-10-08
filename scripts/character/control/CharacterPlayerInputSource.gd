extends Node

class_name CharacterPlayerInputSource

signal action_requested(action_id: String)
signal actor_switch_requested
signal jump_requested

@export var punch_action_id := "action:melee.unarmed_punch"
@export var alternate_action_id := "action:melee.sword_slash"

var move_direction := Vector3.ZERO
var wants_run := false

func sample() -> Dictionary:
	var input := Input.get_vector("phase0_move_left", "phase0_move_right", "phase0_move_forward", "phase0_move_backward")
	move_direction = Vector3(input.x, 0.0, input.y)
	if move_direction.length() > 1.0:
		move_direction = move_direction.normalized()
	wants_run = Input.is_action_pressed("phase0_run") or Input.is_key_pressed(KEY_SHIFT)
	return {"move_direction": move_direction, "wants_run": wants_run}

func handle_input(event: InputEvent) -> bool:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
		action_requested.emit(punch_action_id)
		return true
	if not event is InputEventKey or not event.pressed or event.echo:
		return false
	var key := event as InputEventKey
	match key.keycode:
		KEY_TAB:
			actor_switch_requested.emit()
			return true
		KEY_SPACE:
			jump_requested.emit()
			return true
		KEY_1:
			action_requested.emit(punch_action_id)
			return true
		KEY_Q, KEY_2:
			action_requested.emit(alternate_action_id)
			return true
	return false
