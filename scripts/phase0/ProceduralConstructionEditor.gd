extends Node2D

class_name ProceduralConstructionEditor

## Presentation-only Construction editor. Backend events remain authoritative.

@export var grid_size := 1.0
@export var grid_extent := 12
var committed_cells: Dictionary = {}
var speculative_cells: Dictionary = {}
var backend_projection: Dictionary = {}
var facility_statuses: Dictionary = {}
var job_statuses: Dictionary = {}
var run_statuses: Dictionary = {}
var replay_timeline: Array = []
var _status_label: Label


func _ready() -> void:
	_status_label = Label.new()
	_status_label.text = "Construction editor: backend-authoritative"
	_status_label.position = Vector2(20, 20)
	add_child(_status_label)
	queue_redraw()


func preview_placement(anchor: Vector2i, footprint: Vector2i, orientation: int) -> bool:
	var cells := _occupied_cells(anchor, footprint, orientation)
	if cells.is_empty():
		_clear_speculative()
		return false
	for cell in cells:
		if committed_cells.has(cell):
			_clear_speculative()
			_status_label.text = "Placement conflict (authoritative occupancy)"
			return false
	speculative_cells.clear()
	for cell in cells:
		speculative_cells[cell] = true
	_status_label.text = "Draft placement preview — submit typed intent to backend"
	queue_redraw()
	return true


func apply_backend_projection(projection: Dictionary) -> void:
	## Only committed backend projection may update the visible truth.
	backend_projection = projection.duplicate(true)
	committed_cells.clear()
	for raw_cell in projection.get("occupied_cells", []):
		if raw_cell is Array and raw_cell.size() == 2:
			committed_cells[Vector2i(int(raw_cell[0]), int(raw_cell[1]))] = true
	facility_statuses = _status_map(projection.get("facilities", {}), "facility_ref", "lifecycle_status")
	job_statuses = _status_map(projection.get("jobs", {}), "job_ref", "status")
	run_statuses = _status_map(projection.get("runs", {}), "run_ref", "status")
	_clear_speculative()
	_status_label.text = "Construction projection synced from backend (%d facilities, %d jobs, %d runs)" % [
		facility_statuses.size(), job_statuses.size(), run_statuses.size()
	]
	queue_redraw()


func apply_backend_replay_timeline(timeline: Array) -> void:
	## Replay is a read-only presentation input; it never mutates gameplay truth.
	replay_timeline = timeline.duplicate(true)
	_clear_speculative()
	_status_label.text = "Replay timeline loaded (%d committed steps)" % replay_timeline.size()
	queue_redraw()


func backend_projection_summary() -> Dictionary:
	## Expose only backend-derived status for a read-only HUD or inspector.
	return {
		"facility_statuses": facility_statuses.duplicate(true),
		"job_statuses": job_statuses.duplicate(true),
		"run_statuses": run_statuses.duplicate(true),
		"replay_step_count": replay_timeline.size(),
	}


func reject_backend_intent(reason: String) -> void:
	_clear_speculative()
	_status_label.text = "Rejected: " + reason


func _clear_speculative() -> void:
	speculative_cells.clear()
	queue_redraw()


func _status_map(values: Variant, id_key: String, status_key: String) -> Dictionary:
	var result: Dictionary = {}
	if values is Dictionary:
		for key in values:
			var row = values[key]
			if row is Dictionary and row.has(status_key):
				result[str(row.get(id_key, key))] = row[status_key]
	return result


func build_typed_draft(
	blueprint_ref: String,
	anchor: Vector2i,
	footprint: Vector2i,
	orientation: int,
) -> Dictionary:
	## Presentation-only Canonical JSON draft. The backend owns validation,
	## declaration/content digests, descriptor binding and activation.
	return {
		"blueprint_ref": blueprint_ref,
		"anchor": {"x": anchor.x, "y": anchor.y},
		"footprint": {"width": footprint.x, "depth": footprint.y},
		"orientation": orientation,
	}


func _occupied_cells(anchor: Vector2i, footprint: Vector2i, orientation: int) -> Array[Vector2i]:
	if orientation not in [0, 90, 180, 270] or footprint.x <= 0 or footprint.y <= 0:
		return []
	var cells: Array[Vector2i] = []
	for x in range(footprint.x):
		for y in range(footprint.y):
			var local := Vector2i(x, y)
			var rotated: Vector2i
			match orientation:
				0: rotated = local
				90: rotated = Vector2i(-local.y, local.x)
				180: rotated = Vector2i(-local.x, -local.y)
				270: rotated = Vector2i(local.y, -local.x)
			cells.append(anchor + rotated)
	return cells


func _draw() -> void:
	for x in range(-grid_extent, grid_extent + 1):
		draw_line(Vector2(400 + x * grid_size, 40), Vector2(400 + x * grid_size, 40 + 2 * grid_extent * grid_size), Color(0.25, 0.32, 0.36, 0.45))
	for z in range(-grid_extent, grid_extent + 1):
		draw_line(Vector2(400 - grid_extent * grid_size, 40 + z * grid_size), Vector2(400 + grid_extent * grid_size, 40 + z * grid_size), Color(0.25, 0.32, 0.36, 0.45))
	for cell in committed_cells:
		_draw_cell(cell, Color(0.16, 0.55, 0.35, 0.8))
	for cell in speculative_cells:
		_draw_cell(cell, Color(0.25, 0.65, 0.85, 0.55))


func _draw_cell(cell: Vector2i, color: Color) -> void:
	var center := Vector2(400 + cell.x * grid_size, 40 + cell.y * grid_size)
	var half := grid_size * 0.45
	var points := PackedVector2Array([
		center + Vector2(-half, -half), center + Vector2(half, -half),
		center + Vector2(half, half), center + Vector2(-half, half),
	])
	draw_colored_polygon(points, color)
