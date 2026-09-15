extends Node

class_name CharacterAssetQualificationRunner

const REPORT_PATH := ".harness/verification/character-asset-qualification-report.json"
const DEFAULT_MANIFEST := "res://assets/validation/manifests/character-qualification.example.json"

var _report: Dictionary = {}


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var manifest_path := OS.get_environment("CHARACTER_QUALIFICATION_MANIFEST")
	if manifest_path.is_empty():
		manifest_path = DEFAULT_MANIFEST
	var manifest := _read_json(manifest_path)
	var result := _qualify(manifest)
	_write_report(result)
	print("character_asset_qualification:%s" % str(result.get("status", "failed")))
	get_tree().quit(0 if result.get("status", "") == "qualified" else 1)


func _qualify(manifest: Dictionary) -> Dictionary:
	var report := {
		"contract": "character_asset_qualification.v1",
		"status": "failed",
		"manifest_path": manifest.get("_manifest_path", ""),
		"checks": {},
		"missing": [],
	}
	if manifest.is_empty():
		report["status"] = "not_configured"
		report["missing"] = ["qualification_manifest"]
		return report
	var role_scene_ref := str(manifest.get("role_scene_ref", ""))
	if role_scene_ref.is_empty() or role_scene_ref.contains("<"):
		report["status"] = "not_configured"
		report["missing"] = ["role_scene_ref"]
		return report
	var resource := load(role_scene_ref)
	if not (resource is PackedScene):
		report["missing"] = ["role_scene"]
		return report
	var role_root := (resource as PackedScene).instantiate()
	if role_root == null:
		report["missing"] = ["role_instance"]
		return report
	add_child(role_root)

	var required_methods: Array = manifest.get("required_role_methods", [])
	var missing_methods: Array[String] = []
	for method_name in required_methods:
		if not role_root.has_method(str(method_name)):
			missing_methods.append(str(method_name))
	report["checks"]["role_methods"] = missing_methods.is_empty()
	if not missing_methods.is_empty():
		report["missing"].append_array(missing_methods.map(func(item: String) -> String: return "method:%s" % item))

	var skeleton := _find_skeleton(role_root)
	report["checks"]["skeleton"] = skeleton != null
	if skeleton == null:
		report["missing"].append("Skeleton3D")
	else:
		var missing_bones: Array[String] = []
		var groups: Dictionary = manifest.get("required_bone_groups", {})
		for group_name in groups.keys():
			var found := false
			for candidate in groups[group_name]:
				if skeleton.find_bone(str(candidate)) >= 0:
					found = true
					break
			if not found:
				missing_bones.append(str(group_name))
		report["checks"]["required_bone_groups"] = missing_bones.is_empty()
		report["missing"].append_array(missing_bones.map(func(item: String) -> String: return "bone_group:%s" % item))

	var animation_player := _find_first(role_root, "AnimationPlayer")
	var animation_tree := _find_first(role_root, "AnimationTree")
	report["checks"]["animation_player"] = animation_player != null
	report["checks"]["animation_tree"] = animation_tree != null
	if animation_player == null:
		report["missing"].append("AnimationPlayer")
	if animation_tree == null:
		report["missing"].append("AnimationTree")

	var action_tags: Array = manifest.get("required_action_tags", [])
	var action_clip_map: Dictionary = manifest.get("action_clip_map", {})
	var action_results: Dictionary = {}
	for action_tag in action_tags:
		var clip_name := str(action_clip_map.get(str(action_tag), action_tag))
		var has_clip: bool = animation_player != null and animation_player.has_method("has_animation") and bool(animation_player.has_animation(clip_name))
		action_results[clip_name] = has_clip
		if not has_clip:
			report["missing"].append("action:%s" % clip_name)
	report["checks"]["action_tags"] = not action_results.values().has(false)
	report["action_tags"] = action_results

	var collision_shape := _find_first(self, "CollisionShape3D")
	report["checks"]["collision_shape"] = collision_shape != null
	if collision_shape == null:
		report["missing"].append("CollisionShape3D")

	report["status"] = "qualified" if report["missing"].is_empty() else "failed"
	return report


func _find_skeleton(root: Node) -> Skeleton3D:
	return _find_first(root, "Skeleton3D") as Skeleton3D


func _find_first(root: Node, type_name: String) -> Node:
	if root.get_class() == type_name:
		return root
	for child in root.get_children():
		var found := _find_first(child, type_name)
		if found != null:
			return found
	return null


func _read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not (parsed is Dictionary):
		return {}
	var result: Dictionary = parsed
	result["_manifest_path"] = path
	return result


func _write_report(report: Dictionary) -> void:
	var path := ProjectSettings.globalize_path("res://" + REPORT_PATH)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(report, "\t"))
		file.close()
