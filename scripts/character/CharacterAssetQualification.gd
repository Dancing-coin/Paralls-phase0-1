extends RefCounted

class_name CharacterAssetQualification


const CANONICAL_PROFILE := preload("res://scripts/character/CanonicalSkeletonProfile.gd")
const REALIZATION_MODES := [&"native_upper_body", &"derived_upper_body", &"full_body_exclusive", &"drive_locomotion", &"additive"]
const LOCOMOTION_RELATIONS := [&"coexist", &"drive_locomotion", &"replace_locomotion", &"suspend"]
const ROOT_MOTION_POLICIES := [&"hold", &"bounded_continue", &"reversible_continue"]
const CONCURRENT_MODES := [&"native_upper_body", &"derived_upper_body"]
const LOWER_BODY_BONES := [&"left_upper_leg", &"left_lower_leg", &"left_foot", &"right_upper_leg", &"right_lower_leg", &"right_foot"]
const REQUIRED_LOCOMOTION_TAGS := [&"idle", &"walk_forward", &"run_forward", &"jump_start", &"jump_land", &"turn_left", &"turn_right"]
const FORBIDDEN_TRUTH_FIELDS := ["transform", "global_position", "velocity", "damage", "inventory", "status", "hit_outcome", "ownership_transfer"]
const TRACK_TOLERANCE := 0.0001


class StringCollector extends RefCounted:
	var values: Array[String] = []

	func append_once(value: String) -> void:
		if not values.has(value):
			var updated := values.duplicate()
			updated.append(value)
			values = updated


class DictionaryCollector extends RefCounted:
	var values: Array[Dictionary] = []


static func qualify(package_manifest: Dictionary) -> Dictionary:
	var report := {
		"contract": "character_qualification_report.v1",
		"package_id": str(package_manifest.get("package_id", "")),
		"status": "rejected",
		"checks": {},
		"reasons": [],
		"fallbacks": [],
		"optional": [],
		"clip_audits": {},
		"locomotion": {},
		"actions": [],
	}
	var reasons := StringCollector.new()
	var fallbacks := DictionaryCollector.new()
	var optional := StringCollector.new()
	var skeleton := _resolve_skeleton(package_manifest)
	if skeleton == null:
		reasons.values.append("skeleton_missing")
		report["checks"]["skeleton"] = false
	else:
		report["checks"]["skeleton"] = true
		var mapping: Variant = package_manifest.get("canonical_mapping", {})
		var mapping_result := CANONICAL_PROFILE.validate_mapping(mapping if mapping is Dictionary else {}, skeleton)
		report["checks"]["canonical_mapping"] = bool(mapping_result.get("accepted", false))
		for mapping_reason in mapping_result.get("reasons", []):
			if not reasons.values.has(str(mapping_reason)):
				reasons.values.append(str(mapping_reason))
		var profile: Dictionary = mapping_result
		_validate_package_conventions(package_manifest, report, reasons)
		_record_optional_bones(package_manifest, skeleton, optional)
		var clips := _resolve_clips(package_manifest)
		var declared_locomotion: Dictionary = package_manifest.get("locomotion_map", {})
		for required_tag in REQUIRED_LOCOMOTION_TAGS:
			var required_clip_ref := str(declared_locomotion.get(String(required_tag), ""))
			if required_clip_ref.is_empty():
				reasons.values.append("locomotion_tag_unmapped:%s" % required_tag)
			elif not (clips.get(required_clip_ref) is Animation):
				reasons.values.append("required_clip_missing:%s" % required_tag)
		if not declared_locomotion.has("jump_loop") and not declared_locomotion.has("fall"):
			reasons.values.append("locomotion_tag_unmapped:jump_loop_or_fall")
		_validate_locomotion(package_manifest, clips, profile, report, reasons)
		_validate_actions(package_manifest, clips, profile, report, reasons, fallbacks)
	if not reasons.values.is_empty():
		report["status"] = "rejected"
	elif not fallbacks.values.is_empty():
		report["status"] = "qualified_with_fallback"
	else:
		report["status"] = "qualified"
	report["reasons"] = reasons.values
	report["fallbacks"] = fallbacks.values
	report["optional"] = optional.values
	return report


