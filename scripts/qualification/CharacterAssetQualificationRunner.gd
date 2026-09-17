extends SceneTree

class_name CharacterAssetQualificationRunner

const REPORT_PATH := ".harness/verification/character-asset-qualification-report.json"
const DEFAULT_MANIFEST := "res://assets/validation/manifests/character-qualification.example.json"
const CharacterAssetQualificationRef = preload("res://scripts/character/CharacterAssetQualification.gd")

var _report: Dictionary = {}


func _initialize() -> void:
	_run()


func _run() -> void:
	var manifest_path := OS.get_environment("CHARACTER_QUALIFICATION_MANIFEST")
	var package_path := _command_line_package_path()
	if not package_path.is_empty():
		manifest_path = "res://" + package_path + "/manifest.json"
	if manifest_path.is_empty():
		manifest_path = DEFAULT_MANIFEST
	var manifest := _read_json(manifest_path)
	var result := _qualify(manifest)
	_write_report(result)
	print("character_asset_qualification:%s" % str(result.get("status", "failed")))
	quit(0 if result.get("status", "") in ["qualified", "qualified_with_fallback"] else 1)


func _command_line_package_path() -> String:
	var arguments := OS.get_cmdline_user_args()
	if arguments.is_empty():
		arguments = OS.get_cmdline_args()
	for index in arguments.size() - 1:
		if arguments[index] == "--package":
			return str(arguments[index + 1]).trim_prefix("res://").trim_suffix("/")
	return ""


func _qualify(manifest: Dictionary) -> Dictionary:
	var candidate := manifest.duplicate(true)
	var role_root := _instantiate_role(candidate)
	if role_root != null:
		candidate["_skeleton"] = _find_skeleton(role_root)
		candidate["clips"] = _collect_clips(_find_first(role_root, "AnimationPlayer") as AnimationPlayer)
		_apply_clip_aliases(candidate)
	var report := CharacterAssetQualificationRef.qualify(candidate)
	var qualification_blockers: Variant = manifest.get("qualification_blockers", [])
	if qualification_blockers is Array and not qualification_blockers.is_empty():
		for blocker in qualification_blockers:
			if not report["reasons"].has(str(blocker)):
				report["reasons"].append(str(blocker))
		report["status"] = "rejected"
	report["manifest_path"] = manifest.get("_manifest_path", "")
	for key in ["delivery_level", "fallback", "locomotion_compatibility", "provenance", "source", "report_path"]:
		if manifest.has(key):
			report[key] = manifest[key]
	return report


func _instantiate_role(manifest: Dictionary) -> Node:
	var role_scene_ref := str(manifest.get("role_scene_ref", ""))
	var source_model_path := str(manifest.get("source_model_path", ""))
	var resource := load(role_scene_ref if not role_scene_ref.is_empty() and not role_scene_ref.contains("<") else source_model_path)
	return (resource as PackedScene).instantiate() if resource is PackedScene else null


func _apply_clip_aliases(manifest: Dictionary) -> void:
	var clips: Dictionary = manifest.get("clips", {})
	var aliases: Variant = manifest.get("clip_aliases", {})
	if not aliases is Dictionary:
		return
	for alias in aliases:
		var source_ref := str(aliases[alias])
		if clips.has(source_ref):
			clips[str(alias)] = clips[source_ref]


func _collect_clips(animation_player: AnimationPlayer) -> Dictionary:
	var clips := {}
	if animation_player == null:
		return clips
	for clip_name in animation_player.get_animation_list():
		clips[str(clip_name)] = animation_player.get_animation(clip_name)
	return clips


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
	_write_report_at(REPORT_PATH, report)
	var package_report := str(report.get("report_path", ""))
	if not package_report.is_empty():
		_write_report_at(package_report, report)
	var provenance: Variant = report.get("provenance", {})
	if provenance is Dictionary:
		var source_report := str(provenance.get("qualification_report_ref", ""))
		if not source_report.is_empty():
			_write_report_at(source_report, report)


func _write_report_at(relative_path: String, report: Dictionary) -> void:
	var normalized := relative_path.trim_prefix("res://")
	var path := ProjectSettings.globalize_path("res://" + normalized)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(report, "\t"))
		file.close()
