extends Node3D

## CharacterActor version of the original single-model streetdemo controller.
## Input and camera values intentionally match streetdemo.gd; body movement and
## animation realization remain owned by CharacterActor and its collaborators.

const CANONICAL_STATES := ["idle", "walk", "run", "jump", "boxing", "sword_attack"]
const WALK_SPEED := 1.8
const RUN_SPEED := 4.8
const JUMP_TYPE := "two_foot"

@onready var actor: CharacterActor = $PlayerCharacter
@onready var skin: Node = $PlayerCharacter/VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/StreetCharacterSkin
@onready var camera: Camera3D = $FollowCamera

var jump_requested := false
var jump_in_flight := false
var state_label: Label
var hint_label: Label

func _ready() -> void:
	_build_collision()
	_build_ui()

func _process(_delta: float) -> void:
	if actor == null or skin == null:
		return
	var playback_state := str(skin.get_playback_state())
	var clip := str(skin.get_current_clip_name())
	state_label.text = "sademo  |  Model 2 / female_t_external\nState: %s    Clip: %s    Tree states: %d    Tree active: %s\nVelocity: (%.2f, %.2f, %.2f)    Position: (%.2f, %.2f, %.2f)" % [
		playback_state,
		clip,
		skin.get_source_animation_states().size(),
		str(skin.is_animation_tree_active()),
		actor.velocity.x, actor.velocity.y, actor.velocity.z,
		actor.global_position.x, actor.global_position.y, actor.global_position.z,
	]
	hint_label.text = "WASD move   Shift run   Space jump   1 boxing   2 sword attack   |   CharacterActor"
	var target := actor.global_position + Vector3(0.0, 1.0, 0.0)
	var desired := actor.global_position + Vector3(4.8, 3.1, 6.6)
	camera.global_position = camera.global_position.lerp(desired, minf(1.0, 4.0 * _delta))
	camera.look_at(target, Vector3.UP)

func _physics_process(_delta: float) -> void:
	if actor == null:
		return
	var input := Input.get_vector("phase0_move_left", "phase0_move_right", "phase0_move_forward", "phase0_move_backward")
	var direction := Vector3(input.x, 0.0, input.y)
	if direction.length() > 1.0:
		direction = direction.normalized()
	var running := Input.is_key_pressed(KEY_SHIFT)
	var started_jump := false
	if jump_in_flight and actor.is_on_floor() and not jump_requested:
		jump_in_flight = false
	if jump_requested and actor.is_on_floor() and not jump_in_flight:
		jump_in_flight = true
		started_jump = true
	var jump_type := JUMP_TYPE if jump_in_flight else "none"
	var gait := "idle" if direction.length_squared() < 0.001 else ("run" if running else "walk")
	var look_target := actor.global_position + direction if direction.length_squared() > 0.001 else actor.global_position - actor.global_basis.z
	actor.begin_embodied_control_frame(
		actor.global_position,
		direction,
		look_target,
		actor.is_on_floor() and not jump_in_flight,
		running,
		gait,
		"stand",
		jump_type,
	)
	jump_requested = false
	if started_jump:
		jump_in_flight = true

func _unhandled_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	var key := event as InputEventKey
	if key.keycode == KEY_ESCAPE:
		get_tree().quit()
	elif key.keycode == KEY_SPACE:
		jump_requested = true
	elif key.keycode == KEY_1:
		_request_action("boxing", "action:melee.unarmed_punch")
	elif key.keycode == KEY_2:
		_request_action("sword_attack", "action:melee.sword_slash")

func _request_action(state_name: String, semantic_action_id: String) -> void:
	if skin == null or not CANONICAL_STATES.has(state_name):
		return
	var admission: Dictionary = actor.submit_action_intent(StringName(semantic_action_id), &"", &"player")
	if not bool(admission.get("accepted", false)):
		return
	var clip_ref := "boxing" if state_name == "boxing" else "sword attack"
	actor.play_reviewed_action_atom(state_name, clip_ref, "active")

func _build_collision() -> void:
	for mesh in $CityStreetsEnvironment/EnvironmentCollision.find_children("*", "MeshInstance3D", true, false):
		(mesh as MeshInstance3D).create_trimesh_collision()

func _build_ui() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	var panel := ColorRect.new()
	panel.position = Vector2(24, 24)
	panel.size = Vector2(980, 142)
	panel.color = Color(0.03, 0.05, 0.08, 0.86)
	layer.add_child(panel)
	state_label = Label.new()
	state_label.position = Vector2(42, 38)
	state_label.add_theme_font_size_override("font_size", 18)
	layer.add_child(state_label)
	hint_label = Label.new()
	hint_label.position = Vector2(42, 132)
	hint_label.add_theme_font_size_override("font_size", 16)
	layer.add_child(hint_label)