static func inspect_clip(clip: Animation, profile: Dictionary) -> Dictionary:
	var impact: Array[String] = []
	var lower_body_impact: Array[String] = []
	var root_translation := false
	var root_rotation := false
	var pelvis_translation := false
	var pelvis_rotation := false
	var external_to_canonical: Dictionary = profile.get("external_to_canonical", {})
	if clip == null:
		return {"valid": false, "reason": "clip_missing", "bone_impact": impact}
	for track_index in clip.get_track_count():
		var path := str(clip.track_get_path(track_index))
		var segments := path.split(":")
		var external_bone := segments[segments.size() - 1] if not segments.is_empty() else ""
		var canonical_bone := str(external_to_canonical.get(external_bone, ""))
		if canonical_bone.is_empty() or not _track_has_non_rest_value(clip, track_index):
			continue
		if not impact.has(canonical_bone):
			impact.append(canonical_bone)
		if LOWER_BODY_BONES.has(StringName(canonical_bone)):
			lower_body_impact.append(canonical_bone)
		var track_type := clip.track_get_type(track_index)
		if canonical_bone == "root":
			root_translation = root_translation or track_type == Animation.TYPE_POSITION_3D
			root_rotation = root_rotation or track_type == Animation.TYPE_ROTATION_3D
		if canonical_bone == "pelvis":
			pelvis_translation = pelvis_translation or track_type == Animation.TYPE_POSITION_3D
			pelvis_rotation = pelvis_rotation or track_type == Animation.TYPE_ROTATION_3D
	return {
		"valid": true,
		"duration_seconds": clip.length,
		"source_step_seconds": clip.step,
		"bone_impact": impact,
		"lower_body_impact": lower_body_impact,
		"root_motion": {"translation": root_translation, "rotation": root_rotation},
		"pelvis_motion": {"translation": pelvis_translation, "rotation": pelvis_rotation},
	}


static func _validate_package_conventions(manifest: Dictionary, report: Dictionary, reasons: StringCollector) -> void:
	var rate := float(manifest.get("source_frame_rate", 0.0))
	report["checks"]["source_frame_rate"] = rate > 0.0
	if rate <= 0.0:
		reasons.values.append("source_frame_rate_missing")
	var scale := float(manifest.get("unit_scale", 0.0))
	report["checks"]["unit_scale"] = is_equal_approx(scale, 1.0)
	if not is_equal_approx(scale, 1.0):
		reasons.values.append("unit_scale_invalid")
	var axes_valid := str(manifest.get("forward_axis", "")) == "-z" and str(manifest.get("up_axis", "")) == "+y"
	report["checks"]["axis_convention"] = axes_valid
	if not axes_valid:
		reasons.values.append("axis_convention_invalid")
	_validate_slots(manifest, report, reasons)


static func _validate_slots(manifest: Dictionary, report: Dictionary, reasons: StringCollector) -> void:
	var required_slots: Variant = manifest.get("required_slots", [])
	var slots: Variant = manifest.get("slots", {})
	if not (required_slots is Array) or not (slots is Dictionary):
		reasons.values.append("required_slots_invalid")
		return
	for slot_variant in required_slots:
		var slot_id := str(slot_variant)
		var slot: Variant = slots.get(slot_id, {})
		if not (slot is Dictionary):
			reasons.values.append("slot_missing:%s" % slot_id)
			continue
		var canonical_bone := str(slot.get("canonical_bone", ""))
		var expected_bone := "right_hand" if slot_id.contains("right") or slot_id.contains("weapon") else "left_hand"
		if canonical_bone != expected_bone or str(slot.get("anchor_ref", "")).is_empty():
			reasons.values.append("slot_incompatible:%s" % slot_id)
	var slot_failure := false
	for reason in reasons.values:
		if reason.begins_with("slot_"):
			slot_failure = true
			break
	report["checks"]["required_slots"] = not slot_failure


static func _record_optional_bones(manifest: Dictionary, skeleton: Skeleton3D, missing: StringCollector) -> void:
	var optional: Variant = manifest.get("optional_bones", {})
	if not (optional is Dictionary):
		return
	for canonical_bone in optional:
		if skeleton.find_bone(str(optional[canonical_bone])) < 0:
			missing.values.append("optional:%s" % canonical_bone)


