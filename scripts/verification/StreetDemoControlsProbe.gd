extends SceneTree

var failures: Array[String] = []


func _init() -> void:
	call_deferred("_probe")


func _probe() -> void:
	var scene: Node3D = load("res://scenes/phase0/streetdemo.tscn").instantiate()
	root.add_child(scene)
	for _frame in 5:
		await physics_frame
	var actor: CharacterBody3D = scene.get_node("FemaleTExternal")
	var skin: Node3D = scene.get_node("FemaleTExternal/ImportedModel/StreetCharacterSkin")
	var forward := InputEventKey.new()
	forward.keycode = KEY_W
	forward.physical_keycode = KEY_W
	forward.pressed = true
	Input.parse_input_event(forward)
	for _frame in 40:
		await physics_frame
	var visual_forward: Vector3 = skin.global_transform.basis * Vector3.BACK
	var movement: Vector3 = actor.velocity.slide(Vector3.UP).normalized()
	_check("walk_faces_movement", movement.length() > 0.0 and visual_forward.dot(movement) > 0.8)

	var shift := InputEventKey.new()
	shift.keycode = KEY_SHIFT
	shift.physical_keycode = KEY_SHIFT
	shift.pressed = true
	Input.parse_input_event(shift)
	for _frame in 20:
		await physics_frame
	_check("shift_starts_run", Input.is_key_pressed(KEY_SHIFT) and skin.get_playback_state() == "run" and actor.velocity.length() > 3.0)
	print("streetdemo_controls_probe:failures=", failures)
	quit(0 if failures.is_empty() else 3)


func _check(name: String, passed: bool) -> void:
	print("streetdemo_controls_probe:", name, "=", passed)
	if not passed:
		failures.append(name)
