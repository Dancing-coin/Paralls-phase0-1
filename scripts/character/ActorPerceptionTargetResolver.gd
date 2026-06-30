extends RefCounted

class_name ActorPerceptionTargetResolver

var target_property_names := PackedStringArray(["actor_id", "object_id", "environment_id"])

func resolve_targets(scene_root: Node, owner: Node3D) -> Array[Node3D]:
	var resolved: Array[Node3D] = []
	if scene_root == null:
		return resolved
	_collect_targets(scene_root, owner, resolved)
	return resolved

func _collect_targets(node: Node, owner: Node3D, resolved: Array[Node3D]) -> void:
	if node is Node3D:
		var node_3d := node as Node3D
		if node_3d != owner and _is_target_candidate(node_3d) and not resolved.has(node_3d):
			resolved.append(node_3d)
	for child: Node in node.get_children():
		_collect_targets(child, owner, resolved)

func _is_target_candidate(node: Node3D) -> bool:
	for property_name: String in target_property_names:
		var value: Variant = node.get(property_name)
		if value != null and str(value) != "":
			return true
	return false
