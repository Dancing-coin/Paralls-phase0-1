extends Node3D

const PLAYER_SCENE := preload("res://scenes/phase0/PlayerShell.tscn")
const CHARACTER_SCENE := preload("res://scenes/phase0/ProceduralLowPolyCharacter.tscn")
const HUD := preload("res://scripts/phase0/StormnightRealtimeHud.gd")

const ACTORS := [
	{"actor_ref": "character:stormnight-heir@1", "role_ref": "role:threatened-heir@1", "presentation_profile_ref": "presentation:stormnight:investigator-blue@1", "primary_color": "#3d6ea8", "secondary_color": "#1d2c42", "marker": "blue"},
	{"actor_ref": "character:stormnight-guardian@1", "role_ref": "role:guardian@1", "presentation_profile_ref": "presentation:stormnight:guardian-red@1", "primary_color": "#8f3f45", "secondary_color": "#3a171c", "marker": "red"},
	{"actor_ref": "character:stormnight-investigator@1", "role_ref": "role:investigator@1", "presentation_profile_ref": "presentation:stormnight:witness-green@1", "primary_color": "#3b805e", "secondary_color": "#173c2b", "marker": "green"},
	{"actor_ref": "character:stormnight-physician@1", "role_ref": "role:physician@1", "presentation_profile_ref": "presentation:stormnight:suspect-amber@1", "primary_color": "#a77532", "secondary_color": "#4a3014", "marker": "amber"},
]

var hud: StormnightRealtimeHud
var actors: Array[Node] = []
var request_counter := 0
var last_projection: Dictionary = {}
var player: CharacterBody3D
var player_avatar: Node3D


func _ready() -> void:
	_build_sanatorium()
	_build_player()
	_build_actors()
	_build_lighting()
	hud = HUD.new()
	add_child(hud)
	var bus := get_node_or_null("/root/LocalPresentationBus")
	if bus != null and bus.has_signal("stormnight_case_projection_received"):
		bus.stormnight_case_projection_received.connect(_on_case_projection)
	var bridge := get_node_or_null("/root/BackendBridge")
	if bridge != null and bridge.has_method("connect_to_backend"):
		bridge.connect_to_backend("ws://127.0.0.1:8000/ws")


func _process(_delta: float) -> void:
	if player != null and player_avatar != null:
		player_avatar.global_position = player.global_position
		player_avatar.global_rotation.y = player.global_rotation.y


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey) or not event.pressed or event.echo:
		return
	match event.keycode:
		KEY_ENTER:
			_send_intent("start")
		KEY_E:
			_send_intent("inspect")
		KEY_SPACE:
			_send_intent("advance")
		KEY_Q:
			_send_intent("question", "character:stormnight-guardian@1")
		KEY_H:
			_send_intent("hide")
		KEY_F:
			_send_intent("pursue")
		KEY_1:
			_send_intent("accuse", "character:stormnight-heir@1")
		KEY_2:
			_send_intent("accuse", "character:stormnight-guardian@1")
		KEY_3:
			_send_intent("accuse", "character:stormnight-investigator@1")
		KEY_4:
			_send_intent("accuse", "character:stormnight-physician@1")


func _send_intent(kind: String, target_ref := "") -> void:
	var bridge := get_node_or_null("/root/BackendBridge")
	if bridge == null or not bridge.has_method("is_backend_open") or not bridge.is_backend_open():
		hud.show_pending("backend unavailable")
		return
	request_counter += 1
	var payload := {"kind": kind, "request_id": "godot:stormnight:%s" % request_counter}
	if not target_ref.is_empty():
		payload["target_ref"] = target_ref
	hud.show_pending(kind)
	bridge.send_envelope({"message_type": "stormnight_player_intent", "payload": payload})


func _on_case_projection(payload: Dictionary) -> void:
	last_projection = payload.duplicate(true)
	hud.show_projection(payload)
	if not bool(payload.get("accepted", false)):
		_restore_committed_actor_state()
		return
	_apply_committed_actor_state(payload.get("projection", {}))


func _apply_committed_actor_state(projection: Dictionary) -> void:
	var terminal := str(projection.get("terminal_outcome", ""))
	var phase := str(projection.get("phase_ref", ""))
	for index in range(actors.size()):
		var state := "observe" if phase.ends_with("storm-night@1") else "idle"
		if terminal == "case_solved":
			state = "returned"
		elif terminal == "investigator_captured" and index == 2:
			state = "controlled"
		elif terminal == "culprit_escaped" and index == 1:
			state = "pursue"
		actors[index].apply_committed_state(state)


func _restore_committed_actor_state() -> void:
	for actor in actors:
		actor.clear_speculative_state()


func _build_player() -> void:
	player = PLAYER_SCENE.instantiate()
	player.name = "StormnightPlayer"
	player.position = Vector3(0.0, 1.1, 9.5)
	add_child(player)
	player_avatar = CHARACTER_SCENE.instantiate()
	player_avatar.name = "StormnightPlayerAvatar"
	add_child(player_avatar)
	player_avatar.configure_profile({"actor_ref": "character:stormnight-investigator@1", "role_ref": "role:player-investigator@1", "presentation_profile_ref": "presentation:stormnight:player@1", "primary_color": "#526a98", "secondary_color": "#162034", "marker": "blue"})


func _build_actors() -> void:
	var root := Node3D.new()
	root.name = "StormnightActors"
	add_child(root)
	for index in range(ACTORS.size()):
		var actor := CHARACTER_SCENE.instantiate()
		actor.name = "Actor_%s" % index
		actor.position = Vector3(-6.0 + float(index) * 4.0, 0.0, 1.5)
		root.add_child(actor)
		actor.configure_profile(ACTORS[index])
		actors.append(actor)


func _build_sanatorium() -> void:
	for room_index in range(4):
		var room := Node3D.new()
		room.name = "RealtimeRoom_%s" % room_index
		room.position = Vector3(float(room_index % 2) * 10.0 - 5.0, 0.0, float(room_index / 2) * -10.0)
		add_child(room)
		_add_box(room, "Floor", Vector3(9.4, 0.2, 9.4), Vector3(0.0, 0.0, 0.0), Color(0.13, 0.15, 0.18))
		_add_box(room, "EvidenceTable", Vector3(1.6, 0.8, 0.9), Vector3(-2.0, 0.5, -1.8), Color(0.55, 0.36, 0.17))
		_add_box(room, "HideSpot", Vector3(1.3, 1.4, 1.3), Vector3(2.2, 0.7, 2.0), Color(0.12, 0.38, 0.26))
		_add_box(room, "Occluder", Vector3(0.35, 2.4, 3.2), Vector3(0.0, 1.2, 0.0), Color(0.22, 0.28, 0.35))
		_add_floor_collision(room)


func _build_lighting() -> void:
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-52.0, -28.0, 0.0)
	light.light_energy = 1.4
	add_child(light)
	var world := WorldEnvironment.new()
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color(0.025, 0.035, 0.065)
	world.environment = environment
	add_child(world)


func _add_floor_collision(parent: Node3D) -> void:
	var body := StaticBody3D.new()
	body.name = "FloorCollision"
	var collider := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = Vector3(9.4, 0.2, 9.4)
	collider.shape = shape
	body.add_child(collider)
	parent.add_child(body)


func _add_box(parent: Node3D, node_name: String, size: Vector3, position: Vector3, color: Color) -> void:
	var instance := MeshInstance3D.new()
	instance.name = node_name
	var mesh := BoxMesh.new()
	mesh.size = size
	instance.mesh = mesh
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	instance.material_override = material
	instance.position = position
	parent.add_child(instance)
