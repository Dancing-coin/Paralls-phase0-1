extends CharacterBody3D

class_name ProceduralLowPolyCharacter

const VALID_STATES := ["idle", "observe", "hide", "pursue", "controlled", "returned"]

var actor_ref := ""
var role_ref := ""
var presentation_profile_ref := ""
var committed_state := "returned"
var current_state := "returned"
var speculative_state := ""
var profile: Dictionary = {}
var _built := false

@onready var visual_root: Node3D = $VisualRoot
@onready var animation_player: AnimationPlayer = $AnimationPlayer


func _ready() -> void:
	_build_body()


func configure_profile(next_profile: Dictionary) -> void:
	var allowed := {
		"actor_ref": true,
		"role_ref": true,
		"presentation_profile_ref": true,
		"primary_color": true,
		"secondary_color": true,
		"marker": true,
	}
	for key in next_profile.keys():
		if not allowed.has(key):
			return
	profile = next_profile.duplicate(true)
	actor_ref = str(profile.get("actor_ref", ""))
	role_ref = str(profile.get("role_ref", ""))
	presentation_profile_ref = str(profile.get("presentation_profile_ref", ""))
	if _built:
		_apply_profile_materials()


func apply_committed_state(state: String) -> void:
	if not VALID_STATES.has(state):
		state = "returned"
	committed_state = state
	current_state = state
	speculative_state = ""
	_apply_state_pose(state)


func apply_speculative_state(state: String) -> void:
	if not VALID_STATES.has(state):
		return
	speculative_state = state
	_apply_state_pose(state)


func clear_speculative_state() -> void:
	speculative_state = ""
	current_state = committed_state
	_apply_state_pose(committed_state)


func _build_body() -> void:
	if _built:
		return
	_built = true
	_add_capsule("Torso", Vector3(0.72, 1.05, 0.48), Vector3(0.0, 1.55, 0.0), Color(0.24, 0.32, 0.46))
	_add_sphere("Head", Vector3(0.42, 2.55, 0.0), 0.42, Color(0.72, 0.52, 0.38))
	_add_box("LeftArm", Vector3(0.22, 0.82, 0.22), Vector3(-0.55, 1.62, 0.0), Color(0.24, 0.32, 0.46))
	_add_box("RightArm", Vector3(0.22, 0.82, 0.22), Vector3(0.55, 1.62, 0.0), Color(0.24, 0.32, 0.46))
	_add_box("LeftLeg", Vector3(0.25, 0.9, 0.25), Vector3(-0.22, 0.65, 0.0), Color(0.12, 0.15, 0.2))
	_add_box("RightLeg", Vector3(0.25, 0.9, 0.25), Vector3(0.22, 0.65, 0.0), Color(0.12, 0.15, 0.2))
	_add_box("Belt", Vector3(0.78, 0.16, 0.52), Vector3(0.0, 1.22, 0.0), Color(0.12, 0.08, 0.05))
	_add_box("ShoulderMarker", Vector3(0.18, 0.18, 0.58), Vector3(0.0, 2.0, 0.0), Color(0.85, 0.55, 0.12))
	_apply_profile_materials()


func _add_capsule(node_name: String, size: Vector3, position: Vector3, color: Color) -> void:
	var node := MeshInstance3D.new()
	node.name = node_name
	var mesh := CapsuleMesh.new()
	mesh.radius = size.x * 0.5
	mesh.height = size.y
	node.mesh = mesh
	node.position = position
	node.material_override = _material(color)
	visual_root.add_child(node)


func _add_sphere(node_name: String, position: Vector3, radius: float, color: Color) -> void:
	var node := MeshInstance3D.new()
	node.name = node_name
	var mesh := SphereMesh.new()
	mesh.radius = radius
	mesh.height = radius * 2.0
	node.mesh = mesh
	node.position = position
	node.material_override = _material(color)
	visual_root.add_child(node)


func _add_box(node_name: String, size: Vector3, position: Vector3, color: Color) -> void:
	var node := MeshInstance3D.new()
	node.name = node_name
	var mesh := BoxMesh.new()
	mesh.size = size
	node.mesh = mesh
	node.position = position
	node.material_override = _material(color)
	visual_root.add_child(node)


func _material(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.82
	return material


func _apply_profile_materials() -> void:
	if visual_root == null:
		return
	var primary := _color_from_profile("primary_color", Color(0.24, 0.32, 0.46))
	var secondary := _color_from_profile("secondary_color", Color(0.12, 0.15, 0.2))
	for node in visual_root.get_children():
		if node is MeshInstance3D and node.name not in ["Head", "Belt", "ShoulderMarker"]:
			node.material_override = _material(primary)
	var belt := visual_root.get_node_or_null("Belt") as MeshInstance3D
	if belt != null:
		belt.material_override = _material(secondary)
	var marker := visual_root.get_node_or_null("ShoulderMarker") as MeshInstance3D
	if marker != null:
		marker.material_override = _material(_marker_color(str(profile.get("marker", "amber"))))


func _color_from_profile(key: String, fallback: Color) -> Color:
	var value: Variant = profile.get(key, fallback)
	if value is Color:
		return value
	if value is String:
		return Color(value)
	return fallback


func _marker_color(marker: String) -> Color:
	match marker:
		"blue": return Color(0.15, 0.45, 0.95)
		"red": return Color(0.9, 0.16, 0.12)
		"green": return Color(0.18, 0.72, 0.3)
		_: return Color(0.95, 0.62, 0.1)


func _apply_state_pose(state: String) -> void:
	if visual_root == null:
		return
	var target_scale := Vector3.ONE
	var target_rotation := Vector3.ZERO
	match state:
		"observe":
			target_rotation.y = 0.22
		"hide":
			target_scale = Vector3(0.92, 0.78, 0.92)
		"pursue":
			target_rotation.y = -0.22
		"controlled":
			target_rotation.z = 0.16
		"returned":
			target_scale = Vector3.ONE
	visual_root.scale = target_scale
	visual_root.rotation = target_rotation
