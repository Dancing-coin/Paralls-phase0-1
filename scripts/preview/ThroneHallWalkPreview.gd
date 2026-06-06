extends Node3D

const LIGHTING_TUNER := preload("res://scripts/visual/ThroneRoomLightingTuner.gd")
const COMPENSATION_ENV_TEMPLATE: Environment = preload("res://scenes/phase0/BlenderRenderedApproxEnvironment.tres")
const THRONE_BEAM_SHADER := preload("res://scripts/visual/throne_beam_card.gdshader")

const BLUE_LIGHT_NAMES := [
	"PointLight142",
	"PointLight82",
	"PointLight72",
	"PointLight62",
	"PointLight23",
	"SpotLight602",
	"SpotLight582",
	"SpotLight562",
	"SpotLight423",
]

const DISABLED_COLLIDER_KEYWORDS := [
	"floor",
	"carpet",
	"bench",
]

func _ready() -> void:
	_apply_blender_approx()
	_adjust_blue_lights()
	_simplify_preview_colliders()
	_hide_preview_player_shell()
	_hide_preview_hud()
	_maybe_capture_and_quit()

func _apply_blender_approx() -> void:
	var hall := get_node_or_null("ThroneHallImported")
	if hall != null:
		LIGHTING_TUNER.apply_blender_approx(hall)

	var preview_environment := get_node_or_null("PreviewEnvironment")
	var world_environment := get_node_or_null("PreviewEnvironment/WorldEnvironment")
	if world_environment is WorldEnvironment:
		(world_environment as WorldEnvironment).environment = COMPENSATION_ENV_TEMPLATE.duplicate(true)
	if preview_environment is Node3D:
		_ensure_preview_fog_volumes(preview_environment as Node3D)
		_ensure_preview_god_rays(preview_environment as Node3D)
		_ensure_preview_beam_cards(preview_environment as Node3D)

func _ensure_preview_fog_volumes(preview_environment: Node3D) -> void:
	var existing := preview_environment.get_node_or_null("CodexFogVolumes")
	if existing != null:
		return

	var root := Node3D.new()
	root.name = "CodexFogVolumes"
	preview_environment.add_child(root)

	root.add_child(_make_fog_volume(
		"AisleMistNear",
		Vector3(-58.0, 5.2, 13.0),
		Vector3(26.0, 10.0, 12.0),
		Color(0.9, 0.72, 0.56, 1.0),
		Color(0.012, 0.008, 0.003, 1.0),
		0.008,
		0.52,
		0.08
	))
	root.add_child(_make_fog_volume(
		"AisleMistFar",
		Vector3(-84.0, 8.0, 13.0),
		Vector3(48.0, 16.0, 14.0),
		Color(0.95, 0.8, 0.62, 1.0),
		Color(0.018, 0.012, 0.005, 1.0),
		0.01,
		0.56,
		0.1
	))
	root.add_child(_make_fog_volume(
		"ThroneHalo",
		Vector3(-111.0, 11.5, 13.0),
		Vector3(18.0, 16.0, 12.0),
		Color(1.0, 0.88, 0.72, 1.0),
		Color(0.06, 0.038, 0.014, 1.0),
		0.018,
		0.44,
		0.1
	))
	root.add_child(_make_fog_volume(
		"ChandelierHaze",
		Vector3(-58.0, 20.0, 13.0),
		Vector3(90.0, 10.0, 20.0),
		Color(0.86, 0.68, 0.52, 1.0),
		Color(0.008, 0.004, 0.001, 1.0),
		0.004,
		0.64,
		0.05
	))

func _make_fog_volume(name: String, position: Vector3, size: Vector3, albedo: Color, emission: Color, density: float, edge_fade: float, height_falloff: float) -> FogVolume:
	var fog_volume := FogVolume.new()
	fog_volume.name = name
	fog_volume.position = position
	fog_volume.size = size
	fog_volume.shape = RenderingServer.FOG_VOLUME_SHAPE_BOX

	var fog_material := FogMaterial.new()
	fog_material.albedo = albedo
	fog_material.emission = emission
	fog_material.density = density
	fog_material.edge_fade = edge_fade
	fog_material.height_falloff = height_falloff
	fog_volume.material = fog_material

	return fog_volume

func _ensure_preview_god_rays(preview_environment: Node3D) -> void:
	var existing := preview_environment.get_node_or_null("CodexGodRays")
	if existing != null:
		return

	var root := Node3D.new()
	root.name = "CodexGodRays"
	preview_environment.add_child(root)

	root.add_child(_make_god_ray(
		"ThroneRayLeft",
		Vector3(-100.0, 14.5, 10.0),
		Vector3(-111.0, 7.6, 12.6),
		Color(1.0, 0.82, 0.62, 1.0),
		0.75,
		26.0,
		34.0,
		22.0
	))
	root.add_child(_make_god_ray(
		"ThroneRayRight",
		Vector3(-100.0, 14.5, 16.0),
		Vector3(-111.0, 7.6, 13.4),
		Color(1.0, 0.8, 0.6, 1.0),
		0.72,
		24.0,
		34.0,
		22.0
	))
	root.add_child(_make_god_ray(
		"ThroneBackGlow",
		Vector3(-112.0, 8.8, 13.0),
		Vector3(-92.0, 8.2, 13.0),
		Color(1.0, 0.86, 0.7, 1.0),
		2.8,
		54.0,
		54.0,
		34.0
	))
	root.add_child(_make_portal_glow(
		"ThronePortalGlow",
		Vector3(-114.5, 7.8, 13.0),
		Color(1.0, 0.78, 0.56, 1.0),
		2.6,
		16.0,
		4.0
	))

