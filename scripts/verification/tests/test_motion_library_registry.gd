extends SceneTree

const Registry = preload("res://scripts/character/CharacterEmbodimentAssetRegistry.gd")
const MOTION_MANIFEST_PATH := "res://assets/motion_library/approved/humanoid.v1/street_locomotion.manifest.json"
const MOTION_LIBRARY_PATH := "res://assets/motion_library/approved/humanoid.v1/street_locomotion.tres"

var _failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	test_registry_resolves_shared_walk_without_raw_clip_lookup()
	test_registry_rejects_rejected_motion_manifest()
	test_registry_rejects_mismatched_skeleton_profile()
	test_registry_rejects_raw_clip_lookup()
	if _failures.is_empty():
		print("PASS test_motion_library_registry")
		quit(0)
		return
	print("FAILURES count=%d values=%s" % [_failures.size(), str(_failures)])
	push_error("; ".join(_failures))
	quit(1)


func test_registry_resolves_shared_walk_without_raw_clip_lookup() -> void:
	var registry := Registry.new()
	var result: Dictionary = registry.resolve_motion_realization(&"female_t_external", &"action:locomotion.walk", [])
	_assert_true(bool(result.get("accepted", false)), "shared walk should be accepted")
	_assert_eq(result.get("motion_library_id", ""), "motionlib:humanoid.v1.core@1", "shared walk library id")
	_assert_eq(result.get("realization_mode", ""), "shared_library", "shared walk realization mode")
	_assert_eq(result.get("clip_ref", ""), "walking2", "shared walk clip")
	_assert_true(result.get("animation_library", null) is AnimationLibrary, "shared walk library resource")


func test_registry_rejects_rejected_motion_manifest() -> void:
	var registry := Registry.new()
	var manifest := _motion_manifest()
	manifest["qualification_status"] = "rejected"
	var accepted: bool = registry.register_motion_library(&"motionlib:test.rejected@1", manifest, AnimationLibrary.new())
	_assert_true(not accepted, "rejected motion manifest must not register")
	_assert_eq(registry.inventory_motion_libraries().size(), 1, "rejected manifest must not enter inventory")


func test_registry_rejects_mismatched_skeleton_profile() -> void:
	var registry := Registry.new()
	var manifest := _motion_manifest()
	manifest["motion_library_id"] = "motionlib:test.mismatch@1"
	manifest["skeleton_profile_id"] = "humanoid.v2"
	var accepted: bool = registry.register_motion_library(&"motionlib:test.mismatch@1", manifest, AnimationLibrary.new())
	_assert_true(not accepted, "mismatched skeleton profile must not register")
	_assert_eq(registry.inventory_motion_libraries().size(), 1, "mismatched manifest must not enter inventory")


func test_registry_rejects_raw_clip_lookup() -> void:
	var registry := Registry.new()
	var result: Dictionary = registry.resolve_motion_realization(&"female_t_external", &"action:locomotion.walk", [], "walking2")
	_assert_true(not bool(result.get("accepted", false)), "raw clip lookup must be rejected")
	_assert_eq(result.get("reason", ""), "raw_clip_lookup_forbidden", "raw clip rejection reason")


func _motion_manifest() -> Dictionary:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(MOTION_MANIFEST_PATH))
	return parsed.duplicate(true) if parsed is Dictionary else {}


func _assert_true(value: bool, label: String) -> void:
	if not value:
		_failures.append(label)


func _assert_eq(actual: Variant, expected: Variant, label: String) -> void:
	if actual != expected:
		_failures.append("%s: %s != %s" % [label, str(actual), str(expected)])
