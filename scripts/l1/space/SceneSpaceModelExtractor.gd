extends RefCounted

class_name SceneSpaceModelExtractor

var room_id := "room_demo"
var scene_id := "scene_demo"


func extract(root: Node) -> Dictionary:
	var elements: Array[Dictionary] = []
	if root == null:
		return _model(elements)
	_add_element(elements, "zone_focus", "zone", root, ["runtime_main_scene"], [])
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
	if lower_name.contains("interactiveobject") or lower_name.contains("letter"):
		_add_element(elements, "obj_letter", "interaction_object", node, ["interaction_object"], _geometry_refs(node))
	if node is CollisionShape3D:
		var element_id := "collision_%s" % _safe_id(str(node.get_path()))
		_add_element(elements, element_id, "static_obstacle", node, ["collision_shape"], _geometry_refs(node))
	if node is StaticBody3D or lower_name.contains("pillar") or lower_name.contains("wall"):
		var obstacle_id := "obstacle_%s" % _safe_id(str(node.get_path()))
		_add_element(elements, obstacle_id, "occluder", node, ["occluder_candidate"], _geometry_refs(node))
	if node is NavigationRegion3D:
		var lane_id := "navigation_%s" % _safe_id(str(node.get_path()))
		_add_element(elements, lane_id, "navigation_lane", node, ["navigation_region"], ["navigation_region:%s" % str(node.get_path())])
	if lower_name.contains("walk") or lower_name.contains("floor"):
		var lane_from_floor := "navigation_lane_%s" % _safe_id(str(node.get_path()))
		_add_element(elements, lane_from_floor, "navigation_lane", node, ["navigation_from_walkable_surface"], ["navigation_region:derived_from_runtime_walkable:%s" % str(node.get_path())])


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


func _model(elements: Array[Dictionary]) -> Dictionary:
	return {
		"model_id": "scene_space:%s:%s" % [room_id, scene_id],
		"room_id": room_id,
		"scene_id": scene_id,
		"extraction_sources": [
			"godot_node_path",
			"godot_group",
			"godot_metadata",
			"collision_shape",
			"navigation_region_or_walkable_surface",
		],
		"manual_role": "review_only",
		"elements": elements,
	}


func _safe_id(value: String) -> String:
	return value.replace("/", "_").replace(":", "_").replace("@", "_").strip_edges()
