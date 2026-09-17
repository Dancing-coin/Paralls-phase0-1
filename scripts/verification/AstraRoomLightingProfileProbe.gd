extends SceneTree

const ROOM_SCENE := preload("res://archive/scenes/candidates/AstraRoom.tscn")
const TARGET_BACKGROUND := Color(0.23, 0.27, 0.31, 1.0)
const TARGET_DAYLIGHT_ENERGY := 0.02
const MAX_FLOOR_LAMP_ENERGY := 8.0


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var room := ROOM_SCENE.instantiate()
	root.add_child(room)
	await process_frame
	var world_environment := room.get_node("Presentation/WorldEnvironment") as WorldEnvironment
	var environment := world_environment.environment
	var daylight := room.get_node("Presentation/WindowDaylight") as DirectionalLight3D
	var floor_lamp := room.find_children("*", "OmniLight3D", true, false).front() as OmniLight3D
	assert(environment.background_color.is_equal_approx(TARGET_BACKGROUND))
	assert(is_equal_approx(daylight.light_energy, TARGET_DAYLIGHT_ENERGY))
	assert(floor_lamp.light_energy <= MAX_FLOOR_LAMP_ENERGY)
	print("ASTRA_LIGHTING_PROFILE_PASS")
	quit()
