extends RefCounted

class_name CanonicalSkeletonProfile


const PROFILE_ID := "humanoid.v1"
const REQUIRED_BONES := [
	&"root", &"pelvis", &"spine", &"chest", &"head",
	&"left_upper_arm", &"left_lower_arm", &"left_hand",
	&"right_upper_arm", &"right_lower_arm", &"right_hand",
	&"left_upper_leg", &"left_lower_leg", &"left_foot",
	&"right_upper_leg", &"right_lower_leg", &"right_foot",
]
const OPTIONAL_BONES := [&"left_finger_1", &"right_finger_1", &"facial_jaw"]
const REQUIRED_LOCOMOTION_TAGS := [
	&"idle", &"walk_forward", &"run_forward", &"jump_start", &"jump_land", &"turn_left", &"turn_right",
]
const REST_SCALE_TOLERANCE := 0.01


static func validate_mapping(mapping: Dictionary, skeleton: Skeleton3D) -> Dictionary:
	var reasons: Array[String] = []
	var external_to_canonical: Dictionary = {}
	if skeleton == null:
		reasons.append("skeleton_missing")
		return {"accepted": false, "reasons": reasons, "external_to_canonical": external_to_canonical}
	if str(mapping.get("profile_id", "")) != PROFILE_ID:
		reasons.append("canonical_profile_invalid")
	var raw_bones: Variant = mapping.get("bones", null)
	if not (raw_bones is Dictionary):
		reasons.append("mapping_not_explicit")
		return {"accepted": false, "reasons": reasons, "external_to_canonical": external_to_canonical}
	var bones: Dictionary = raw_bones
	for canonical_bone in REQUIRED_BONES:
		var external_name := str(bones.get(String(canonical_bone), ""))
		if external_name.is_empty():
			_append_once(reasons, "root_bone_missing" if canonical_bone == &"root" else "mapping_missing:%s" % canonical_bone)
			continue
		if external_to_canonical.has(external_name):
			_append_once(reasons, "mapping_duplicate:%s" % external_name)
			continue
		var bone_index := skeleton.find_bone(external_name)
		if bone_index < 0:
			_append_once(reasons, "root_bone_missing" if canonical_bone == &"root" else "mapped_bone_missing:%s" % canonical_bone)
			continue
		external_to_canonical[external_name] = String(canonical_bone)
		if not _rest_transform_is_valid(skeleton.get_bone_rest(bone_index)):
			_append_once(reasons, "rest_pose_invalid:%s" % canonical_bone)
	if not reasons.has("root_bone_missing"):
		var root_name := str(bones.get("root", ""))
		var root_index := skeleton.find_bone(root_name)
		if root_index < 0 or skeleton.get_bone_parent(root_index) >= 0:
			_append_once(reasons, "root_bone_missing")
	return {
		"accepted": reasons.is_empty(),
		"reasons": reasons,
		"external_to_canonical": external_to_canonical,
		"canonical_to_external": bones.duplicate(true),
	}


static func _rest_transform_is_valid(rest: Transform3D) -> bool:
	var scale := rest.basis.get_scale()
	if absf(rest.basis.determinant()) <= REST_SCALE_TOLERANCE:
		return false
	if absf(scale.x - 1.0) > REST_SCALE_TOLERANCE or absf(scale.y - 1.0) > REST_SCALE_TOLERANCE or absf(scale.z - 1.0) > REST_SCALE_TOLERANCE:
		return false
	return is_finite(rest.origin.x) and is_finite(rest.origin.y) and is_finite(rest.origin.z)


static func _append_once(values: Array[String], value: String) -> void:
	if not values.has(value):
		values.append(value)
