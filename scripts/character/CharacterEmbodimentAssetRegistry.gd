extends RefCounted

class_name CharacterEmbodimentAssetRegistry

const STATUS_REJECTED := "rejected"
const PRIMARY_PACKAGE_IDS := [&"female_jk_external", &"female_t_external", &"female_bandage_external"]
const PRIMARY_PACKAGE_MANIFEST_PATHS := {
	&"female_jk_external": "res://assets/active/female_jk_external/manifest.json",
	&"female_t_external": "res://assets/active/female_t_external/manifest.json",
	&"female_bandage_external": "res://assets/active/female_bandage_external/manifest.json",
}
const PRIMARY_QUALIFICATION_REPORT_PATHS := {
	&"female_jk_external": "res://assets/characters/qualification_reports/female_jk_external.json",
	&"female_t_external": "res://assets/characters/qualification_reports/female_t_external.json",
	&"female_bandage_external": "res://assets/characters/qualification_reports/female_bandage_external.json",
}

var _motion_assets: Dictionary = {}
var _reviewed_action_catalog: Dictionary = {}
var _qualified_packages: Dictionary = {}
var _admission_log: Array[Dictionary] = []


func _init() -> void:
	register_primary_packages()


func register_primary_packages() -> Dictionary:
	var registered_package_ids: Array[StringName] = []
	var rejected_package_ids: Array[StringName] = []
	for package_id in PRIMARY_PACKAGE_IDS:
		var manifest := _read_json(str(PRIMARY_PACKAGE_MANIFEST_PATHS.get(package_id, "")))
		var report_path := str(PRIMARY_QUALIFICATION_REPORT_PATHS.get(package_id, ""))
		var report := _read_json(report_path)
		if register_qualified_package(package_id, manifest, report, report_path):
			registered_package_ids.append(package_id)
		else:
			rejected_package_ids.append(package_id)
	return {"registered_package_ids": registered_package_ids, "rejected_package_ids": rejected_package_ids}


func register_qualified_package(package_id: StringName, manifest: Dictionary, report: Dictionary, qualification_report_ref: String) -> bool:
	if String(package_id).is_empty() or not PRIMARY_PACKAGE_IDS.has(package_id):
		return false
	var status := str(report.get("status", STATUS_REJECTED))
	if status == STATUS_REJECTED or status not in ["qualified", "qualified_with_fallback"]:
		return false
	if str(manifest.get("package_id", "")) != String(package_id):
		return false
	if str(report.get("package_id", "")) != String(package_id):
		return false
	var manifest_status := str(manifest.get("actions_qualification_status", ""))
	if manifest_status != status:
		return false
	var runtime_admission := str(manifest.get("runtime_admission", ""))
	if not runtime_admission.is_empty() and runtime_admission != "qualified":
		return false
	if not _has_empty_atomic_sequence(manifest):
		return false
	if not _has_canonical_mapping(manifest, report):
		return false
	var declared_report_ref := str(manifest.get("provenance", {}).get("qualification_report_ref", ""))
	if declared_report_ref.is_empty() or not qualification_report_ref.ends_with(declared_report_ref.get_file()):
		return false
	var provenance: Variant = report.get("provenance", {})
	if not (provenance is Dictionary):
		return false
	var package_digest := str((provenance as Dictionary).get("package_digest", ""))
	if package_digest.is_empty() or package_digest != str(manifest.get("source", {}).get("digest_sha256", "")):
		return false
	if str(report.get("source", {}).get("digest_sha256", package_digest)) != package_digest:
		return false
	var equipment := CharacterEquipmentBindingProfile.new({"slots": manifest.get("slots", {})})
	var slots := _required_slots(equipment)
	if not _has_required_weapon_slots(slots):
		return false
	var profiles: Dictionary = {}
	var actions: Variant = manifest.get("actions", [])
	if not (actions is Array):
		return false
	for raw_action in actions:
		if not (raw_action is Dictionary):
			continue
		if not _has_empty_atomic_sequence(raw_action):
			return false
		var profile := _profile_from_action(package_id, raw_action, report, qualification_report_ref)
		if profile.is_empty():
			continue
		profiles[StringName(str(profile.get("semantic_action_id", "")))] = [profile]
	var hitscan_profile := _semantic_hitscan_fixture(package_id, report, qualification_report_ref)
	profiles[StringName(str(hitscan_profile.get("semantic_action_id", "")))] = [hitscan_profile]
	if profiles.is_empty():
		return false
	_qualified_packages[package_id] = {
		"package_id": package_id,
		"package_digest": package_digest,
		"qualification_report_ref": qualification_report_ref,
		"qualification_status": status,
		"canonical_skeleton_mapping_ref": _canonical_mapping_ref(package_id),
		"equipment": equipment,
		"profiles": profiles,
	}
	return true


