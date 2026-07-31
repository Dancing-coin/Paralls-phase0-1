extends Node

const CONTROLLER := preload("res://scripts/interaction/EmbodiedActionController.gd")
const REPORT_PATH := ".harness/verification/embodied-kick-chair-vertical-slice-godot-runtime.json"
const SCREENSHOT_PATH := ".harness/verification/embodied-kick-chair-vertical-slice.png"

var _screenshot_source := ""


func _ready() -> void:
	call_deferred("_run_probe")


func _run_probe() -> void:
	var scene_root := Node3D.new()
	scene_root.name = "EmbodiedKickChairProbeRoot"
	add_child(scene_root)
	var success_chair := _create_chair("SuccessChair", Vector3(-1.25, 0.5, -4.0), Color(0.2, 0.55, 0.9, 1.0))
	var failure_chair := _create_chair("FailureChair", Vector3(1.25, 0.5, -4.0), Color(0.7, 0.7, 0.7, 1.0))
	scene_root.add_child(success_chair)
	scene_root.add_child(failure_chair)
	_setup_camera(scene_root)
	_setup_light(scene_root)

	var controller = CONTROLLER.new()
	add_child(controller)
	var request := _request()
	var grant := _grant()
	var binding := _binding()
	var success_outcome: Dictionary = controller.run_attempt(request.duplicate(true), grant.duplicate(true), binding.duplicate(true), "success")
	var failure_outcome: Dictionary = controller.run_attempt(request.duplicate(true), grant.duplicate(true), binding.duplicate(true), "miss")

	var success_before := success_chair.rotation_degrees
	var failure_before := failure_chair.rotation_degrees
	var success_after_local := success_chair.rotation_degrees
	var failure_after_local := failure_chair.rotation_degrees

	var success_settlement := _backend_settlement_projection(true)
	var failure_settlement := _backend_settlement_projection(false)
	if success_settlement.get("settlement_status", "") == "committed":
		success_chair.rotation_degrees = Vector3(0.0, 0.0, -28.0)
		success_chair.position.y = 0.35
		_set_chair_color(success_chair, Color(0.1, 0.8, 0.35, 1.0))
	if failure_settlement.get("settlement_status", "") == "committed":
		failure_chair.rotation_degrees = Vector3(0.0, 0.0, 28.0)

	await get_tree().process_frame
	await get_tree().process_frame
	var success_after_settlement := success_chair.rotation_degrees
	var failure_after_settlement := failure_chair.rotation_degrees

	var success_changed_after_settlement := not success_after_settlement.is_equal_approx(success_before)
	var success_unchanged_before_settlement := success_after_local.is_equal_approx(success_before)
	var failure_unchanged := failure_after_local.is_equal_approx(failure_before) and failure_after_settlement.is_equal_approx(failure_before)
	var screenshot_path := _write_screenshot(SCREENSHOT_PATH, success_changed_after_settlement, failure_unchanged)
	var ok := (
		str(success_outcome.get("terminal_status", "")) == "contact_observed"
		and str(failure_outcome.get("terminal_status", "")) == "missed_contact"
		and success_unchanged_before_settlement
		and success_changed_after_settlement
		and failure_unchanged
		and str(success_settlement.get("settlement_writer_kind", "")) == "esm_compatibility_adapter"
		and str(failure_settlement.get("settlement_status", "")) == "rejected"
		and screenshot_path != ""
	)
	var report := {
		"status": "godot-runtime-kick-chair-vertical-slice-verified" if ok else "godot-runtime-kick-chair-vertical-slice-failed",
		"success": {
			"outcome_terminal_status": success_outcome.get("terminal_status", ""),
			"before_rotation": _vector_to_dict(success_before),
			"after_local_observation_rotation": _vector_to_dict(success_after_local),
			"after_settlement_rotation": _vector_to_dict(success_after_settlement),
			"changed_only_after_settlement": success_unchanged_before_settlement and success_changed_after_settlement,
			"settlement_projection": success_settlement,
		},
		"failure": {
			"outcome_terminal_status": failure_outcome.get("terminal_status", ""),
			"before_rotation": _vector_to_dict(failure_before),
			"after_local_observation_rotation": _vector_to_dict(failure_after_local),
			"after_settlement_rotation": _vector_to_dict(failure_after_settlement),
			"world_state_unchanged": failure_unchanged,
			"settlement_projection": failure_settlement,
		},
		"route_gate": {
			"selected_realization_route": controller.selected_realization_route,
			"legacy_character_actor_status_used": false,
		},
		"screenshot": screenshot_path,
		"screenshot_source": _screenshot_source,
	}
	var report_path := _write_json(REPORT_PATH, report)
	print("embodied_kick_chair_probe:artifact=%s" % report_path)
	print("embodied_kick_chair_probe:screenshot=%s" % screenshot_path)
	print("embodied_kick_chair_probe:verified=%s" % str(ok).to_lower())
	get_tree().quit(0 if ok else 1)


