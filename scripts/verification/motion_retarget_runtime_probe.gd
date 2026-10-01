extends SceneTree

const MotionRetargeterRef = preload("res://scripts/character/MotionRetargeter.gd")
const CharacterEmbodimentAssetRegistryRef = preload("res://scripts/character/CharacterEmbodimentAssetRegistry.gd")
const StreetCharacterSkinRef = preload("res://scripts/street_combat/StreetCharacterSkin.gd")
const SOURCE_LIBRARY_PATH := "res://assets/motion_library/approved/humanoid.v1/street_locomotion.tres"
const SOURCE_MANIFEST_PATH := "res://assets/motion_library/approved/humanoid.v1/street_locomotion.manifest.json"
const TARGET_PROFILE_PATH := "res://assets/skeleton_profiles/humanoid.v1.json"
const BODY_PROFILE_PATH := "res://assets/characters/profiles/body/female_t.default.json"
const CALIBRATION_PROFILE_PATH := "res://assets/characters/profiles/calibration/humanoid.v1.street.default.json"
const IK_PROFILE_PATH := "res://assets/characters/profiles/ik/humanoid.v1.default.json"
const EXPECTED_CLIPS := ["idle", "walking2", "running", "jump", "boxing", "sword_attack"]
const PACKAGE_ID := "female_t_external"


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var source_manifest := _read_json(SOURCE_MANIFEST_PATH)
	var source_profile := _read_json(TARGET_PROFILE_PATH)
	source_profile["motion_library_id"] = str(source_manifest.get("motion_library_id", ""))
	source_profile["digest"] = str(source_manifest.get("source_digest", ""))
	var target_profile := source_profile.duplicate(true)
	target_profile["digest"] = str(source_profile.get("hierarchy_digest", ""))
	var body_profile := _read_json(BODY_PROFILE_PATH)
	var calibration_profile := _read_json(CALIBRATION_PROFILE_PATH)
	var ik_profile := _read_json(IK_PROFILE_PATH)
	var retargeter := MotionRetargeterRef.new()
	var source_digest := str(source_manifest.get("source_digest", ""))
	var target_digest := str(target_profile.get("hierarchy_digest", ""))
	var body_id := str(body_profile.get("profile_id", ""))
	var calibration_id := str(calibration_profile.get("profile_id", ""))
	var cache_key_a := retargeter.compute_cache_key(str(source_profile.get("motion_library_id", "")), source_digest, str(target_profile.get("skeleton_profile_id", "")), target_digest, body_id, calibration_id, MotionRetargeterRef.SOLVER_VERSION)
	var cache_key_b := retargeter.compute_cache_key(str(source_profile.get("motion_library_id", "")), source_digest, str(target_profile.get("skeleton_profile_id", "")), target_digest, body_id, calibration_id, MotionRetargeterRef.SOLVER_VERSION)
	var output_dir := "user://motion_retarget_runtime_probe"
	var output_path := output_dir.path_join("retargeted_library.tres")
	var retarget_result: Dictionary = retargeter.build_library(ResourceLoader.load(SOURCE_LIBRARY_PATH) as AnimationLibrary, source_profile, target_profile, body_profile, calibration_profile, output_path)
	var cache_key_stable := cache_key_a == cache_key_b and cache_key_a == str(retarget_result.get("cache_key", ""))
	var runtime_manifest := _build_runtime_manifest(source_manifest, target_profile, body_profile, calibration_profile, ik_profile, retarget_result, output_path, output_dir.path_join("qualification-report.json"))
	var qualification_report := {"accepted": true, "realization_mode": "retargeted_library", "cache_key": cache_key_a, "clip_reports": retarget_result.get("clip_reports", [])}
	_write_json(runtime_manifest.get("qualification_report_ref", ""), qualification_report)
	var registry := CharacterEmbodimentAssetRegistryRef.new()
	var library_id := StringName(str(runtime_manifest.get("motion_library_id", "")))
	var retargeted_library := ResourceLoader.load(output_path) as AnimationLibrary
	var target_tracks_valid := bool(retarget_result.get("accepted", false)) and _target_tracks_valid(retargeted_library, target_profile)
	var registered := registry.register_motion_library(library_id, runtime_manifest, retargeted_library)
	var six_states_valid := registered and _six_states_valid(retargeted_library)
	var clip_reports: Array = retarget_result.get("clip_reports", [])
	var foot_contact_valid := registered and _clip_gate_valid(clip_reports, "foot")
	var hand_socket_valid := registered and _clip_gate_valid(clip_reports, "hand") and _clip_gate_valid(clip_reports, "weapon_slot") and not str(ik_profile.get("weapon_anchor_policy", "")).is_empty()
	var skin_states_valid := await _play_target_states(retargeted_library, library_id, registry, cache_key_a)
	var root_motion_single_consume := await _root_motion_single_consume()
	var rejected_output_blocked := _rejected_output_blocked(registry, runtime_manifest, retargeted_library)
	var fields := {
		"cache_key_stable": cache_key_stable,
		"target_tracks_valid": target_tracks_valid,
		"six_states_valid": six_states_valid and skin_states_valid,
		"foot_contact_valid": foot_contact_valid,
		"hand_socket_valid": hand_socket_valid,
		"root_motion_single_consume": root_motion_single_consume,
		"rejected_output_blocked": rejected_output_blocked,
	}
	for field in fields:
		print("%s=%s" % [field, str(bool(fields[field])).to_lower()])
	print("failure_context=package=%s cache_key=%s clip_ref=%s" % [PACKAGE_ID, cache_key_a, "idle|walking2|running|jump|boxing|sword_attack"])
	quit(0 if _all_true(fields) else 1)