func resolve(package_id: StringName, action_id: StringName, claims: Array[StringName]) -> Dictionary:
	var package: Variant = _qualified_packages.get(package_id, {})
	if not (package is Dictionary) or (package as Dictionary).is_empty():
		return {"accepted": false, "reason": &"package_not_qualified"}
	var profiles: Variant = (package as Dictionary).get("profiles", {}).get(action_id, [])
	if not (profiles is Array) or profiles.is_empty():
		return {"accepted": false, "reason": &"semantic_action_unavailable"}
	for raw_profile in profiles:
		if not (raw_profile is Dictionary):
			continue
		var profile: Dictionary = raw_profile
		if str(profile.get("qualification_status", STATUS_REJECTED)) == STATUS_REJECTED:
			continue
		if _is_compatible_with_locomotion(profile, claims):
			return {"accepted": true, "status": "available", "profile": profile.duplicate(true)}
		var fallback: Variant = profile.get("fallback", {})
		if fallback is Dictionary and not (fallback as Dictionary).is_empty():
			return {"accepted": true, "status": "queued_until_compatible", "profile": (fallback as Dictionary).duplicate(true), "fallback_applied": true}
	return {"accepted": false, "reason": &"declared_fallback_unavailable"}

func admit_action_package(package_id: StringName, action_id: StringName, manifest_digest: String, skeleton_mapping: String, marker_id: String, raw_clip_lookup: String = "", claims: Array[StringName] = []) -> Dictionary:
	var result := {"accepted": false, "package_id": String(package_id), "manifest_digest": manifest_digest, "action_id": String(action_id), "root_policy": "hold", "fallback_mode": "", "rejection_reason": ""}
	var package: Variant = _qualified_packages.get(package_id, {})
	if not (package is Dictionary) or (package as Dictionary).is_empty():
		result["rejection_reason"] = "unknown_package"
		_admission_log.append(result.duplicate(true))
		return result
	if manifest_digest.is_empty() or manifest_digest != str((package as Dictionary).get("package_digest", "")):
		result["rejection_reason"] = "digest_mismatch"
		_admission_log.append(result.duplicate(true))
		return result
	if skeleton_mapping.is_empty() or skeleton_mapping != str((package as Dictionary).get("canonical_skeleton_mapping_ref", "")):
		result["rejection_reason"] = "missing_skeleton_mapping"
		_admission_log.append(result.duplicate(true))
		return result
	if not raw_clip_lookup.is_empty():
		result["rejection_reason"] = "raw_clip_lookup_forbidden"
		_admission_log.append(result.duplicate(true))
		return result
	var resolved := resolve(package_id, action_id, claims)
	if not bool(resolved.get("accepted", false)):
		result["rejection_reason"] = str(resolved.get("reason", "semantic_action_unavailable"))
		_admission_log.append(result.duplicate(true))
		return result
	var profile: Dictionary = resolved.get("profile", {})
	var markers: Array = profile.get("timing_markers", []) if profile.get("timing_markers", []) is Array else []
	if marker_id.is_empty() or not markers.any(func(marker): return marker is Dictionary and str(marker.get("marker_id", "")) == marker_id):
		result["rejection_reason"] = "marker_missing"
		_admission_log.append(result.duplicate(true))
		return result
	result["accepted"] = true
	result["root_policy"] = str(profile.get("root_motion_policy", "hold"))
	result["fallback_mode"] = str(profile.get("mode", ""))
	result["profile"] = profile.duplicate(true)
	_admission_log.append(result.duplicate(true))
	return result

func inventory_admission_log() -> Array[Dictionary]:
	return _admission_log.duplicate(true)


func resolve_equipment_slot(package_id: StringName, slot_id: StringName) -> Dictionary:
	var package: Variant = _qualified_packages.get(package_id, {})
	if not (package is Dictionary):
		return {}
	var equipment: Variant = (package as Dictionary).get("equipment", null)
	return equipment.resolve_slot(slot_id) if equipment is CharacterEquipmentBindingProfile else {}


