extends Node3D

@onready var actor: CharacterBody3D = $FemaleTExternal
@onready var skin: Node3D = $FemaleTExternal/ImportedModel/StreetCharacterSkin
@onready var camera: Camera3D = $FollowCamera

const WALK_SPEED := 1.8
const RUN_SPEED := 4.8
const ACCELERATION := 12.0
const GRAVITY := 18.0
const JUMP_SPEED := 6.0
const XFADE_TIME := 0.18

var jump_until := 0.0
var state_label: Label
var hint_label: Label

func _ready() -> void:
	_build_collision()
	_build_ui()
	_set_locomotion("idle")

func _process(_delta: float) -> void:
	if actor == null:
		return
	var controller: Node = skin.animation_controller
	var playback_state: String = str(skin.get_playback_state())
	var clip: String = str(skin.get_current_clip_name())
	state_label.text = "streetdemo  |  Model 2 / female_t_external\nState: %s    Clip: %s    Tree states: %d    Tree active: %s\nVelocity: (%.2f, %.2f, %.2f)    Position: (%.2f, %.2f, %.2f)" % [
		playback_state,
		clip,
		skin.get_source_animation_states().size(),
		str(skin.is_animation_tree_active()),
		actor.velocity.x, actor.velocity.y, actor.velocity.z,
		actor.global_position.x, actor.global_position.y, actor.global_position.z,
	]
	if controller != null:
		hint_label.text = "WASD move   Shift run   Space jump   1 boxing   2 sword attack   |   controller: %s" % controller.name
	var target := actor.global_position + Vector3(0.0, 1.0, 0.0)
	var desired := actor.global_position + Vector3(4.8, 3.1, 6.6)
	camera.global_position = camera.global_position.lerp(desired, minf(1.0, 4.0 * _delta))
	camera.look_at(target, Vector3.UP)

func _physics_process(delta: float) -> void:
	var input := Input.get_vector("phase0_move_left", "phase0_move_right", "phase0_move_forward", "phase0_move_backward")
	var direction := Vector3(input.x, 0.0, input.y)
	if direction.length() > 1.0:
		direction = direction.normalized()
	var running := Input.is_key_pressed(KEY_SHIFT)
	var speed := RUN_SPEED if running else WALK_SPEED
	var desired := direction * speed
	actor.velocity.x = move_toward(actor.velocity.x, desired.x, ACCELERATION * delta)
	actor.velocity.z = move_toward(actor.velocity.z, desired.z, ACCELERATION * delta)
	if not actor.is_on_floor():
		actor.velocity.y -= GRAVITY * delta
	elif actor.velocity.y < 0.0:
		actor.velocity.y = 0.0
	actor.move_and_slide()
	if direction.length_squared() > 0.001 and not _animation_locked():
		actor.rotation.y = lerp_angle(actor.rotation.y, atan2(direction.x, direction.z), minf(1.0, 10.0 * delta))
	if _animation_locked():
		return
	if not actor.is_on_floor():
		_set_locomotion("jump")
	elif direction.length_squared() < 0.001:
		_set_locomotion("idle")
	elif running:
		_set_locomotion("run")
	else:
		_set_locomotion("walk")

func _unhandled_input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed or event.echo:
		return
	var key := event as InputEventKey
	if key.keycode == KEY_ESCAPE:
		get_tree().quit()
	elif key.keycode == KEY_SPACE and actor.is_on_floor() and not _animation_locked():
		actor.velocity.y = JUMP_SPEED
		jump_until = Time.get_ticks_msec() / 1000.0 + _clip_length("jump")
		_set_locomotion("jump")
	elif key.keycode == KEY_1 and not _animation_locked():
		skin.play_action_state("boxing")
	elif key.keycode == KEY_2 and not _animation_locked():
		skin.play_action_state("sword_attack")

func _set_locomotion(state_name: String) -> void:
	if state_name in ["idle", "walk", "run", "jump"]:
		skin.play_locomotion_state(state_name)

func _animation_locked() -> bool:
	return skin.animation_controller != null and skin.animation_controller.has_method("is_locked") and skin.animation_controller.is_locked()

func _clip_length(clip_name: String) -> float:
	var animation: Animation = skin.animation_controller.animation_player.get_animation(clip_name)
	return maxf(0.1, animation.length if animation != null else 0.5)

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
