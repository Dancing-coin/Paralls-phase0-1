extends Node

class_name CharacterControlFoundation

signal active_actor_changed(actor_id: String)

@export var actor_paths: Array[NodePath] = []
@export var actor_group := "character_control_actor"
@export var discover_group_members := true
@export var player_move_speed := 1.8

var actors: Array[CharacterActor] = []
var active_actor: CharacterActor
var active_actor_index := -1
var _default_move_speeds: Dictionary = {}
var _jump_requested := false
var _jump_in_flight := false

func bind(root: Node) -> void:
	actors.clear()
	_default_move_speeds.clear()
	var candidates: Array[Node] = []
	if discover_group_members and not actor_group.is_empty():
		for candidate: Node in get_tree().get_nodes_in_group(actor_group):
			if root.is_ancestor_of(candidate):
				candidates.append(candidate)
	else:
		for actor_path: NodePath in actor_paths:
			var actor := root.get_node_or_null(actor_path) as CharacterActor
			if actor != null:
				candidates.append(actor)
	for candidate: Node in candidates:
		var actor := candidate as CharacterActor
		if actor == null:
			continue
		actors.append(actor)
		_default_move_speeds[actor.actor_id] = actor.move_speed
		var nameplate := actor.get_node_or_null("Nameplate") as Node3D
		if nameplate != null:
			nameplate.visible = false
		actor.set_perception_debug_visible(false)
	set_active_actor(0)

func get_active_actor() -> CharacterActor:
	return active_actor

func get_actors() -> Array[CharacterActor]:
	return actors

func request_jump() -> void:
	_jump_requested = true

func select_next_actor() -> void:
	if not actors.is_empty():
		set_active_actor((active_actor_index + 1) % actors.size())

func set_active_actor(next_index: int) -> void:
	if actors.is_empty():
		return
	var next_actor := actors[posmod(next_index, actors.size())]
	if active_actor == next_actor:
		return
	if active_actor != null:
		active_actor.clear_embodied_control_frame()
		active_actor.move_speed = float(_default_move_speeds.get(active_actor.actor_id, active_actor.move_speed))
	active_actor_index = actors.find(next_actor)
	active_actor = next_actor
	active_actor.move_speed = player_move_speed
	active_actor.set_driver_mode(CharacterActor.DriverMode.PLAYER)
	active_actor.clear_move_target()
	_jump_requested = false
	_jump_in_flight = not active_actor.is_on_floor()
	active_actor.begin_embodied_control_frame(active_actor.global_position, Vector3.ZERO, active_actor.global_position - active_actor.global_basis.z, active_actor.is_on_floor(), false, "idle", "stand", "none")
	active_actor_changed.emit(active_actor.actor_id)

func apply_player_frame(input: Dictionary) -> void:
	if active_actor == null:
		return
	var direction: Vector3 = input.get("move_direction", Vector3.ZERO)
	var running := bool(input.get("wants_run", false))
	if _jump_in_flight and active_actor.is_on_floor() and not _jump_requested:
		_jump_in_flight = false
	if _jump_requested and active_actor.is_on_floor() and not _jump_in_flight:
		_jump_in_flight = true
	var jump_type := "two_foot" if _jump_in_flight else "none"
	var gait := "idle" if direction.length_squared() < 0.001 else ("run" if running else "walk")
	var look_target := active_actor.global_position + direction if direction.length_squared() > 0.001 else active_actor.global_position - active_actor.global_basis.z
	active_actor.begin_embodied_control_frame(active_actor.global_position, direction, look_target, active_actor.is_on_floor() and not _jump_in_flight, running, gait, "stand", jump_type)
	_jump_requested = false