func _profile_from_action(package_id: StringName, raw_action: Dictionary, report: Dictionary, qualification_report_ref: String) -> Dictionary:
	var semantic_action_id := StringName(str(raw_action.get("semantic_action_id", "")))
	if String(semantic_action_id).is_empty():
		return {}
	var clip_ref := str(raw_action.get("clip_ref", ""))
	if clip_ref.is_empty():
		return {}
	var mode := StringName(str(raw_action.get("mode", "")))
	var fallback: Dictionary = raw_action.get("fallback", {}).duplicate(true) if raw_action.get("fallback", {}) is Dictionary else {}
	if mode == &"full_body_exclusive" and fallback.is_empty():
		fallback = {
			"profile_id": "%s:declared_full_body_fallback" % semantic_action_id,
			"semantic_action_id": semantic_action_id,
			"mode": &"full_body_exclusive",
			"locomotion_compatibility": "replace_locomotion",
			"clip_ref": clip_ref,
			"fallback_policy": str(raw_action.get("fallback_policy", "queue_until_compatible")),
		}
	var profile := CharacterActionAssetDescriptor.normalize({
		"semantic_action_id": semantic_action_id,
		"action_tag": semantic_action_id,
		"required_clips": [clip_ref],
		"realization_profile": {"profile_id": "%s:primary" % semantic_action_id, "mode": mode, "clip_ref": clip_ref, "fallback_rank": 0},
		"canonical_skeleton_mapping_ref": _canonical_mapping_ref(package_id),
		"canonical_bone_mask_ref": "canonical:upper_body" if mode == &"derived_upper_body" else "",
		"resource_claims": raw_action.get("resource_claims", []),
		"physics_claims": raw_action.get("physics_claims", []),
		"physics_profile_ref": "%s#%s:physics_claims" % [qualification_report_ref, semantic_action_id],
		"authority_route_ref": raw_action.get("authority_route_ref", ""),
		"animation_clip_ref": clip_ref,
		"source_clip_ref": raw_action.get("source_clip_ref", clip_ref),
		"derived_clip_ref": raw_action.get("derived_clip_ref", ""),
		"derived_from_clip_ref": raw_action.get("derived_from_clip_ref", ""),
		"locomotion_compatibility": raw_action.get("locomotion_compatibility", ""),
		"root_motion_policy": raw_action.get("root_motion_policy", "hold"),
		"root_motion_envelope": raw_action.get("root_motion_envelope", {}),
		"timing_markers": raw_action.get("markers", []),
		"cancel_windows": raw_action.get("cancel_windows", []),
		"required_slots": raw_action.get("required_slots", []),
		"fallback": fallback,
		"fallback_policy": raw_action.get("fallback_policy", ""),
		"qualification_report_ref": qualification_report_ref,
		"package_digest": report.get("provenance", {}).get("package_digest", ""),
	})
	var validation := CharacterActionAssetDescriptor.validate_phase1(profile)
	if not bool(validation.get("accepted", false)):
		return {}
	profile["profile_id"] = "%s:primary" % semantic_action_id
	profile["mode"] = mode
	profile["clip_ref"] = clip_ref
	profile["qualification_status"] = str(report.get("status", STATUS_REJECTED))
	profile["fallback_rank"] = 0
	profile["timing_markers"] = raw_action.get("markers", []).duplicate(true)
	profile["fallback"] = _complete_fallback(profile, fallback)
	return profile


func _semantic_hitscan_fixture(package_id: StringName, report: Dictionary, qualification_report_ref: String) -> Dictionary:
	var weapon_profile := CharacterWeaponActionProfile.normalize({
		"semantic_kind": "hitscan",
		"semantic_action_id": "action:hitscan.semantic_request",
		"required_slots": ["weapon_hand", "weapon_slot:sword"],
		"resource_claims": ["right_arm", "weapon_slot:sword"],
		"physics_claims": [],
		"authority_route_ref": "esm",
		"presentation_only": true,
	})
	return {
		"profile_id": "action:hitscan.semantic_request:fixture",
		"semantic_action_id": weapon_profile.get("semantic_action_id", &""),
		"semantic_kind": weapon_profile.get("semantic_kind", &"hitscan"),
		"mode": &"additive",
		"locomotion_compatibility": "coexist",
		"presentation_only": true,
		"qualification_status": str(report.get("status", STATUS_REJECTED)),
		"qualification_report_ref": qualification_report_ref,
		"package_digest": str(report.get("provenance", {}).get("package_digest", "")),
		"canonical_skeleton_mapping_ref": _canonical_mapping_ref(package_id),
		"required_slots": weapon_profile.get("required_slots", []),
		"resource_claims": weapon_profile.get("resource_claims", []),
		"physics_claims": weapon_profile.get("physics_claims", []),
		"timing_markers": [],
	}


