extends SceneTree
class_name MotionRetargetBuildRunner

const MotionRetargeterRef = preload("res://scripts/character/MotionRetargeter.gd")
const DEFAULT_LIBRARY := "res://assets/motion_library/approved/humanoid.v1/street_locomotion.tres"
const DEFAULT_PROFILE := "res://assets/skeleton_profiles/humanoid.v1.json"
const DEFAULT_OUTPUT_ROOT := "res://assets/motion_library/generated"

func _initialize() -> void:
	call_deferred("_run")

func _run() -> void:
	var args := _arguments()
	var source_library_path := String(args.get("source-library", DEFAULT_LIBRARY))
	var source_profile_path := String(args.get("source-profile", DEFAULT_PROFILE))
	var target_profile_path := String(args.get("target-profile", DEFAULT_PROFILE))
	var source_library := ResourceLoader.load(source_library_path) as AnimationLibrary
	var source_profile := _read_json(source_profile_path)
	var target_profile := _read_json(target_profile_path)
	var body_profile := {"profile_id": String(args.get("body-profile-id", "body:female_t.default")), "relative_stride_scale": 1.0}
	var calibration_profile := {"profile_id": String(args.get("calibration-profile-id", "calibration:humanoid.v1.street.default")), "root_motion_scale": 1.0}
	var retargeter := MotionRetargeterRef.new()
	var source_digest := _digest(source_library_path)
	var target_digest := String(target_profile.get("hierarchy_digest", ""))
	var cache_key := retargeter.compute_cache_key(
		String(source_profile.get("motion_library_id", source_profile.get("skeleton_profile_id", ""))),
		source_digest,
		String(target_profile.get("skeleton_profile_id", "")),
		target_digest,
		String(body_profile.get("profile_id", "")),
		String(calibration_profile.get("profile_id", "")),
		MotionRetargeterRef.SOLVER_VERSION
	)
	var output_root := String(args.get("output-root", DEFAULT_OUTPUT_ROOT)).trim_suffix("/")
	var output_dir := output_root.path_join(cache_key)
	var output_path := output_dir.path_join("retargeted_library.tres")
	var result := retargeter.build_library(source_library, source_profile, target_profile, body_profile, calibration_profile, output_path)
	result["source_library_path"] = source_library_path
	result["target_profile_path"] = target_profile_path
	result["cache_key"] = cache_key
	if result.get("accepted", false):
		var output_digest := _digest(output_path)
		var manifest := _manifest(result, source_profile, target_profile, body_profile, calibration_profile, source_digest, target_digest, output_path, output_digest)
		_write_json(output_dir.path_join("manifest.json"), manifest)
		_write_json(output_dir.path_join("qualification-report.json"), {"accepted": true, "realization_mode": "retargeted_library", "cache_key": cache_key, "clip_reports": result.get("clip_reports", [])})
		print("motion_retarget_build:accepted:%s" % cache_key)
		quit(0)
	else:
		_write_json(output_dir.path_join("qualification-report.json"), {"accepted": false, "cache_key": cache_key, "rejection_reason": result.get("rejection_reason", "")})
		print("motion_retarget_build:rejected:%s" % result.get("rejection_reason", "unknown"))
		quit(1)

func _manifest(result: Dictionary, source_profile: Dictionary, target_profile: Dictionary, body_profile: Dictionary, calibration_profile: Dictionary, source_digest: String, target_digest: String, output_path: String, output_digest: String) -> Dictionary:
	var clips := {}
	for report in result.get("clip_reports", []):
		clips[report.get("clip_ref", "")] = {
			"clip_ref": report.get("clip_ref", ""),
			"duration_seconds": 0.0,
			"track_count": int(report.get("track_count", 1)),
			"canonical_bone_ids": [],
			"loop_mode": "linear",
		}
	return {
		"motion_library_id": source_profile.get("motion_library_id", "motionlib:retargeted@1"),
		"skeleton_profile_id": target_profile.get("skeleton_profile_id", ""),
		"animation_library_ref": output_path,
		"clips": clips,
		"semantic_actions": {},
		"source_digest": source_digest,
		"qualification_report_ref": output_path.get_base_dir().path_join("qualification-report.json"),
		"qualification_status": "approved",
		"realization_mode": "retargeted_library",
		"cache_key": result.get("cache_key", ""),
		"source_library_id": source_profile.get("motion_library_id", ""),
		"source_library_digest": source_digest,
		"target_profile_id": target_profile.get("skeleton_profile_id", ""),
		"target_profile_digest": target_digest,
		"body_profile_id": body_profile.get("profile_id", ""),
		"calibration_profile_id": calibration_profile.get("profile_id", ""),
		"ik_profile_id": calibration_profile.get("ik_profile_id", "ik:humanoid.v1.default"),
		"solver_version": MotionRetargeterRef.SOLVER_VERSION,
		"output_digest": output_digest,
	}

func _arguments() -> Dictionary:
	var result := {}
	var values := OS.get_cmdline_user_args()
	if values.is_empty():
		values = OS.get_cmdline_args()
	for index in values.size():
		var value := String(values[index])
		if value.begins_with("--") and index + 1 < values.size():
			result[value.trim_prefix("--")] = values[index + 1]
	return result

func _read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed if parsed is Dictionary else {}

func _digest(path: String) -> String:
	if not FileAccess.file_exists(path):
		return ""
	return "sha256:%s" % FileAccess.get_sha256(path)

func _write_json(path: String, value: Dictionary) -> void:
	var absolute := ProjectSettings.globalize_path(path)
	DirAccess.make_dir_recursive_absolute(absolute.get_base_dir())
	var file := FileAccess.open(absolute, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(value, "\t"))
		file.close()
