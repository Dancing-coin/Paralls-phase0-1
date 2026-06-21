extends Node

@export_range(0.05, 0.95, 0.01) var faded_alpha := 0.22
@export_range(1.0, 20.0, 0.1) var fade_speed := 10.0
@export_range(1.0, 20.0, 0.1) var restore_speed := 7.0
@export_range(1, 16, 1) var max_ray_hits := 10
@export var sample_height := 1.2

@onready var player: CharacterBody3D = get_parent() as CharacterBody3D
@onready var cam: Camera3D = _find_camera()

var material_by_mesh: Dictionary = {}
var base_alpha_by_mesh: Dictionary = {}

func _physics_process(delta: float) -> void:
	if player == null or cam == null:
		return

	var occluding_meshes := _collect_occluding_meshes()
	_update_fade_state(occluding_meshes, delta)

func _collect_occluding_meshes() -> Dictionary:
	var result: Dictionary = {}
	var space_state: PhysicsDirectSpaceState3D = player.get_world_3d().direct_space_state
	var from := cam.global_position
	var anchor := _get_occlusion_anchor_position()
	var to := anchor + Vector3(0.0, sample_height, 0.0)
	var exclude: Array[RID] = [player.get_rid()]

	for _i in max_ray_hits:
		var query := PhysicsRayQueryParameters3D.create(from, to, 0xFFFFFFFF, exclude)
		query.collide_with_areas = false
		query.collide_with_bodies = true
		query.hit_back_faces = true
		var hit: Dictionary = space_state.intersect_ray(query)
		if hit.is_empty():
			break

		var collider: Object = hit.get("collider")
		if collider is CollisionObject3D:
			exclude.append((collider as CollisionObject3D).get_rid())
		else:
			break

		if _is_fallback_occluder(collider):
			var mesh := _resolve_mesh_for_body(collider)
			if mesh and not _should_skip_low_boundary(mesh):
				result[mesh] = true

	return result

func _is_fallback_occluder(collider: Object) -> bool:
	if not (collider is StaticBody3D):
		return false

	var body := collider as StaticBody3D
	var body_name := body.name
	if not (
		body_name.ends_with("TableTopBody")
		or (body_name.contains("Boundary") and body_name.ends_with("Body"))
	):
		return false

	return true

func _resolve_mesh_for_body(collider: Object) -> MeshInstance3D:
	if not (collider is StaticBody3D):
		return null
	var body := collider as StaticBody3D
	var parent := body.get_parent()
	if parent == null:
		return null

	var mesh_name := body.name
	if mesh_name.ends_with("Body"):
		mesh_name = mesh_name.trim_suffix("Body")
	var mesh_node := parent.get_node_or_null(NodePath(mesh_name))
	if mesh_node is MeshInstance3D:
		return mesh_node as MeshInstance3D
	return null

func _should_skip_low_boundary(mesh: MeshInstance3D) -> bool:
	return mesh.name.contains("Boundary") and sample_height >= 1.0

func _update_fade_state(occluding_meshes: Dictionary, delta: float) -> void:
	var all_meshes: Dictionary = material_by_mesh.duplicate()
	for mesh in occluding_meshes.keys():
		all_meshes[mesh] = true

	for mesh_variant in all_meshes.keys():
		var mesh := mesh_variant as MeshInstance3D
		var material := _get_or_create_override_material(mesh)
		if material == null:
			continue

		var current_alpha := material.albedo_color.a
		var base_alpha: float = base_alpha_by_mesh.get(mesh, 1.0)
		var target_alpha := faded_alpha if occluding_meshes.has(mesh) else base_alpha
		var speed := fade_speed if occluding_meshes.has(mesh) else restore_speed
		var next_alpha := move_toward(current_alpha, target_alpha, speed * delta)

		var color := material.albedo_color
		color.a = next_alpha
		material.albedo_color = color

func _get_or_create_override_material(mesh: MeshInstance3D) -> StandardMaterial3D:
	if material_by_mesh.has(mesh):
		return material_by_mesh[mesh] as StandardMaterial3D

	var source_material: Material = mesh.material_override
	if source_material == null and mesh.mesh != null and mesh.mesh.get_surface_count() > 0:
		source_material = mesh.get_active_material(0)
	if not (source_material is StandardMaterial3D):
		return null

	var material_copy := (source_material as StandardMaterial3D).duplicate() as StandardMaterial3D
	material_copy.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mesh.material_override = material_copy
	material_by_mesh[mesh] = material_copy
	base_alpha_by_mesh[mesh] = material_copy.albedo_color.a
	return material_copy

func _find_camera() -> Camera3D:
	if player and player.has_method("get_camera"):
		var player_camera: Variant = player.get_camera()
		if player_camera is Camera3D:
			return player_camera as Camera3D
	var found := player.find_child("Camera3D", true, false)
	if found is Camera3D:
		return found as Camera3D
	return null

func _get_occlusion_anchor_position() -> Vector3:
	if player and player.has_method("get_control_anchor_position"):
		var anchor: Variant = player.get_control_anchor_position()
		if anchor is Vector3:
			return anchor
	return player.global_position