func _complete_fallback(profile: Dictionary, raw_fallback: Dictionary) -> Dictionary:
	if raw_fallback.is_empty():
		return {}
	var fallback := profile.duplicate(true)
	fallback["profile_id"] = "%s:declared_fallback" % profile.get("semantic_action_id", "")
	fallback["mode"] = StringName(str(raw_fallback.get("mode", "full_body_exclusive")))
	fallback["locomotion_compatibility"] = str(raw_fallback.get("locomotion_compatibility", "replace_locomotion"))
	fallback["clip_ref"] = str(raw_fallback.get("clip_ref", profile.get("clip_ref", "")))
	fallback["fallback_policy"] = str(profile.get("fallback_policy", "queue_until_compatible"))
	return fallback


func _is_compatible_with_locomotion(profile: Dictionary, claims: Array[StringName]) -> bool:
	if not claims.has(&"locomotion"):
		return true
	return StringName(str(profile.get("locomotion_compatibility", ""))) == &"coexist"


func _required_slots(equipment: CharacterEquipmentBindingProfile) -> Array[StringName]:
	var result: Array[StringName] = []
	for slot_id in [&"weapon_hand", &"weapon_slot:sword", &"weapon_hit_volume:sword"]:
		if not equipment.resolve_slot(slot_id).is_empty():
			result.append(slot_id)
	return result


func _has_required_weapon_slots(slots: Array[StringName]) -> bool:
	return slots.has(&"weapon_hand") and slots.has(&"weapon_slot:sword") and slots.has(&"weapon_hit_volume:sword")


func _has_empty_atomic_sequence(candidate: Dictionary) -> bool:
	var atomic_sequence: Variant = candidate.get("atomic_sequence", [])
	return atomic_sequence is Array and (atomic_sequence as Array).is_empty()


func _has_canonical_mapping(manifest: Dictionary, report: Dictionary) -> bool:
	var checks: Variant = report.get("checks", {})
	if not (checks is Dictionary) or not bool((checks as Dictionary).get("canonical_mapping", false)):
		return false
	var mapping: Variant = manifest.get("canonical_mapping", {})
	if not (mapping is Dictionary):
		return false
	var mapping_dict: Dictionary = mapping
	if str(mapping_dict.get("profile_id", "")).is_empty() or str(mapping_dict.get("deform_skeleton_ref", "")).is_empty():
		return false
	var bones: Variant = mapping_dict.get("bones", {})
	if not (bones is Dictionary):
		return false
	for canonical_bone in ["root", "pelvis", "spine", "chest", "head", "left_upper_arm", "left_lower_arm", "left_hand", "right_upper_arm", "right_lower_arm", "right_hand", "left_upper_leg", "left_lower_leg", "left_foot", "right_upper_leg", "right_lower_leg", "right_foot"]:
		if str((bones as Dictionary).get(canonical_bone, "")).is_empty():
			return false
	return true


func _read_json(path: String) -> Dictionary:
	if path.is_empty() or not FileAccess.file_exists(path):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed if parsed is Dictionary else {}


func _canonical_mapping_ref(package_id: StringName) -> String:
	return "%s#canonical_mapping" % str(PRIMARY_PACKAGE_MANIFEST_PATHS.get(package_id, ""))


func register_motion_asset(semantic_key: String, asset_ref: String) -> void:
	if semantic_key.is_empty() or asset_ref.is_empty():
		return
	_motion_assets[semantic_key] = {
		"asset_ref": asset_ref,
		"descriptor": CharacterActionAssetDescriptor.normalize({
			"action_tag": semantic_key,
			"animation_clip_ref": asset_ref,
		}),
	}


func register_action_asset(action_tag: String, candidate: Dictionary) -> bool:
	if action_tag.is_empty():
		return false
	var descriptor := CharacterActionAssetDescriptor.normalize(candidate)
	var validation := CharacterActionAssetDescriptor.validate_root_motion_descriptor(descriptor)
	if not bool(validation.get("accepted", false)):
		return false
	if str(descriptor.get("action_tag", "")).is_empty():
		descriptor["action_tag"] = action_tag
	var asset_ref := str(descriptor.get("animation_clip_ref", ""))
	if asset_ref.is_empty():
		return false
	_motion_assets[action_tag] = {
		"asset_ref": asset_ref,
		"descriptor": descriptor,
	}
	return true