func _build_runtime_manifest(source_manifest: Dictionary, target_profile: Dictionary, body_profile: Dictionary, calibration_profile: Dictionary, ik_profile: Dictionary, result: Dictionary, output_path: String, report_path: String) -> Dictionary:
	var clips: Dictionary = source_manifest.get("clips", {}).duplicate(true)
	var semantic_actions: Dictionary = source_manifest.get("semantic_actions", {}).duplicate(true)
	for action_id in semantic_actions:
		var action: Dictionary = semantic_actions[action_id].duplicate(true)
		action["realization_mode"] = "retargeted_library"
		semantic_actions[action_id] = action
	return {
		"motion_library_id": "motionlib:humanoid.v1.female_t.retarget@1",
		"skeleton_profile_id": target_profile.get("skeleton_profile_id", ""),
		"animation_library_ref": output_path,
		"clips": clips,
		"semantic_actions": semantic_actions,
		"source_digest": source_manifest.get("source_digest", ""),
		"qualification_report_ref": report_path,
		"qualification_status": "approved",
		"realization_mode": "retargeted_library",
		"cache_key": result.get("cache_key", ""),
		"source_library_id": source_manifest.get("motion_library_id", ""),
		"source_library_digest": source_manifest.get("source_digest", ""),
		"target_profile_id": target_profile.get("skeleton_profile_id", ""),
		"target_profile_digest": target_profile.get("hierarchy_digest", ""),
		"body_profile_id": body_profile.get("profile_id", ""),
		"calibration_profile_id": calibration_profile.get("profile_id", ""),
		"ik_profile_id": ik_profile.get("profile_id", ""),
		"solver_version": MotionRetargeterRef.SOLVER_VERSION,
		"output_digest": _digest(output_path),
	}


func _play_target_states(library: AnimationLibrary, library_id: StringName, registry: CharacterEmbodimentAssetRegistry, cache_key: String) -> bool:
	var skin := StreetCharacterSkinRef.new()
	# Keep the probe scene package-free so it cannot mount an unqualified source
	# library before the target retargeted resource is explicitly mounted.
	skin.package_id = ""
	var animation_player := AnimationPlayer.new()
	animation_player.name = "AnimationPlayer"
	var rig := Node3D.new()
	rig.name = "rig"
	var skeleton := Skeleton3D.new()
	skeleton.name = "Skeleton3D"
	var target_profile := _read_json(TARGET_PROFILE_PATH)
	for raw_bone_name in target_profile.get("canonical_bones", {}).values():
		skeleton.add_bone(str(raw_bone_name))
	rig.add_child(skeleton)
	skin.add_child(rig)
	animation_player.add_animation_library(&"central", library)
	skin.add_child(animation_player)
	get_root().add_child(skin)
	await process_frame
	if not skin.mount_motion_library(library, library_id, "retargeted_library"):
		return false
	var actions := [
		["action:locomotion.walk", "walk", "walking2"],
		["action:locomotion.run", "run", "running"],
		["action:melee.boxing", "boxing", "boxing"],
		["action:melee.sword_attack", "sword_attack", "sword_attack"],
	]
	for action in actions:
		var resolution := {"accepted": true, "clip_ref": action[2], "motion_library_id": String(library_id), "realization_mode": "retargeted_library", "animation_library": library, "cache_key": cache_key}
		var played := skin.play_semantic_action(str(action[0]), str(action[1]), "retargeted", 1.0, resolution)
		if not bool(played.get("playback_accepted", false)):
			return false
	return true


