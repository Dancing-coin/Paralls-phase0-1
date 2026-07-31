extends Node

const REPLAY_SCENE := preload("res://scenes/phase0/ThroneHallWalkPreview.tscn")
const REPLAY_SCENE_ASSET := "res://scenes/phase0/ThroneHallWalkPreview.tscn"
const REPLAY_CAPTURE_PATH := ".harness/verification/vla-replay-thronehall-walk-preview.png"
const REPLAY_REPORT_PATH := ".harness/verification/vla-replay-thronehall-walk-preview.json"
const VISUAL_PROVIDER := preload("res://scripts/character/VisualPatchProvider.gd")


func _ready() -> void:
	call_deferred("_capture")


func _capture() -> void:
	var replay_scene := REPLAY_SCENE.instantiate()
	add_child(replay_scene)
	var camera := _find_first_camera(replay_scene)
	if camera == null:
		push_error("vla_replay_second_scene_capture:missing_camera")
		get_tree().quit(1)
		return
	camera.make_current()
	await get_tree().process_frame
	await get_tree().process_frame

	var visual_provider = VISUAL_PROVIDER.new()
	var viewport_image := get_viewport().get_texture().get_image()
	var render_status := "meaningful" if _has_meaningful_pixels(viewport_image) else "blank_or_flat"
	var artifact_ref: String = visual_provider.write_viewport_capture_artifact(
		get_viewport(),
		REPLAY_CAPTURE_PATH
	)
	var report := {
		"status": "godot-runtime-replay-capture-verified" if artifact_ref != "" and render_status == "meaningful" else "godot-runtime-replay-capture-invalid",
		"scene_asset": REPLAY_SCENE_ASSET,
		"camera_path": str(camera.get_path()),
		"artifact_ref": artifact_ref,
		"render_status": render_status,
	}
	var report_path := _write_json(REPLAY_REPORT_PATH, report)
	print("vla_replay_second_scene_capture:report=%s" % report_path)
	print("vla_replay_second_scene_capture:artifact=%s" % artifact_ref)
	get_tree().quit(0 if artifact_ref != "" and render_status == "meaningful" else 1)


func _find_first_camera(root: Node) -> Camera3D:
	if root is Camera3D:
		return root as Camera3D
	for child: Node in root.get_children():
		var found := _find_first_camera(child)
		if found != null:
			return found
	return null


func _has_meaningful_pixels(image: Image) -> bool:
	if image == null or image.get_width() < 2 or image.get_height() < 2:
		return false
	var min_red := 255
	var max_red := 0
	var min_green := 255
	var max_green := 0
	var min_blue := 255
	var max_blue := 0
	for x in range(1, 16):
		for y in range(1, 10):
			var pixel := image.get_pixel(int(image.get_width() * x / 16), int(image.get_height() * y / 10))
			var red := int(pixel.r * 255.0)
			var green := int(pixel.g * 255.0)
			var blue := int(pixel.b * 255.0)
			min_red = min(min_red, red)
			max_red = max(max_red, red)
			min_green = min(min_green, green)
			max_green = max(max_green, green)
			min_blue = min(min_blue, blue)
			max_blue = max(max_blue, blue)
			if max_red - min_red >= 16 or max_green - min_green >= 16 or max_blue - min_blue >= 16:
				return true
	return false


func _write_json(relative_path: String, payload: Dictionary) -> String:
	var path := ProjectSettings.globalize_path("res://" + relative_path)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return ""
	file.store_string(JSON.stringify(payload, "\t"))
	file.close()
	return path