func register_reviewed_action_catalog(entries: Array[Dictionary]) -> Dictionary:
	var registered_action_tags: Array[String] = []
	var rejected_action_tags: Array[String] = []
	for entry: Dictionary in entries:
		if not bool(entry.get("reviewed", false)):
			rejected_action_tags.append(str(entry.get("descriptor", {}).get("action_tag", "")))
			continue
		var descriptor_candidate: Variant = entry.get("descriptor", {})
		if not (descriptor_candidate is Dictionary):
			rejected_action_tags.append("")
			continue
		var descriptor := CharacterActionAssetDescriptor.normalize(descriptor_candidate)
		var action_tag := str(descriptor.get("action_tag", ""))
		var descriptor_validation := CharacterActionAssetDescriptor.validate_root_motion_descriptor(descriptor)
		if not bool(descriptor_validation.get("accepted", false)):
			rejected_action_tags.append(action_tag)
			continue
		var clip_ref := str(descriptor.get("animation_clip_ref", ""))
		var controller_phase := str(entry.get("controller_phase", ""))
		var registration_keys: Variant = entry.get("registration_keys", [])
		if action_tag.is_empty() or clip_ref.is_empty() or controller_phase.is_empty() or not (registration_keys is Array):
			rejected_action_tags.append(action_tag)
			continue
		var normalized_keys: Array[String] = []
		for value: Variant in registration_keys:
			var key := str(value)
			if not key.is_empty() and not normalized_keys.has(key):
				normalized_keys.append(key)
		if normalized_keys.is_empty() or not normalized_keys.has(action_tag):
			rejected_action_tags.append(action_tag)
			continue
		for key: String in normalized_keys:
			register_action_asset(key, descriptor)
		_reviewed_action_catalog[action_tag] = {
			"action_tag": action_tag,
			"controller_phase": controller_phase,
			"registration_keys": normalized_keys,
			"descriptor": descriptor.duplicate(true),
		}
		registered_action_tags.append(action_tag)
	return {
		"status": "available" if rejected_action_tags.is_empty() else "action_assets_unavailable",
		"registered_action_tags": registered_action_tags,
		"rejected_action_tags": rejected_action_tags,
	}


func inventory_reviewed_action_assets() -> Array[Dictionary]:
	var inventory: Array[Dictionary] = []
	for action_tag: String in _reviewed_action_catalog:
		inventory.append(_reviewed_action_catalog[action_tag].duplicate(true))
	return inventory


func preload_assets_for_semantics(semantic_keys: Array[String]) -> Array[String]:
	var queued: Array[String] = []
	for semantic_key: String in semantic_keys:
		if not _motion_assets.has(semantic_key):
			continue
		var entry: Variant = _motion_assets[semantic_key]
		if entry is Dictionary:
			queued.append(str(entry.get("asset_ref", "")))
		else:
			queued.append(str(entry))
	return queued


func compose_realization_plan(semantic_keys: Array[String], generated_motion_allowed: bool) -> Dictionary:
	var local_fallback_asset_refs := preload_assets_for_semantics(semantic_keys)
	var missing_semantic_keys: Array[String] = []
	for semantic_key: String in semantic_keys:
		if _motion_assets.has(semantic_key):
			continue
		missing_semantic_keys.append(semantic_key)
	return {
		"semantic_keys": semantic_keys,
		"generated_motion_allowed": generated_motion_allowed,
		"local_fallback_asset_refs": local_fallback_asset_refs,
		"missing_semantic_keys": missing_semantic_keys,
	}


func resolve_action_atoms(primitive_action_tags: Array, primitive_realization_keys: Array) -> Dictionary:
	var requested_keys: Array[String] = []
	for value: Variant in primitive_action_tags:
		var action_tag := str(value)
		if not action_tag.is_empty() and not requested_keys.has(action_tag):
			requested_keys.append(action_tag)
	for value: Variant in primitive_realization_keys:
		var realization_key := str(value)
		if not realization_key.is_empty() and not requested_keys.has(realization_key):
			requested_keys.append(realization_key)

	var selected_action_atoms: Array[Dictionary] = []
	var selected_action_tags: Array[String] = []
	var missing_action_keys: Array[String] = []
	for key: String in requested_keys:
		var entry: Variant = _motion_assets.get(key, null)
		if not (entry is Dictionary):
			missing_action_keys.append(key)
			continue
		var descriptor: Variant = entry.get("descriptor", {})
		if not (descriptor is Dictionary):
			missing_action_keys.append(key)
			continue
		var atom := (descriptor as Dictionary).duplicate(true)
		atom["action_tag"] = key
		atom["asset_ref"] = str(entry.get("asset_ref", atom.get("animation_clip_ref", "")))
		selected_action_atoms.append(atom)
		selected_action_tags.append(key)
	return {
		"status": "available" if missing_action_keys.is_empty() else "action_assets_unavailable",
		"selected_action_atoms": selected_action_atoms,
		"selected_action_tags": selected_action_tags,
		"missing_action_keys": missing_action_keys,
	}
