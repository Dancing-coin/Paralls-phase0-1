extends Node3D

class_name StreetCombatActorControlDemo


@onready var coordinator: Node = $CombatCoordinator
@onready var camera: Camera3D = $FollowCamera
@onready var control: Node = $CharacterControlFoundation

func _ready() -> void:
	_build_collision()
	$ControlInput.action_requested.connect(_request_attack)
	$ControlInput.actor_switch_requested.connect(control.select_next_actor)
	$ControlInput.jump_requested.connect(control.request_jump)
	control.active_actor_changed.connect(_on_active_actor_changed)
	control.bind(self)
	$ControlCamera.setup(camera)
	$CityStreetsEnvironment/EnvironmentNavigation.bake_navigation_mesh(false)


func _process(delta: float) -> void:
	$ControlCamera.follow(control.get_active_actor(), delta)

func _physics_process(_delta: float) -> void:
	control.apply_player_frame($ControlInput.sample())
	for actor: CharacterActor in control.get_actors():
		var ring := actor.get_node_or_null("TargetRing") as MeshInstance3D
		if ring != null:
			ring.visible = actor.actor_id == coordinator.target_actor_id and actor != control.get_active_actor()

func _unhandled_input(event: InputEvent) -> void:
	$ControlInput.handle_input(event)

func _request_attack(semantic_action_id: String) -> void:
	var active_actor: CharacterActor = control.get_active_actor()
	if active_actor != null:
		coordinator.request_attack(active_actor.actor_id, coordinator.target_actor_id, "", {}, semantic_action_id)

func _on_active_actor_changed(actor_id: String) -> void:
	coordinator.set_player_actor_id(actor_id)

func _build_collision() -> void:
	for mesh in $CityStreetsEnvironment/EnvironmentCollision.find_children("*", "MeshInstance3D", true, false):
		(mesh as MeshInstance3D).create_trimesh_collision()
