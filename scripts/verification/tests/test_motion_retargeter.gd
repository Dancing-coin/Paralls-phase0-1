extends SceneTree

const MotionRetargeter = preload("res://scripts/character/MotionRetargeter.gd")

func _initialize() -> void:
	call_deferred("_run")

func _run() -> void:
	var retargeter := MotionRetargeter.new()
	var first := retargeter.compute_cache_key("motionlib:humanoid.v1.core@1", "SRC", "humanoid.v2", "DST", "body:female_t.default", "calibration:humanoid.v1.street.default", "retargeter.v1")
	var second := retargeter.compute_cache_key("motionlib:humanoid.v1.core@1", "SRC", "humanoid.v2", "DST", "body:female_t.default", "calibration:humanoid.v1.street.default", "retargeter.v1")
	assert_eq(first, second)
	assert_true(first.begins_with("retarget-cache-"))

	var source_profile := _profile()
	var target_profile := _profile()
	var library := _library()
	var output_path := "user://motion-retarget-test.tres"
	var accepted := retargeter.build_library(library, source_profile, target_profile, {"profile_id": "body:female_t.default"}, {"profile_id": "calibration:humanoid.v1.street.default"}, output_path)
	assert_true(accepted.get("accepted", false))
	assert_eq(accepted.get("realization_mode", ""), "retargeted_library")
	assert_eq(accepted.get("clip_reports", []).size(), 6)
	assert_true(FileAccess.file_exists(output_path))

	var missing_target := _profile()
	missing_target["canonical_bones"].erase("hand_r")
	var missing := retargeter.build_library(library, source_profile, missing_target, {}, {}, "user://motion-retarget-missing.tres")
	assert_true(not missing.get("accepted", true))
	assert_eq(missing.get("rejection_reason", ""), "missing_canonical_bone:hand_r")

	var conflict_target := _profile()
	conflict_target["canonical_bones"]["hand_l"] = "hand.r"
	var conflict := retargeter.build_library(library, source_profile, conflict_target, {}, {}, "user://motion-retarget-conflict.tres")
	assert_true(not conflict.get("accepted", true))
	assert_eq(conflict.get("rejection_reason", ""), "axis_mismatch")

	print("MOTION_RETARGET_CACHE_KEY=%s" % first)
	print("MOTION_RETARGET_ACCEPTED_CLIPS=%d" % accepted.get("clip_reports", []).size())
	print("MOTION_RETARGET_REJECTION=%s" % missing.get("rejection_reason", ""))
	quit(0)

func _profile() -> Dictionary:
	return {
		"skeleton_profile_id": "humanoid.v1",
		"canonical_bones": {
			"root": "root",
			"pelvis": "pelvis",
			"hand_l": "hand.l",
			"hand_r": "hand.r",
		},
		"rest_pose": "humanoid_v1_rest",
		"forward_axis": "+Z",
	}

func _library() -> AnimationLibrary:
	var library := AnimationLibrary.new()
	for clip_name in ["idle", "walking2", "running", "jump", "boxing", "sword_attack"]:
		var animation := Animation.new()
		animation.length = 1.0
		var track := animation.add_track(Animation.TYPE_VALUE)
		animation.track_set_path(track, NodePath("rig/Skeleton3D:root.x"))
		animation.track_insert_key(track, 0.0, 0.0)
		if clip_name == "sword_attack":
			var hand_track := animation.add_track(Animation.TYPE_VALUE)
			animation.track_set_path(hand_track, NodePath("rig/Skeleton3D:hand.r"))
			animation.track_insert_key(hand_track, 0.0, 0.0)
		library.add_animation(clip_name, animation)
	return library

func assert_true(value: bool) -> void:
	if not value:
		push_error("assert_true failed")
		quit(1)

func assert_eq(actual, expected) -> void:
	if actual != expected:
		push_error("assert_eq failed: %s != %s" % [str(actual), str(expected)])
		quit(1)
