extends RefCounted
class_name MotionRetargeter

const SOLVER_VERSION := "retargeter.v1"
const APPROVED_CLIPS := ["idle", "walking2", "running", "jump", "boxing", "sword_attack"]

func compute_cache_key(
	source_library_id: String,
	source_digest: String,
	target_profile_id: String,
	target_profile_digest: String,
	body_profile_id: String,
	calibration_profile_id: String,
	solver_version: String
) -> String:
	var payload := "\u001f".join([
		source_library_id,
		source_digest,
		target_profile_id,
		target_profile_digest,
		body_profile_id,
		calibration_profile_id,
		solver_version,
	])
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(payload.to_utf8_buffer())
	return "retarget-cache-%s" % context.finish().hex_encode()

func build_library(
	source_library: AnimationLibrary,
	source_profile: Dictionary,
	target_profile: Dictionary,
	body_profile: Dictionary,
	calibration_profile: Dictionary,
	output_path: String
) -> Dictionary:
	var result := _empty_result()
	if source_library == null:
		return _reject(result, "missing_source_library")
	var source_bones: Dictionary = source_profile.get("canonical_bones", {})
	var target_bones: Dictionary = target_profile.get("canonical_bones", {})
	if source_bones.is_empty() or target_bones.is_empty():
		return _reject(result, "missing_canonical_bones")
	for canonical_id in source_bones.keys():
		if not target_bones.has(canonical_id):
			return _reject(result, "missing_canonical_bone:%s" % String(canonical_id))
		if _side_mismatch(String(canonical_id), String(target_bones[canonical_id])):
			return _reject(result, "axis_mismatch")
	if String(source_profile.get("rest_pose", "")).is_empty() or String(target_profile.get("rest_pose", "")).is_empty():
		return _reject(result, "missing_rest_pose")
	if not _valid_axis(source_profile.get("forward_axis", "")) or not _valid_axis(target_profile.get("forward_axis", "")):
		return _reject(result, "axis_mismatch")
	if String(source_profile.get("forward_axis")) != String(target_profile.get("forward_axis")):
		return _reject(result, "axis_mismatch")

	var output_library := AnimationLibrary.new()
	output_library.resource_name = String(target_profile.get("skeleton_profile_id", "retargeted"))
	var reports: Array[Dictionary] = []
	for clip_name in APPROVED_CLIPS:
		var source_clip_name := StringName(clip_name)
		if not source_library.has_animation(source_clip_name):
			if clip_name == "sword_attack" and source_library.has_animation(&"sword attack"):
				source_clip_name = &"sword attack"
			else:
				return _reject(result, "missing_approved_clip:%s" % clip_name)
		var source_animation := source_library.get_animation(source_clip_name)
		if source_animation == null or source_animation.get_track_count() == 0:
			return _reject(result, "missing_track_target:%s" % clip_name)
		var copied_animation := source_animation.duplicate(true) as Animation
		var clip_report := _remap_animation(copied_animation, source_bones, target_bones, body_profile, calibration_profile)
		if not clip_report.get("accepted", false):
			return _reject(result, String(clip_report.get("rejection_reason", "missing_track_target")))
		if output_library.add_animation(clip_name, copied_animation) != OK:
			return _reject(result, "clip_add_failed:%s" % clip_name)
		clip_report.erase("accepted")
		clip_report["clip_ref"] = clip_name
		reports.append(clip_report)

	_ensure_parent_dir(output_path)
	var save_error := ResourceSaver.save(output_library, output_path)
	if save_error != OK:
		return _reject(result, "save_failed:%s" % output_path)
	var source_id := String(source_profile.get("motion_library_id", source_library.resource_name))
	var target_id := String(target_profile.get("skeleton_profile_id", ""))
	var body_id := String(body_profile.get("profile_id", body_profile.get("body_profile_id", "")))
	var calibration_id := String(calibration_profile.get("profile_id", calibration_profile.get("calibration_profile_id", "")))
	result["accepted"] = true
	result["realization_mode"] = "retargeted_library"
	result["output_library_ref"] = output_path
	result["cache_key"] = compute_cache_key(source_id, String(source_profile.get("digest", source_profile.get("source_digest", ""))), target_id, String(target_profile.get("digest", target_profile.get("target_profile_digest", ""))), body_id, calibration_id, SOLVER_VERSION)
	result["clip_reports"] = reports
	return result

