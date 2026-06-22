extends Node


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey):
		return
	var key_event := event as InputEventKey
	if not key_event.pressed:
		return
	var state := _get_state()
	if state == null:
		return
	if key_event.keycode == KEY_F6:
		state.set_observatory_enabled(not state.observatory_enabled)
	elif key_event.keycode == KEY_F7:
		state.set_director_mode(not state.director_mode)
	elif key_event.keycode == KEY_F8:
		state.set_script_mode(not state.script_mode)
	elif key_event.keycode == KEY_TAB and key_event.shift_pressed:
		state.cycle_actor(-1)
	elif key_event.keycode == KEY_TAB:
		state.cycle_actor(1)
	elif key_event.keycode == KEY_SPACE:
		state.set_freeze_mode(not state.freeze_mode)
	elif key_event.keycode == KEY_ESCAPE:
		state.set_freeze_mode(false)


func select_actor_by_click(actor_id: String) -> void:
	var state := _get_state()
	if state == null:
		return
	state.set_selected_actor(actor_id)


func _get_state() -> Node:
	return get_node_or_null("../CharacterDirectorState")
