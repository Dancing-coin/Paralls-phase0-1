extends Node3D

class_name ArchiveDoorPhysical


@export var object_id := "obj_archive_door"
@export var display_name := "Archive Door"
@export_node_path("Node") var presentation_path := NodePath("ArchiveDoorPhysicalPresentation")

var focused := false


func current_state() -> String:
	var presentation := get_node_or_null(presentation_path)
	return str(presentation.get("current_state")) if presentation != null else "closed"


func set_focus_highlight(is_focused: bool) -> void:
	focused = is_focused
	var door_leaf := get_node_or_null("HingePivot/DoorLeaf") as MeshInstance3D
	if door_leaf == null:
		return
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(0.95, 0.78, 0.25, 1.0) if focused else Color(0.2, 0.13, 0.07, 1.0)
	material.roughness = 0.62
	door_leaf.material_overlay = material