func _make_god_ray(name: String, position: Vector3, target: Vector3, color: Color, energy: float, volumetric_energy: float, range_m: float, angle_deg: float) -> SpotLight3D:
	var light := SpotLight3D.new()
	light.name = name
	light.position = position
	light.light_color = color
	light.light_energy = energy
	light.light_volumetric_fog_energy = volumetric_energy
	light.light_specular = 0.0
	light.light_indirect_energy = 0.0
	light.shadow_enabled = false
	light.spot_range = range_m
	light.spot_angle = angle_deg
	light.spot_angle_attenuation = 0.45
	light.spot_attenuation = 0.7
	light.look_at_from_position(position, target, Vector3.UP)
	return light

func _make_portal_glow(name: String, position: Vector3, color: Color, energy: float, range_m: float, volumetric_energy: float) -> OmniLight3D:
	var light := OmniLight3D.new()
	light.name = name
	light.position = position
	light.light_color = color
	light.light_energy = energy
	light.omni_range = range_m
	light.omni_attenuation = 0.8
	light.light_volumetric_fog_energy = volumetric_energy
	light.light_specular = 0.0
	light.light_indirect_energy = 0.0
	light.shadow_enabled = false
	return light

func _ensure_preview_beam_cards(preview_environment: Node3D) -> void:
	var existing := preview_environment.get_node_or_null("CodexBeamCards")
	if existing != null:
		return

	var root := Node3D.new()
	root.name = "CodexBeamCards"
	preview_environment.add_child(root)

	root.add_child(_make_beam_card(
		"AltarBeamCenter",
		Vector3(-103.0, 11.5, 13.0),
		Vector3(-24.0, -8.0, 0.0),
		Vector3(7.0, 18.0, 1.0),
		Color(1.0, 0.84, 0.62, 0.32),
		2.4
	))
	root.add_child(_make_beam_card(
		"AltarBeamLeft",
		Vector3(-98.5, 12.2, 10.4),
		Vector3(-18.0, -9.0, 12.0),
		Vector3(5.0, 16.0, 1.0),
		Color(1.0, 0.72, 0.46, 0.22),
		1.8
	))
	root.add_child(_make_beam_card(
		"AltarBeamRight",
		Vector3(-98.5, 12.2, 15.6),
		Vector3(-18.0, -9.0, -12.0),
		Vector3(5.0, 16.0, 1.0),
		Color(1.0, 0.72, 0.46, 0.22),
		1.8
	))

func _make_beam_card(name: String, position: Vector3, rotation_degrees: Vector3, size: Vector3, color: Color, energy: float) -> MeshInstance3D:
	var mesh_instance := MeshInstance3D.new()
	mesh_instance.name = name
	mesh_instance.position = position
	mesh_instance.rotation_degrees = rotation_degrees
	mesh_instance.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

	var quad := QuadMesh.new()
	quad.size = Vector2(size.x, size.y)
	mesh_instance.mesh = quad
	mesh_instance.scale = Vector3(1.0, 1.0, size.z)

	var material := ShaderMaterial.new()
	material.shader = THRONE_BEAM_SHADER
	material.set_shader_parameter("beam_color", color)
	material.set_shader_parameter("beam_energy", energy)
	material.set_shader_parameter("center_falloff", 3.4)
	material.set_shader_parameter("length_falloff", 1.15)
	material.set_shader_parameter("edge_softness", 0.22)
	material.set_shader_parameter("noise_mix", 0.16)
	material.set_shader_parameter("scroll_speed", 0.03)
	mesh_instance.material_override = material

	return mesh_instance

func _maybe_capture_and_quit() -> void:
	var screenshot_path := OS.get_environment("THRONE_WALK_SCREENSHOT")
	if screenshot_path == "":
		return
	call_deferred("_capture_screenshot", screenshot_path)

func _capture_screenshot(screenshot_path: String) -> void:
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var image := get_viewport().get_texture().get_image()
	var err := image.save_png(screenshot_path)
	print("throne_walk_screenshot=%s err=%s" % [screenshot_path, err])
	get_tree().quit(0 if err == OK else 1)

func _adjust_blue_lights() -> void:
	var hall := get_node_or_null("ThroneHallImported")
	if hall == null:
		return

	for light_name in BLUE_LIGHT_NAMES:
		var candidate := hall.find_child(light_name, true, false)
		if candidate is Light3D:
			var light := candidate as Light3D
			light.light_color = Color(1.0, 0.92, 0.82, 1.0)
			light.light_energy *= 0.35

func _simplify_preview_colliders() -> void:
	var root := get_node_or_null("PreviewCollisionRoot")
	if root == null:
		return

	for child in root.get_children():
		if not (child is StaticBody3D):
			continue
		var lower := String(child.name).to_lower()
		var disable := false
		for keyword in DISABLED_COLLIDER_KEYWORDS:
			if lower.find(keyword) != -1:
				disable = true
				break
		if not disable:
			continue
		for shape_node in child.get_children():
			if shape_node is CollisionShape3D:
				(shape_node as CollisionShape3D).disabled = true

func _hide_preview_player_shell() -> void:
	var player := get_node_or_null("Player")
	if player == null:
		return
	var visual_root := player.find_child("VisualRoot", true, false)
	if visual_root is Node3D:
		(visual_root as Node3D).visible = false

func _hide_preview_hud() -> void:
	var player := get_node_or_null("Player")
	if player == null:
		return
	var hud := player.find_child("HUD", true, false)
	if hud is CanvasLayer:
		(hud as CanvasLayer).visible = false