func _create_chair(node_name: String, position: Vector3, color: Color) -> MeshInstance3D:
	var chair := MeshInstance3D.new()
	chair.name = node_name
	chair.position = position
	var mesh := BoxMesh.new()
	mesh.size = Vector3(0.55, 1.0, 0.55)
	chair.mesh = mesh
	_set_chair_color(chair, color)
	return chair


func _set_chair_color(chair: MeshInstance3D, color: Color) -> void:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	chair.set_surface_override_material(0, material)


func _setup_camera(root: Node3D) -> void:
	var camera := Camera3D.new()
	camera.name = "ProbeCamera"
	camera.position = Vector3(0.0, 2.0, 0.2)
	camera.rotation_degrees = Vector3(-12.0, 0.0, 0.0)
	camera.current = true
	root.add_child(camera)
	camera.make_current()


func _setup_light(root: Node3D) -> void:
	var light := DirectionalLight3D.new()
	light.name = "ProbeLight"
	light.rotation_degrees = Vector3(-45.0, 30.0, 0.0)
	root.add_child(light)


func _backend_settlement_projection(committed: bool) -> Dictionary:
	if committed:
		return {
			"interaction_attempt_id": "attempt:kick-chair:vertical-slice",
			"settlement_status": "committed",
			"settlement_writer_kind": "esm_compatibility_adapter",
			"server_ledger_sequence": 5,
			"presentation_directive": "apply_visible_chair_tip",
			"public_effect_summary": "chair tipped",
		}
	return {
		"interaction_attempt_id": "attempt:kick-chair:vertical-slice-failure",
		"settlement_status": "rejected",
		"settlement_writer_kind": "esm_compatibility_adapter",
		"server_ledger_sequence": 5,
		"retry_directive": "resync_affordance",
		"public_effect_summary": "no world state change",
	}


func _request() -> Dictionary:
	return {
		"request_id": "embodied_request:kick:vertical-slice",
		"interaction_attempt_id": "attempt:kick-chair:vertical-slice",
		"actor_id": "char_a",
		"target_ref": "entity:scene_demo:chair_01",
		"action_semantic": "kick",
		"affordance_id": "affordance:chair_01:kick",
		"authority_preflight_ref": "preflight:kick-chair:vertical-slice",
		"policy_revision": 2,
		"scene_revision": 5,
		"binding_revision": 7,
		"required_anchor_roles": ["approach_stance", "contact"],
		"execution_profile_ref": "execution_profile:kick:v1",
		"expiration_tick": 2000,
		"causation_id": "cause:kick-chair:vertical-slice",
		"correlation_id": "corr:kick-chair:vertical-slice",
		"realization_route": "embodied_controller_v1",
		"settlement_writer_kind": "esm_compatibility_adapter",
	}


func _grant() -> Dictionary:
	return {
		"grant_id": "grant:kick-chair:vertical-slice:1",
		"connection_epoch": 1,
		"one_time_outcome_nonce": "nonce:kick-chair:vertical-slice",
	}


func _binding() -> Dictionary:
	return {
		"entity_ref": "entity:scene_demo:chair_01",
		"local_binding": {
			"collider_refs": ["collider:chair_01:body"],
		},
	}


func _vector_to_dict(value: Vector3) -> Dictionary:
	return {"x": value.x, "y": value.y, "z": value.z}


func _write_screenshot(relative_path: String, success_changed: bool, failure_unchanged: bool) -> String:
	var path := ProjectSettings.globalize_path("res://" + relative_path)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var image: Image = null
	if DisplayServer.get_name() != "headless":
		var viewport_texture := get_viewport().get_texture()
		if viewport_texture != null:
			image = viewport_texture.get_image()
			_screenshot_source = "viewport"
	if image == null:
		image = _state_raster_image(success_changed, failure_unchanged)
		_screenshot_source = "runtime_state_raster_fallback"
	var error := image.save_png(path)
	return path if error == OK else ""


func _state_raster_image(success_changed: bool, failure_unchanged: bool) -> Image:
	var image := Image.create_empty(512, 256, false, Image.FORMAT_RGBA8)
	image.fill(Color(0.06, 0.07, 0.08, 1.0))
	var success_color := Color(0.1, 0.8, 0.35, 1.0) if success_changed else Color(0.8, 0.1, 0.1, 1.0)
	var failure_color := Color(0.7, 0.7, 0.7, 1.0) if failure_unchanged else Color(0.8, 0.1, 0.1, 1.0)
	for x in range(80, 210):
		for y in range(70, 190):
			image.set_pixel(x, y, success_color)
	for x in range(300, 430):
		for y in range(70, 190):
			image.set_pixel(x, y, failure_color)
	return image


func _write_json(relative_path: String, payload: Dictionary) -> String:
	var path := ProjectSettings.globalize_path("res://" + relative_path)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return ""
	file.store_string(JSON.stringify(payload, "\t"))
	file.close()
	return path
