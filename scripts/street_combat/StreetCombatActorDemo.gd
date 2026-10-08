extends Node3D

const ACTOR_NAMES := ["PlayerCharacter", "AgentCharacterJK", "AgentCharacterT"]
const WALK_SPEED := 1.8
const SKIN_PATH := "VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/StreetCharacterSkin"

@onready var coordinator: Node = $CombatCoordinator
@onready var camera: Camera3D = $FollowCamera

var controlled_actors: Array[CharacterActor] = []
var controlled_actor_index := 0
var active_actor: CharacterActor
var _ai_move_speeds: Dictionary = {}
var jump_requested := false
var jump_in_flight := false

func _ready() -> void:
	_build_collision()
	for actor_name: String in ACTOR_NAMES:
		var actor := get_node(actor_name) as CharacterActor
		controlled_actors.append(actor)
		_ai_move_speeds[actor.actor_id] = actor.move_speed
		actor.get_node("Nameplate").visible = false
		actor.get_node("PerceptionConeDebug").visible = false
	_set_active_actor(0)
	$CityStreetsEnvironment/EnvironmentNavigation.bake_navigation_mesh(false)
	if OS.get_environment("PARALLS_STREET_PROBE") in ["7", "8"]:
		call_deferred("_run_verification")

func _process(delta: float) -> void:
	if active_actor == null:
		return
	var target := active_actor.global_position + Vector3(0.0, 1.0, 0.0)
	var desired := active_actor.global_position + Vector3(4.8, 3.1, 6.6)
	camera.global_position = camera.global_position.lerp(desired, minf(1.0, 4.0 * delta))
	camera.look_at(target, Vector3.UP)

func _physics_process(_delta: float) -> void:
	if active_actor == null:
		return
	var input := Input.get_vector("phase0_move_left", "phase0_move_right", "phase0_move_forward", "phase0_move_backward")
	var direction := Vector3(input.x, 0.0, input.y)
	if direction.length() > 1.0:
		direction = direction.normalized()
	var running := Input.is_action_pressed("phase0_run") or Input.is_key_pressed(KEY_SHIFT)
	if jump_in_flight and active_actor.is_on_floor() and not jump_requested:
		jump_in_flight = false
	if jump_requested and active_actor.is_on_floor() and not jump_in_flight:
		jump_in_flight = true
	var jump_type := "two_foot" if jump_in_flight else "none"
	var gait := "idle" if direction.length_squared() < 0.001 else ("run" if running else "walk")
	var look_target := active_actor.global_position + direction if direction.length_squared() > 0.001 else active_actor.global_position - active_actor.global_basis.z
	active_actor.begin_embodied_control_frame(active_actor.global_position, direction, look_target, active_actor.is_on_floor() and not jump_in_flight, running, gait, "stand", jump_type)
	jump_requested = false
	for actor: CharacterActor in controlled_actors:
		var ring := actor.get_node_or_null("TargetRing") as MeshInstance3D
		if ring != null:
			ring.visible = actor.actor_id == coordinator.target_actor_id and actor != active_actor

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
		_request_attack("action:melee.unarmed_punch")
		return
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	var key := event as InputEventKey
	match key.keycode:
		KEY_TAB:
			_set_active_actor((controlled_actor_index + 1) % controlled_actors.size())
		KEY_SPACE:
			jump_requested = true
		KEY_1:
			_request_attack("action:melee.unarmed_punch")
		KEY_Q, KEY_2:
			_request_attack("action:melee.sword_slash")
		KEY_ESCAPE:
			get_tree().quit()

func _request_attack(semantic_action_id: String) -> void:
	if active_actor == null:
		return
	coordinator.request_attack(active_actor.actor_id, coordinator.target_actor_id, "", {}, semantic_action_id)

func _set_active_actor(next_index: int) -> void:
	if controlled_actors.is_empty():
		return
	var next_actor := controlled_actors[posmod(next_index, controlled_actors.size())]
	if active_actor == next_actor:
		return
	if active_actor != null:
		active_actor.clear_embodied_control_frame()
		active_actor.move_speed = float(_ai_move_speeds[active_actor.actor_id])
	controlled_actor_index = controlled_actors.find(next_actor)
	active_actor = next_actor
	active_actor.move_speed = WALK_SPEED
	active_actor.set_driver_mode(CharacterActor.DriverMode.PLAYER)
	active_actor.clear_move_target()
	jump_requested = false
	jump_in_flight = not active_actor.is_on_floor()
	coordinator.set_player_actor_id(active_actor.actor_id)
	active_actor.begin_embodied_control_frame(active_actor.global_position, Vector3.ZERO, active_actor.global_position - active_actor.global_basis.z, active_actor.is_on_floor(), false, "idle", "stand", "none")

func _build_collision() -> void:
	for mesh in $CityStreetsEnvironment/EnvironmentCollision.find_children("*", "MeshInstance3D", true, false):
		(mesh as MeshInstance3D).create_trimesh_collision()

func _run_verification() -> void:
	for _frame in range(8):
		await get_tree().physics_frame
	var initial_ok: bool = active_actor == $PlayerCharacter and active_actor.is_embodied_control_active() and coordinator.player_actor_id == "street_bandage"
	_set_active_actor(1)
	for _frame in range(3):
		await get_tree().physics_frame
	var char_a_ok: bool = active_actor == $AgentCharacterJK and active_actor.is_embodied_control_active() and not $PlayerCharacter.is_embodied_control_active() and coordinator.player_actor_id == "char_a" and coordinator.target_actor_id != "char_a"
	_set_active_actor(2)
	for _frame in range(3):
		await get_tree().physics_frame
	var char_b_ok: bool = active_actor == $AgentCharacterT and active_actor.is_embodied_control_active() and not $AgentCharacterJK.is_embodied_control_active() and coordinator.player_actor_id == "char_b" and coordinator.target_actor_id != "char_b"
	_set_active_actor(0)
	for _frame in range(3):
		await get_tree().physics_frame
	var round_trip_ok: bool = active_actor == $PlayerCharacter and active_actor.is_embodied_control_active() and not $AgentCharacterJK.is_embodied_control_active() and not $AgentCharacterT.is_embodied_control_active() and coordinator.player_actor_id == "street_bandage"
	var walk_clip_ok := true
	for actor: CharacterActor in controlled_actors:
		var skin := actor.get_node("VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/StreetCharacterSkin")
		var walk_accepted := bool(skin.play_locomotion_state("walk"))
		var walk_clip := str(skin.get_current_clip_name())
		walk_clip_ok = walk_clip_ok and walk_accepted and walk_clip.to_lower().ends_with("walking2")
	var passed: bool = initial_ok and char_a_ok and char_b_ok and round_trip_ok and walk_clip_ok
	print("street_actor_switch_probe:initial=%s:char_a=%s:char_b=%s:round_trip=%s:walk_clip=%s" % [str(initial_ok).to_lower(), str(char_a_ok).to_lower(), str(char_b_ok).to_lower(), str(round_trip_ok).to_lower(), str(walk_clip_ok).to_lower()])
	get_tree().quit(0 if passed else 1)
