extends Node

const REALTIME_SCENE := preload("res://scenes/phase0/StormnightRealtimePlayable.tscn")


func _ready() -> void:
	call_deferred("_capture")


func _capture() -> void:
	var scene := REALTIME_SCENE.instantiate()
	add_child(scene)
	_apply_capture_projection(scene)
	var player := scene.get_node_or_null("StormnightPlayer") as CharacterBody3D
	if player == null:
		push_error("stormnight_realtime_capture:player_missing")
		get_tree().quit(1)
		return
	var index := int(OS.get_environment("STORMNIGHT_CAPTURE_INDEX"))
	match index:
		1:
			player.position = Vector3(-4.0, 1.1, 5.0)
			player.rotation.y = 0.3
		2:
			player.position = Vector3(0.0, 1.1, 6.0)
			player.rotation.y = 0.0
		_:
			player.position = Vector3(2.0, 1.1, 8.0)
			player.rotation.y = -0.25
	var camera := Camera3D.new()
	add_child(camera)
	match index:
		1:
			camera.position = Vector3(0.0, 7.0, 16.0)
			camera.look_at(Vector3(0.0, 1.3, 0.0), Vector3.UP)
		2:
			camera.position = Vector3(-9.0, 5.0, 8.0)
			camera.look_at(Vector3(-2.0, 1.2, -1.8), Vector3.UP)
		_:
			camera.position = Vector3(9.0, 6.0, 7.0)
			camera.look_at(Vector3(0.0, 1.4, 1.5), Vector3.UP)
	camera.make_current()
	await get_tree().process_frame
	await get_tree().process_frame
	await get_tree().process_frame
	var relative := OS.get_environment("STORMNIGHT_CAPTURE_PATH")
	if relative.is_empty():
		relative = ".harness/verification/stormnight-realtime-playable-%s.png" % index
	var path := ProjectSettings.globalize_path("res://" + relative)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var image := get_viewport().get_texture().get_image()
	var error := image.save_png(path)
	print("stormnight_realtime_capture:path=%s" % path)
	get_tree().quit(0 if error == OK else 1)


func _apply_capture_projection(scene: Node) -> void:
	var configured_path := OS.get_environment("STORMNIGHT_CAPTURE_PROJECTION_PATH")
	if configured_path.is_empty() or not FileAccess.file_exists(configured_path):
		return
	var file := FileAccess.open(configured_path, FileAccess.READ)
	if file == null:
		return
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	file.close()
	if parsed is Dictionary and scene.has_method("_on_case_projection"):
		scene.call("_on_case_projection", parsed)
