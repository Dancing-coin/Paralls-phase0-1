extends MeshInstance3D

@export var range_m := 28.0
@export var half_fov_degrees := 78.0
@export var cone_color := Color(0.45, 0.95, 1.0, 0.55)


func _ready() -> void:
	_rebuild_mesh()
	visible = false


func set_parameters(next_range_m: float, next_half_fov_degrees: float) -> void:
	range_m = max(next_range_m, 0.1)
	half_fov_degrees = clamp(next_half_fov_degrees, 1.0, 89.0)
	_rebuild_mesh()


func set_debug_visible(is_visible: bool) -> void:
	visible = is_visible


func _rebuild_mesh() -> void:
	var depth: float = max(range_m, 0.1)
	var half_width: float = tan(deg_to_rad(half_fov_degrees)) * depth
	var half_height: float = half_width * 0.6

	var apex := Vector3.ZERO
	var top_left := Vector3(-half_width, half_height, -depth)
	var top_right := Vector3(half_width, half_height, -depth)
	var bottom_left := Vector3(-half_width, -half_height, -depth)
	var bottom_right := Vector3(half_width, -half_height, -depth)

	var immediate := ImmediateMesh.new()
	immediate.surface_begin(Mesh.PRIMITIVE_LINES)
	for pair in [
		[apex, top_left],
		[apex, top_right],
		[apex, bottom_left],
		[apex, bottom_right],
		[top_left, top_right],
		[top_right, bottom_right],
		[bottom_right, bottom_left],
		[bottom_left, top_left],
	]:
		immediate.surface_set_color(cone_color)
		immediate.surface_add_vertex(pair[0])
		immediate.surface_add_vertex(pair[1])
	immediate.surface_end()
	mesh = immediate

	var material := StandardMaterial3D.new()
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.albedo_color = cone_color
	material.vertex_color_use_as_albedo = true
	material.no_depth_test = true
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	material_override = material
