extends Node3D

@export var display_name := "replica"
@export var body_color := Color(0.78, 0.8, 0.88, 1.0)
@export var skin_color := Color(0.95, 0.84, 0.72, 1.0)
@export var accent_color := Color(0.25, 0.55, 0.95, 1.0)
@export var focus_color := Color(0.95, 0.85, 0.35, 1.0)

@onready var body_mesh: MeshInstance3D = $Body
@onready var head_mesh: MeshInstance3D = $Head
@onready var arm_l_mesh: MeshInstance3D = $ArmL
@onready var arm_r_mesh: MeshInstance3D = $ArmR
@onready var leg_l_mesh: MeshInstance3D = $LegL
@onready var leg_r_mesh: MeshInstance3D = $LegR
@onready var chest_plate_mesh: MeshInstance3D = $ChestPlate
@onready var nameplate: Label3D = $Nameplate

var focused := false

func _ready() -> void:
	_apply_visuals()

func configure_visuals(next_name: String, next_body_color: Color, next_skin_color: Color, next_accent_color: Color, next_focus_color: Color) -> void:
	display_name = next_name
	body_color = next_body_color
	skin_color = next_skin_color
	accent_color = next_accent_color
	focus_color = next_focus_color
	_apply_visuals()

func set_focus_highlight(is_focused: bool) -> void:
	focused = is_focused
	_apply_visuals()

func _apply_visuals() -> void:
	if nameplate:
		nameplate.text = "%s%s" % [display_name.to_upper(), " !" if focused else ""]
		nameplate.modulate = focus_color if focused else Color(1.0, 1.0, 1.0, 1.0)

	_set_mesh_color(body_mesh, focus_color if focused else body_color)
	_set_mesh_color(arm_l_mesh, focus_color if focused else body_color)
	_set_mesh_color(arm_r_mesh, focus_color if focused else body_color)
	_set_mesh_color(leg_l_mesh, focus_color if focused else body_color)
	_set_mesh_color(leg_r_mesh, focus_color if focused else body_color)
	_set_mesh_color(chest_plate_mesh, focus_color if focused else accent_color)
	_set_mesh_color(head_mesh, skin_color)

func _set_mesh_color(mesh_instance: MeshInstance3D, color: Color) -> void:
	if mesh_instance == null:
		return
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	mesh_instance.material_override = material
