extends SceneTree


const Registry := preload("res://scripts/character/CharacterEmbodimentAssetRegistry.gd")


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var registry = Registry.new()
	var result := {
		"female_jk_external": _resolve_package(registry, &"female_jk_external"),
		"female_t_external": _resolve_package(registry, &"female_t_external"),
		"female_bandage_external": _resolve_package(registry, &"female_bandage_external"),
		"rejected_registration": _reject_profile(registry),
		"validation_matrix": _validation_matrix(registry),
	}
	print("TASK8_REGISTRY_PROBE=" + JSON.stringify(result))
	var passed := bool(result["female_jk_external"].get("passed", false)) and bool(result["female_t_external"].get("passed", false)) and bool(result["female_bandage_external"].get("passed", false)) and bool(result["rejected_registration"]) and _all_true(result["validation_matrix"])
	quit(0 if passed else 1)


func _resolve_package(registry: CharacterEmbodimentAssetRegistry, package_id: StringName) -> Dictionary:
	var unarmed := registry.resolve(package_id, &"action:melee.unarmed_punch", [])
	var full_body := registry.resolve(package_id, &"action:melee.sword_slash", [&"locomotion"])
	var hitscan := registry.resolve(package_id, &"action:hitscan.semantic_request", [&"locomotion"])
	return {
		"passed": bool(unarmed.get("accepted", false)) and str(unarmed.get("profile", {}).get("mode", "")) == "full_body_exclusive" and bool(full_body.get("fallback_applied", false)) and str(full_body.get("profile", {}).get("mode", "")) == "full_body_exclusive" and bool(hitscan.get("accepted", false)),
		"unarmed_profile": unarmed.get("profile", {}).get("profile_id", ""),
		"full_body_status": full_body.get("status", ""),
		"full_body_profile": full_body.get("profile", {}).get("profile_id", ""),
		"hitscan_profile": hitscan.get("profile", {}).get("profile_id", ""),
	}


func _reject_profile(registry: CharacterEmbodimentAssetRegistry) -> bool:
	var manifest := _read_json("res://assets/active/female_jk_external/manifest.json")
	var rejected_report := _read_json("res://assets/characters/qualification_reports/female_jk_external.json")
	rejected_report["status"] = "rejected"
	return not registry.register_qualified_package(&"female_jk_external", manifest, rejected_report, "res://assets/characters/qualification_reports/female_jk_external.json")


func _validation_matrix(registry: CharacterEmbodimentAssetRegistry) -> Dictionary:
	var manifest := _read_json("res://assets/active/female_jk_external/manifest.json")
	var report := _read_json("res://assets/characters/qualification_reports/female_jk_external.json")
	var report_ref := "res://assets/characters/qualification_reports/female_jk_external.json"
	var digest_mismatch := manifest.duplicate(true)
	digest_mismatch["source"]["digest_sha256"] = "0".repeat(64)
	var canonical_mapping_missing := manifest.duplicate(true)
	canonical_mapping_missing.erase("canonical_mapping")
	var manifest_status_mismatch := manifest.duplicate(true)
	manifest_status_mismatch["actions_qualification_status"] = "rejected"
	var atomic_sequence_nonempty := manifest.duplicate(true)
	atomic_sequence_nonempty["atomic_sequence"] = ["atom:forbidden"]
	var required_slot_missing := manifest.duplicate(true)
	required_slot_missing["slots"].erase("weapon_hit_volume:sword")
	return {
		"digest_mismatch": not registry.register_qualified_package(&"female_jk_external", digest_mismatch, report, report_ref),
		"canonical_mapping_missing": not registry.register_qualified_package(&"female_jk_external", canonical_mapping_missing, report, report_ref),
		"manifest_status_mismatch": not registry.register_qualified_package(&"female_jk_external", manifest_status_mismatch, report, report_ref),
		"atomic_sequence_nonempty": not registry.register_qualified_package(&"female_jk_external", atomic_sequence_nonempty, report, report_ref),
		"required_slot_missing": not registry.register_qualified_package(&"female_jk_external", required_slot_missing, report, report_ref),
	}


func _all_true(values: Variant) -> bool:
	if not (values is Dictionary):
		return false
	for value in (values as Dictionary).values():
		if not bool(value):
			return false
	return true


func _read_json(path: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed if parsed is Dictionary else {}
