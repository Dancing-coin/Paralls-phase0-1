extends Node

const MAIN_DEMO_SCENE := preload("res://scenes/phase0/MainDemo.tscn")
const THRONE_HALL_SCENE := preload("res://scenes/phase0/ThroneHallWalkPreview.tscn")
const VISUAL_PROVIDER := preload("res://scripts/character/VisualPatchProvider.gd")


func _ready() -> void:
	call_deferred("_capture")


func _capture() -> void:
	var scene_key := OS.get_environment("VLA_COVERAGE_SCENE")
	var candidate_id := OS.get_environment("VLA_COVERAGE_CANDIDATE_ID")
	var capture_path := OS.get_environment("VLA_COVERAGE_CAPTURE_PATH")
	var report_path := OS.get_environment("VLA_COVERAGE_REPORT_PATH")
	var variant_index := int(OS.get_environment("VLA_COVERAGE_VARIANT_INDEX"))
	if candidate_id == "" or capture_path == "" or report_path == "" or not capture_path.begins_with(".harness/verification/") or not report_path.begins_with(".harness/verification/"):
		push_error("vla_replay_coverage_capture:invalid_environment")
		get_tree().quit(1)
		return
	var scene := MAIN_DEMO_SCENE.instantiate() if scene_key == "main_demo" else THRONE_HALL_SCENE.instantiate()
	add_child(scene)
	var camera := _find_first_camera(scene)
	if camera == null:
		push_error("vla_replay_coverage_capture:missing_camera")
		get_tree().quit(1)
		return
	_apply_variant(camera, variant_index)
	camera.make_current()
	await get_tree().process_frame
	await get_tree().process_frame

	var provider := VISUAL_PROVIDER.new()
	var image := get_viewport().get_texture().get_image()
	var meaningful := _has_meaningful_pixels(image)
	var artifact_ref := provider.write_viewport_capture_artifact(get_viewport(), capture_path)
	var report := {
		"status": "candidate_capture_ready" if meaningful and artifact_ref != "" else "candidate_capture_invalid",
		"candidate_id": candidate_id,
		"scene_key": scene_key,
		"scene_asset": "res://scenes/phase0/MainDemo.tscn" if scene_key == "main_demo" else "res://scenes/phase0/ThroneHallWalkPreview.tscn",
		"variant_index": variant_index,
		"artifact_ref": artifact_ref,
		"capture_path": capture_path,
		"camera_path": str(camera.get_path()),
		"camera_position": [camera.global_position.x, camera.global_position.y, camera.global_position.z],
		"camera_yaw_degrees": rad_to_deg(camera.global_rotation.y),
		"human_review_status": "pending_human_review",
	}
	_write_json(report_path, report)
	print("vla_replay_coverage_capture:candidate=%s status=%s" % [candidate_id, report["status"]])
	get_tree().quit(0 if report["status"] == "candidate_capture_ready" else 1)


func _apply_variant(camera: Camera3D, variant_index: int) -> void:
	var lateral := float((variant_index % 5) - 2) * 0.35
	var depth := float((variant_index / 5) - 1) * 0.35
	var yaw := float((variant_index % 5) - 2) * 4.0
	camera.global_position += Vector3(lateral, 0.0, depth)
	camera.rotate_y(deg_to_rad(yaw))


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


func _write_json(relative_path: String, payload: Dictionary) -> void:
	var path := ProjectSettings.globalize_path("res://" + relative_path)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(payload, "\t"))
		file.close()