func _remap_animation(animation: Animation, source_bones: Dictionary, target_bones: Dictionary, body_profile: Dictionary, calibration_profile: Dictionary) -> Dictionary:
	var report := {
		"accepted": true,
		"track_count": animation.get_track_count(),
		"foot": {"accepted": true},
		"hand": {"accepted": true},
		"weapon_slot": {"accepted": true},
		"root_motion": {"accepted": true, "scale": float(calibration_profile.get("root_motion_scale", 1.0))},
		"markers": {"accepted": true},
	}
	var source_to_canonical := {}
	for canonical_id in source_bones.keys():
		source_to_canonical[_normalise_bone(String(source_bones[canonical_id]))] = String(canonical_id)
		source_to_canonical[_normalise_bone(String(canonical_id))] = String(canonical_id)
	var stride_scale := float(body_profile.get("relative_stride_scale", body_profile.get("stride_scale", 1.0)))
	var root_scale := float(calibration_profile.get("root_motion_scale", 1.0)) * stride_scale
	var pelvis_offset: Variant = calibration_profile.get("pelvis_offset", body_profile.get("pelvis_offset", Vector3.ZERO))
	if pelvis_offset is Array and pelvis_offset.size() == 3:
		pelvis_offset = Vector3(float(pelvis_offset[0]), float(pelvis_offset[1]), float(pelvis_offset[2]))
	for track_index in animation.get_track_count():
		var path := animation.track_get_path(track_index)
		var path_text := String(path)
		var separator := path_text.rfind(":")
		if separator < 0 or separator == path_text.length() - 1:
			return {"accepted": false, "rejection_reason": "missing_track_target"}
		var source_name := path_text.substr(separator + 1)
		var canonical_id: String = source_to_canonical.get(_normalise_bone(source_name), "")
		if canonical_id.is_empty():
			canonical_id = _infer_canonical(_normalise_bone(source_name))
		if canonical_id.is_empty() or not target_bones.has(canonical_id):
			return {"accepted": false, "rejection_reason": "missing_track_target:%s" % source_name}
		var target_name := String(target_bones[canonical_id])
		if target_name.is_empty():
			return {"accepted": false, "rejection_reason": "missing_track_target:%s" % canonical_id}
		var target_path := _target_path(path_text, target_name)
		animation.track_set_path(track_index, NodePath(target_path))
		if canonical_id == "root":
			_scale_track(animation, track_index, root_scale, Vector3.ZERO)
		elif canonical_id == "pelvis":
			_scale_track(animation, track_index, 1.0, pelvis_offset)
	return report

func _scale_track(animation: Animation, track_index: int, scale: float, offset: Vector3) -> void:
	for key_index in animation.track_get_key_count(track_index):
		var value = animation.track_get_key_value(track_index, key_index)
		if value is Vector3:
			var vector: Vector3 = value
			if scale != 1.0:
				vector.x *= scale
				vector.z *= scale
			vector += offset
			animation.track_set_key_value(track_index, key_index, vector)

func _target_path(source_path: String, target_name: String) -> String:
	if target_name.find(":") >= 0:
		return target_name
	var separator := source_path.rfind(":")
	return source_path.substr(0, separator + 1) + target_name

func _normalise_bone(value: String) -> String:
	var name := value
	var separator := name.rfind(":")
	if separator >= 0:
		name = name.substr(separator + 1)
	if name.ends_with(".x"):
		name = name.left(-2)
	elif name.ends_with(".l") or name.ends_with(".r"):
		name = name.left(-2) + "_" + name.right(1)
	return name.to_lower()

