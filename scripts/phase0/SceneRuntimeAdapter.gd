extends Node

@export_node_path("Node3D") var imported_root_path := NodePath("../ThroneRoomImported")
@export_node_path("Node3D") var collision_root_path := NodePath("../ThroneRoomCollisionRoot")
@export var imported_root_name := "ThroneRoomImported"
@export var collision_root_name := "ThroneRoomCollisionRoot"
@export var bootstrap_collision_enabled := true
@export var lighting_profile := "blender_approx"
@export_file var source_scene_path := ""
@export_multiline var import_notes := ""


func get_imported_root() -> Node3D:
	var explicit_root := get_node_or_null(imported_root_path)
	if explicit_root is Node3D:
		return explicit_root as Node3D
	var host := get_parent()
	if host == null:
		return null
	var named_root := host.get_node_or_null(imported_root_name)
	if named_root is Node3D:
		return named_root as Node3D
	return null


func get_collision_root() -> Node3D:
	var explicit_root := get_node_or_null(collision_root_path)
	if explicit_root is Node3D:
		return explicit_root as Node3D
	var host := get_parent()
	if host == null:
		return null
	var named_root := host.get_node_or_null(collision_root_name)
	if named_root is Node3D:
		return named_root as Node3D
	return null


func get_collision_root_name() -> String:
	return collision_root_name


func should_bootstrap_collision() -> bool:
	return bootstrap_collision_enabled


func should_apply_blender_approx_lighting() -> bool:
	return lighting_profile == "blender_approx"