static func _validate_locomotion(manifest: Dictionary, clips: Dictionary, profile: Dictionary, report: Dictionary, reasons: StringCollector) -> void:
	var raw_map: Variant = manifest.get("locomotion_map", {})
	var locomotion_map: Dictionary = raw_map if raw_map is Dictionary else {}
	for tag in REQUIRED_LOCOMOTION_TAGS:
		_validate_locomotion_tag(String(tag), locomotion_map, clips, profile, report, reasons)
	_validate_locomotion_tag("turn_right", locomotion_map, clips, profile, report, reasons)
	if not locomotion_map.has("jump_loop") and not locomotion_map.has("fall"):
		reasons.values.append("locomotion_tag_unmapped:jump_loop_or_fall")
	else:
		_validate_locomotion_tag("jump_loop" if locomotion_map.has("jump_loop") else "fall", locomotion_map, clips, profile, report, reasons)


static func _validate_locomotion_tag(tag: String, locomotion_map: Dictionary, clips: Dictionary, profile: Dictionary, report: Dictionary, reasons: StringCollector) -> void:
	if not locomotion_map.has(tag):
		reasons.values.append("locomotion_tag_unmapped:%s" % tag)
		return
	var clip_ref := str(locomotion_map.get(tag, ""))
	var clip: Animation = clips.get(clip_ref) as Animation
	if clip == null:
		reasons.values.append("required_clip_missing:%s" % tag)
		return
	var audit := inspect_clip(clip, profile)
	report["clip_audits"][clip_ref] = audit
	report["locomotion"][tag] = {"clip_ref": clip_ref, "classification": "root_motion" if bool(audit.get("root_motion", {}).get("translation", false)) else "in_place"}


static func _validate_actions(manifest: Dictionary, clips: Dictionary, profile: Dictionary, report: Dictionary, reasons: StringCollector, fallbacks: DictionaryCollector) -> void:
	var raw_actions: Variant = manifest.get("actions", [])
	if not (raw_actions is Array) or raw_actions.is_empty():
		reasons.values.append("action_required_missing")
		return
	for raw_action in raw_actions:
		if not (raw_action is Dictionary):
			reasons.values.append("action_invalid")
			continue
		var action: Dictionary = raw_action
		var action_id := str(action.get("semantic_action_id", ""))
		if action_id.is_empty():
			reasons.values.append("semantic_action_id_missing")
			continue
		var clip_ref := str(action.get("clip_ref", ""))
		var clip: Animation = clips.get(clip_ref) as Animation
		if clip == null:
			reasons.values.append("required_clip_missing:action:%s" % action_id)
			continue
		var audit := inspect_clip(clip, profile)
		report["clip_audits"][clip_ref] = audit
		var action_report := {"semantic_action_id": action_id, "clip_ref": clip_ref, "audit": audit, "mode": str(action.get("mode", ""))}
		report["actions"].append(action_report)
		_validate_action_metadata(action, action_id, reasons)
		var action_slots: Variant = action.get("required_slots", [])
		var declared_slots: Dictionary = manifest.get("slots", {})
		if action_slots is Array:
			for slot_id in action_slots:
				if not declared_slots.has(str(slot_id)):
					reasons.values.append("slot_missing:%s" % str(slot_id))
		var mode := StringName(str(action.get("mode", "")))
		var relation := StringName(str(action.get("locomotion_compatibility", "")))
		if mode in CONCURRENT_MODES and relation == &"coexist" and _has_concurrent_violation(audit):
			var fallback: Variant = action.get("fallback", null)
			if _is_explicit_fallback(fallback):
				fallbacks.values.append({"semantic_action_id": action_id, "reason": "upper_body_lower_body_motion", "fallback": fallback.duplicate(true)})
			else:
				reasons.values.append("upper_body_lower_body_motion")
		var root_motion: Dictionary = audit.get("root_motion", {})
		if bool(action.get("root_motion_required", false)) and not bool(root_motion.get("translation", false)):
			reasons.values.append("root_motion_required_unavailable:%s" % action_id)