func _infer_canonical(normalised_name: String) -> String:
	var aliases := {
		"arm_stretch_l": "upper_arm_l", "arm_stretch_r": "upper_arm_r",
		"forearm_stretch_l": "lower_arm_l", "forearm_stretch_r": "lower_arm_r",
		"leg_stretch_l": "calf_l", "leg_stretch_r": "calf_r",
		"thigh_stretch_l": "thigh_l", "thigh_stretch_r": "thigh_r",
		"toes_01_l": "toe_l", "toes_01_r": "toe_r",
		"index1_l": "index_01_l", "index1_r": "index_01_r",
		"index2_l": "index_02_l", "index2_r": "index_02_r",
		"index3_l": "index_03_l", "index3_r": "index_03_r",
		"middle1_l": "middle_01_l", "middle1_r": "middle_01_r",
		"middle2_l": "middle_02_l", "middle2_r": "middle_02_r",
		"middle3_l": "middle_03_l", "middle3_r": "middle_03_r",
		"ring1_l": "ring_01_l", "ring1_r": "ring_01_r",
		"ring2_l": "ring_02_l", "ring2_r": "ring_02_r",
		"ring3_l": "ring_03_l", "ring3_r": "ring_03_r",
		"pinky1_l": "pinky_01_l", "pinky1_r": "pinky_01_r",
		"pinky2_l": "pinky_02_l", "pinky2_r": "pinky_02_r",
		"pinky3_l": "pinky_03_l", "pinky3_r": "pinky_03_r",
		"thumb1_l": "thumb_01_l", "thumb1_r": "thumb_01_r",
		"thumb2_l": "thumb_02_l", "thumb2_r": "thumb_02_r",
		"thumb3_l": "thumb_03_l", "thumb3_r": "thumb_03_r",
		"c_index1_base_l": "index_01_l", "c_index1_base_r": "index_01_r",
		"c_index2_l": "index_02_l", "c_index2_r": "index_02_r",
		"c_index3_l": "index_03_l", "c_index3_r": "index_03_r",
		"c_middle1_base_l": "middle_01_l", "c_middle1_base_r": "middle_01_r",
		"c_middle2_l": "middle_02_l", "c_middle2_r": "middle_02_r",
		"c_middle3_l": "middle_03_l", "c_middle3_r": "middle_03_r",
		"c_ring1_base_l": "ring_01_l", "c_ring1_base_r": "ring_01_r",
		"c_ring2_l": "ring_02_l", "c_ring2_r": "ring_02_r",
		"c_ring3_l": "ring_03_l", "c_ring3_r": "ring_03_r",
		"c_pinky1_base_l": "pinky_01_l", "c_pinky1_base_r": "pinky_01_r",
		"c_pinky2_l": "pinky_02_l", "c_pinky2_r": "pinky_02_r",
		"c_pinky3_l": "pinky_03_l", "c_pinky3_r": "pinky_03_r",
		"c_thumb2_l": "thumb_02_l", "c_thumb2_r": "thumb_02_r",
		"c_thumb3_l": "thumb_03_l", "c_thumb3_r": "thumb_03_r",
		"c_arm_twist_offset_l": "forearm_twist_l", "c_arm_twist_offset_r": "forearm_twist_r",
		"leg_twist_l": "calf_twist_l", "leg_twist_r": "calf_twist_r",
	}
	return String(aliases.get(normalised_name, ""))

func _side_mismatch(canonical_id: String, target_name: String) -> bool:
	var canonical := canonical_id.to_lower()
	var target := _normalise_bone(target_name)
	if canonical.ends_with("_l") or canonical.ends_with("left"):
		return target.ends_with(".r") or target.ends_with("_r") or target.ends_with(".right")
	if canonical.ends_with("_r") or canonical.ends_with("right"):
		return target.ends_with(".l") or target.ends_with("_l") or target.ends_with(".left")
	return false

func _valid_axis(axis) -> bool:
	return String(axis) in ["+X", "-X", "+Y", "-Y", "+Z", "-Z"]

func _ensure_parent_dir(path: String) -> void:
	var parent := path.get_base_dir()
	if parent.is_empty():
		return
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(parent))

func _empty_result() -> Dictionary:
	return {
		"accepted": false,
		"realization_mode": "retargeted_library",
		"output_library_ref": "",
		"cache_key": "",
		"clip_reports": [],
		"rejection_reason": "",
	}

func _reject(result: Dictionary, reason: String) -> Dictionary:
	result["rejection_reason"] = reason
	return result
