extends Node

class_name EnvironmentAssetQualificationRunner

const REPORT_PATH := ".harness/verification/environment-asset-qualification-report.json"
const DEFAULT_MANIFEST := "res://assets/validation/manifests/environment-qualification.example.json"


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	var manifest_path := OS.get_environment("ENVIRONMENT_QUALIFICATION_MANIFEST")
	if manifest_path.is_empty():
		manifest_path = DEFAULT_MANIFEST
	var manifest := _read_json(manifest_path)
	var report := _qualify(manifest)
	_write_report(report)
	print("environment_asset_qualification:%s" % str(report.get("status", "failed")))
	get_tree().quit(0 if report.get("status", "") == "qualified" else 1)


func _qualify(manifest: Dictionary) -> Dictionary:
	var report := {
		"contract": "environment_asset_qualification.v1",
		"status": "failed",
		"manifest_path": manifest.get("_manifest_path", ""),
		"checks": {},
		"missing": [],
	}
	if manifest.is_empty():
		report["status"] = "not_configured"
		report["missing"] = ["qualification_manifest"]
		return report
	var scene_ref := str(manifest.get("environment_scene_ref", ""))
	if scene_ref.is_empty() or scene_ref.contains("<"):
		report["status"] = "not_configured"
		report["missing"] = ["environment_scene_ref"]
		return report
	var resource := load(scene_ref)
	if not (resource is PackedScene):
		report["missing"] = ["environment_scene"]
		return report
	var environment_root := (resource as PackedScene).instantiate()
	add_child(environment_root)
	var mesh_count := _count_type(environment_root, "MeshInstance3D")
	var imported_collision_count := _count_type(environment_root, "CollisionShape3D")
	report["checks"]["environment_mesh"] = mesh_count > 0
	report["checks"]["imported_collision"] = imported_collision_count > 0
	report["mesh_count"] = mesh_count
	report["imported_collision_count"] = imported_collision_count
	if mesh_count == 0:
		report["missing"].append("MeshInstance3D")

	var collision_ref := str(manifest.get("collision_scene_ref", ""))
	var collision_count := 0
	if not collision_ref.is_empty() and not collision_ref.contains("<"):
		var collision_resource := load(collision_ref)
		if collision_resource is PackedScene:
			var collision_root := (collision_resource as PackedScene).instantiate()
			add_child(collision_root)
			collision_count = _count_type(collision_root, "CollisionShape3D")
	report["checks"]["collision_scene"] = collision_count > 0
	report["collision_scene_shape_count"] = collision_count
	if collision_count == 0:
		report["missing"].append("collision_scene:CollisionShape3D")

	report["checks"]["navigation_contract"] = manifest.has("required_anchor_ids")
	if not manifest.has("required_anchor_ids"):
		report["missing"].append("required_anchor_ids")
	report["checks"]["state_fixture_contract"] = manifest.has("required_state_fixture_ids")
	if not manifest.has("required_state_fixture_ids"):
		report["missing"].append("required_state_fixture_ids")
	report["status"] = "qualified" if report["missing"].is_empty() else "failed"
	return report


func _count_type(root: Node, type_name: String) -> int:
	var count := 1 if root.get_class() == type_name else 0
	for child in root.get_children():
		count += _count_type(child, type_name)
	return count


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
