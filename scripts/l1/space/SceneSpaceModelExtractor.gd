extends RefCounted

class_name SceneSpaceModelExtractor

var room_id := "room_demo"
var scene_id := "scene_demo"
var max_collision_shape_elements := 64
var max_navigation_lane_elements := 32
var _collision_shape_element_count := 0
var _navigation_lane_element_count := 0
var _real_navigation_region_available := false


func extract(root: Node) -> Dictionary:
	var elements: Array[Dictionary] = []
	_collision_shape_element_count = 0
	_navigation_lane_element_count = 0
	_real_navigation_region_available = false
	if root == null:
		return _model(elements)
	_add_element(elements, "zone_focus", "zone", root, ["runtime_main_scene"], [])
	_real_navigation_region_available = _has_navigation_region(root)
	_walk(root, elements)
	return _model(elements)


func write_artifact(model: Dictionary, relative_path: String = ".harness/verification/l1-space-model-runtime.json") -> String:
	var path := ProjectSettings.globalize_path("res://" + relative_path)
	var dir := path.get_base_dir()
	DirAccess.make_dir_recursive_absolute(dir)
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return ""
	file.store_string(JSON.stringify(model, "\t"))
	file.close()
	return path


func _walk(node: Node, elements: Array[Dictionary]) -> void:
	if node == null:
		return
	_maybe_add_node(node, elements)
	for child: Node in node.get_children():
		_walk(child, elements)


func _maybe_add_node(node: Node, elements: Array[Dictionary]) -> void:
	var lower_name := node.name.to_lower()
	if lower_name.contains("environmentstatenode"):
		_add_element(elements, "env_lamp", "environment_anchor", node, ["environment_state_node"], [])
	if lower_name.contains("interactiveobject") or node.has_meta("grounding_refs"):
		# Reviewed scene objects supply their stable ID explicitly. The legacy
		# fallback keeps the original single-letter fixture readable.
		var interaction_object_id := str(node.get_meta("entity_ref", "")).strip_edges()
		if interaction_object_id.is_empty():
			var object_id_value: Variant = node.get("object_id")
			if object_id_value != null:
				interaction_object_id = str(object_id_value).strip_edges()
		if interaction_object_id.is_empty():
			interaction_object_id = "obj_letter"
		_add_element(elements, interaction_object_id, "interaction_object", node, ["interaction_object"], _geometry_refs(node))
	if _is_collision_aggregate_root(node):
		var aggregate_id := "collision_root_%s" % _safe_id(str(node.get_path()))
		_add_element(elements, aggregate_id, "static_obstacle", node, ["collision_shape_aggregate"], _geometry_refs_limited(node, 12))
	if node is CollisionShape3D and _collision_shape_element_count < max_collision_shape_elements:
		var element_id := "collision_%s" % _safe_id(str(node.get_path()))
		_add_element(elements, element_id, "static_obstacle", node, ["collision_shape"], _geometry_refs(node))
		_collision_shape_element_count += 1
	if node is StaticBody3D or lower_name.contains("pillar") or lower_name.contains("wall"):
		var obstacle_id := "obstacle_%s" % _safe_id(str(node.get_path()))
		_add_element(elements, obstacle_id, "occluder", node, ["occluder_candidate"], _geometry_refs(node))
	if node is NavigationRegion3D:
		var lane_id := "navigation_%s" % _safe_id(str(node.get_path()))
		_add_element(elements, lane_id, "navigation_lane", node, ["navigation_region"], ["navigation_region:%s" % str(node.get_path())])
	if not _real_navigation_region_available and (lower_name.contains("walk") or lower_name.contains("floor")) and _navigation_lane_element_count < max_navigation_lane_elements:
		var lane_from_floor := "navigation_lane_%s" % _safe_id(str(node.get_path()))
		_add_element(elements, lane_from_floor, "navigation_lane", node, ["navigation_from_walkable_surface"], ["walkable_surface:derived_from_runtime_walkable:%s" % str(node.get_path())])
		_navigation_lane_element_count += 1


func _add_element(
	elements: Array[Dictionary],
	element_id: String,
	element_type: String,
	node: Node,
	semantic_tags: Array[String],
	extra_refs: Array[String]
) -> void:
	for existing: Dictionary in elements:
		if str(existing.get("element_id", "")) == element_id and str(existing.get("element_type", "")) == element_type:
			return
	var refs: Array[String] = [
		"node_path:%s" % str(node.get_path()),
		"runtime_source_ref:runtime://node%s" % str(node.get_path()),
	]
	for group_name: StringName in node.get_groups():
		refs.append("group:%s" % str(group_name))
	if node.has_meta("l1_space_type") or node.has_meta("element_id") or node.has_meta("zone_id"):
		refs.append("metadata:%s" % str(node.get_path()))
	if node.has_meta("grounding_refs"):
		for grounding_ref: Variant in node.get_meta("grounding_refs"):
			var normalized_ref := str(grounding_ref)
			if not normalized_ref.is_empty():
				refs.append(normalized_ref)
	for ref: String in extra_refs:
		if ref != "":
			refs.append(ref)
	elements.append({
		"element_id": element_id,
		"element_type": element_type,
		"source_refs": refs,
		"semantic_tags": semantic_tags,
		"confidence": 0.8,
	})


func _geometry_refs(node: Node) -> Array[String]:
	var refs: Array[String] = []
	if node is CollisionShape3D:
		refs.append("collision_shape:%s" % str(node.get_path()))
	for child: Node in node.get_children():
		if child is CollisionShape3D:
			refs.append("collision_shape:%s" % str(child.get_path()))
	return refs


func _geometry_refs_limited(node: Node, limit: int) -> Array[String]:
	var refs: Array[String] = []
	_collect_collision_refs(node, refs, limit)
	return refs


func _collect_collision_refs(node: Node, refs: Array[String], limit: int) -> void:
	if refs.size() >= limit:
		return
	if node is CollisionShape3D:
		refs.append("collision_shape:%s" % str(node.get_path()))
	for child: Node in node.get_children():
		if refs.size() >= limit:
			return
		_collect_collision_refs(child, refs, limit)


func _is_collision_aggregate_root(node: Node) -> bool:
	var lower_name := node.name.to_lower()
	return lower_name.contains("collisionroot") or lower_name.contains("collision_root") or lower_name.contains("greybox")


func _has_navigation_region(node: Node) -> bool:
	if node is NavigationRegion3D:
		return true
	for child: Node in node.get_children():
		if _has_navigation_region(child):
			return true
	return false


func _model(elements: Array[Dictionary]) -> Dictionary:
	return {
		"model_id": "scene_space:%s:%s" % [room_id, scene_id],
		"room_id": room_id,
		"scene_id": scene_id,
		"extraction_sources": [
			"godot_node_path",
			"godot_group",
			"godot_metadata",
			"reviewed_grounding_metadata",
			"collision_shape",
			"navigation_region",
			"walkable_surface_fallback",
		],
		"manual_role": "review_only",
		"elements": elements,
	}


func _safe_id(value: String) -> String:
	return value.replace("/", "_").replace(":", "_").replace("@", "_").strip_edges()
