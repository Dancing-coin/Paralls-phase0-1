extends Control

const ROOM_SCENE: PackedScene = preload("res://assets/environment/throne_room_existing/Demo.gltf")
const COMPENSATION_ENV_TEMPLATE: Environment = preload("res://scenes/phase0/BlenderRenderedApproxEnvironment.tres")
const LIGHTING_TUNER := preload("res://scripts/visual/ThroneRoomLightingTuner.gd")

const RAW_TITLE := "Raw import"
const RAW_NOTE := "No extra environment. Shows the scene as Godot receives it."

const COMP_TITLE := "Import + preview environment"
const COMP_NOTE := "Same import with a minimal sky / ambient / key-light compensation."

const CAMERA_POSITION := Vector3(-96.0, 6.0, 13.0)
const CAMERA_TARGET := Vector3(-58.0, 5.5, 13.0)
const CAMERA_FOV := 55.0

func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	_build_ui()
	_maybe_capture_and_quit()

func _build_ui() -> void:
	var background := ColorRect.new()
	background.set_anchors_preset(Control.PRESET_FULL_RECT)
	background.color = Color(0.06, 0.06, 0.07, 1.0)
	add_child(background)

	var root := VBoxContainer.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.offset_left = 24.0
	root.offset_top = 20.0
	root.offset_right = -24.0
	root.offset_bottom = -20.0
	root.add_theme_constant_override("separation", 14)
	add_child(root)

	root.add_child(_make_title())

	var row := HBoxContainer.new()
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.size_flags_vertical = Control.SIZE_EXPAND_FILL
	row.add_theme_constant_override("separation", 16)
	root.add_child(row)

	row.add_child(_make_panel(RAW_TITLE, RAW_NOTE, false))
	row.add_child(_make_panel(COMP_TITLE, COMP_NOTE, true))

	root.add_child(_make_footer())

func _make_title() -> Control:
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 4)

	var title := Label.new()
	title.text = "Blender vs Godot color comparison"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", 24)
	box.add_child(title)

	var subtitle := Label.new()
	subtitle.text = "Use the left panel to isolate raw import. Use the right panel to see how much environment compensation changes the result."
	subtitle.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	subtitle.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	subtitle.add_theme_font_size_override("font_size", 13)
	box.add_child(subtitle)

	return box

func _make_panel(title_text: String, note_text: String, with_environment: bool) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.size_flags_vertical = Control.SIZE_EXPAND_FILL

	var column := VBoxContainer.new()
	column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	column.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_theme_constant_override("separation", 8)
	panel.add_child(column)

	var title := Label.new()
	title.text = title_text
	title.add_theme_font_size_override("font_size", 18)
	column.add_child(title)

	var note := Label.new()
	note.text = note_text
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	note.add_theme_font_size_override("font_size", 12)
	column.add_child(note)

	var viewport_container := SubViewportContainer.new()
	viewport_container.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	viewport_container.size_flags_vertical = Control.SIZE_EXPAND_FILL
	viewport_container.stretch = true
	viewport_container.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_child(viewport_container)

	var viewport := SubViewport.new()
	viewport.size = Vector2i(1280, 720)
	viewport.disable_3d = false
	viewport.transparent_bg = false
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	viewport_container.add_child(viewport)

	var world_root := Node3D.new()
	viewport.add_child(world_root)

	var room := ROOM_SCENE.instantiate()
	world_root.add_child(room)

	if with_environment:
		LIGHTING_TUNER.apply_blender_approx(room)
		world_root.add_child(_make_environment())

	var camera := Camera3D.new()
	camera.current = true
	camera.fov = CAMERA_FOV
	camera.near = 0.1
	camera.far = 500.0
	camera.look_at_from_position(CAMERA_POSITION, CAMERA_TARGET, Vector3.UP)
	world_root.add_child(camera)

	return panel

func _make_environment() -> Node3D:
	var root := Node3D.new()
	root.name = "PreviewEnvironment"

	var world_environment := WorldEnvironment.new()
	world_environment.environment = COMPENSATION_ENV_TEMPLATE.duplicate(true)
	root.add_child(world_environment)

	var sun := DirectionalLight3D.new()
	sun.name = "DirectionalLight3D"
	sun.light_energy = 0.22
	sun.shadow_enabled = true
	sun.rotation_degrees = Vector3(-35.0, -30.0, 0.0)
	root.add_child(sun)

	return root

func _make_footer() -> Label:
	var footer := Label.new()
	footer.text = "If the right panel feels closer to Blender Rendered, the missing piece is environment / exposure. If both are still off, inspect material import next."
	footer.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	footer.add_theme_font_size_override("font_size", 11)
	return footer

func _maybe_capture_and_quit() -> void:
	var screenshot_path := OS.get_environment("THRONE_COMPARE_SCREENSHOT")
	if screenshot_path == "":
		return
	call_deferred("_capture_compare_screenshot", screenshot_path)

func _capture_compare_screenshot(screenshot_path: String) -> void:
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var image := get_viewport().get_texture().get_image()
	var err := image.save_png(screenshot_path)
	print("throne_compare_screenshot=%s err=%s" % [screenshot_path, err])
	get_tree().quit(0 if err == OK else 1)