func _root_motion_single_consume() -> bool:
	var skin := StreetCharacterSkinRef.new()
	get_root().add_child(skin)
	await process_frame
	if not skin.has_method("reset_root_motion"):
		return false
	skin.reset_root_motion()
	skin.consume_root_motion_delta()
	skin.consume_root_motion_delta()
	return int(skin.get_root_motion_consume_count()) == 1


func _rejected_output_blocked(registry: CharacterEmbodimentAssetRegistry, manifest: Dictionary, library: AnimationLibrary) -> bool:
	var rejected := manifest.duplicate(true)
	rejected["qualification_status"] = "rejected"
	rejected["animation_library_ref"] = "user://motion_retarget_runtime_probe/rejected/retargeted_library.tres"
	rejected["qualification_report_ref"] = "user://motion_retarget_runtime_probe/rejected/qualification-report.json"
	if registry.register_motion_library(StringName(str(manifest.get("motion_library_id", ""))), rejected, library):
		return false
	var digest_tampered := manifest.duplicate(true)
	digest_tampered["source_digest"] = "sha256:%s" % "0".repeat(64)
	if registry.register_motion_library(StringName(str(manifest.get("motion_library_id", ""))), digest_tampered, library):
		return false
	var canonical_missing := manifest.duplicate(true)
	canonical_missing["clips"] = manifest.get("clips", {}).duplicate(true)
	var first_clip := str(canonical_missing["clips"].keys()[0])
	canonical_missing["clips"][first_clip]["canonical_bone_ids"] = []
	return not registry.register_motion_library(StringName(str(manifest.get("motion_library_id", ""))), canonical_missing, library)


func _target_tracks_valid(library: AnimationLibrary, target_profile: Dictionary) -> bool:
	if library == null:
		return false
	var allowed: Dictionary = target_profile.get("canonical_bones", {})
	for clip_name in EXPECTED_CLIPS:
		if not library.has_animation(StringName(clip_name)):
			return false
		var animation := library.get_animation(StringName(clip_name))
		for track_index in animation.get_track_count():
			var path_text := String(animation.track_get_path(track_index))
			var separator := path_text.rfind(":")
			if separator < 0 or not allowed.values().has(path_text.substr(separator + 1)):
				return false
	return true


func _six_states_valid(library: AnimationLibrary) -> bool:
	if library == null:
		return false
	for clip_name in EXPECTED_CLIPS:
		if not library.has_animation(StringName(clip_name)):
			return false
	return true


func _clip_gate_valid(reports: Array, gate_name: String) -> bool:
	if reports.is_empty():
		return false
	for raw_report in reports:
		if not (raw_report is Dictionary):
			return false
		var gate: Variant = (raw_report as Dictionary).get(gate_name, {})
		if not (gate is Dictionary) or not bool((gate as Dictionary).get("accepted", false)):
			return false
	return true


func _all_true(fields: Dictionary) -> bool:
	for value in fields.values():
		if not bool(value):
			return false
	return true


func _read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed if parsed is Dictionary else {}


func _write_json(path: String, value: Dictionary) -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(path.get_base_dir()))
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(value, "\t"))
		file.close()


func _digest(path: String) -> String:
	if not FileAccess.file_exists(path):
		return ""
	return "sha256:%s" % FileAccess.get_sha256(path)