static func _validate_action_metadata(action: Dictionary, action_id: String, reasons: StringCollector) -> void:
	if StringName(str(action.get("mode", ""))) not in REALIZATION_MODES:
		reasons.values.append("realization_mode_invalid:%s" % action_id)
	if StringName(str(action.get("locomotion_compatibility", ""))) not in LOCOMOTION_RELATIONS:
		reasons.values.append("locomotion_compatibility_invalid:%s" % action_id)
	var policy := StringName(str(action.get("root_motion_policy", "")))
	if policy not in ROOT_MOTION_POLICIES:
		reasons.values.append("root_motion_policy_invalid:%s" % action_id)
	elif policy != &"hold":
		var envelope: Variant = action.get("root_motion_envelope", {})
		if not (envelope is Dictionary) or float(envelope.get("max_distance", 0.0)) <= 0.0 or int(envelope.get("max_duration_ticks", 0)) <= 0:
			reasons.values.append("root_motion_envelope_required:%s" % action_id)
	var markers: Variant = action.get("markers", [])
	if not (markers is Array) or markers.is_empty():
		reasons.values.append("markers_missing:%s" % action_id)
	else:
		for marker in markers:
			if not (marker is Dictionary) or str(marker.get("marker_id", "")).is_empty() or float(marker.get("time_seconds", -1.0)) < 0.0 or str(marker.get("marker_kind", "")).is_empty() or not marker.has("emits_attempt") or str(marker.get("evidence_requirement", "")).is_empty():
				reasons.values.append("marker_invalid:%s" % action_id)
	var windows: Variant = action.get("cancel_windows", [])
	if not (windows is Array) or windows.is_empty():
		reasons.values.append("cancel_windows_missing:%s" % action_id)
	else:
		for window in windows:
			if not (window is Dictionary) or float(window.get("start_seconds", -1.0)) < 0.0 or float(window.get("end_seconds", -1.0)) < float(window.get("start_seconds", 0.0)):
				reasons.values.append("cancel_window_invalid:%s" % action_id)
	if not (action.get("resource_claims", []) is Array) or not (action.get("physics_claims", []) is Array):
		reasons.values.append("claims_invalid:%s" % action_id)
	if str(action.get("authority_route_ref", "")) not in ["esm", "gameplay", "composite"]:
		reasons.values.append("authority_route_invalid:%s" % action_id)
	for field in FORBIDDEN_TRUTH_FIELDS:
		if action.has(field):
			reasons.values.append("world_truth_field_forbidden:%s" % field)


static func _has_concurrent_violation(audit: Dictionary) -> bool:
	if not (audit.get("lower_body_impact", []) as Array).is_empty():
		return true
	var root_motion: Dictionary = audit.get("root_motion", {})
	var pelvis_motion: Dictionary = audit.get("pelvis_motion", {})
	return bool(root_motion.get("translation", false)) or bool(root_motion.get("rotation", false)) or bool(pelvis_motion.get("translation", false)) or bool(pelvis_motion.get("rotation", false))


static func _is_explicit_fallback(fallback: Variant) -> bool:
	if not (fallback is Dictionary):
		return false
	return StringName(str(fallback.get("mode", ""))) in [&"full_body_exclusive", &"drive_locomotion"] and StringName(str(fallback.get("locomotion_compatibility", ""))) in [&"replace_locomotion", &"suspend", &"drive_locomotion"]


static func _resolve_skeleton(manifest: Dictionary) -> Skeleton3D:
	var direct: Variant = manifest.get("_skeleton", null)
	if direct is Skeleton3D:
		return direct
	var root := _instantiate_role_scene(manifest)
	return _find_skeleton(root)


static func _resolve_clips(manifest: Dictionary) -> Dictionary:
	var direct: Variant = manifest.get("clips", {})
	if direct is Dictionary:
		return direct
	return {}


static func _instantiate_role_scene(manifest: Dictionary) -> Node:
	var ref := str(manifest.get("role_scene_ref", ""))
	if ref.is_empty():
		return null
	var scene := load(ref)
	return scene.instantiate() if scene is PackedScene else null


static func _find_skeleton(root: Node) -> Skeleton3D:
	if root == null:
		return null
	if root is Skeleton3D:
		return root
	for child in root.get_children():
		var found := _find_skeleton(child)
		if found != null:
			return found
	return null


static func _track_has_non_rest_value(clip: Animation, track_index: int) -> bool:
	for key_index in clip.track_get_key_count(track_index):
		var value: Variant = clip.track_get_key_value(track_index, key_index)
		if value is Vector3 and (value as Vector3).length() > TRACK_TOLERANCE:
			return true
		if value is Quaternion and not (value as Quaternion).is_equal_approx(Quaternion.IDENTITY):
			return true
	return false


static func _append_once(values: StringCollector, value: String) -> void:
	if not values.values.has(value):
		values.values.append(value)


static func _append_all(values: StringCollector, additions: Variant) -> void:
	if additions is Array:
		for addition in additions:
			if not values.values.has(str(addition)):
				values.values.append(str(addition))
