extends SceneTree

const MotionLibraryBuilder = preload("res://scripts/qualification/MotionLibraryBuilder.gd")
const SOURCE_PATH := "res://assets/active/female_jk_external/female_jk_external.glb"
const OUTPUT_PATH := "res://assets/motion_library/approved/humanoid.v1/street_locomotion.tres"

func _initialize() -> void:
	call_deferred("_run")

func _run() -> void:
	var clips := PackedStringArray(["idle", "walking2", "running", "jump", "boxing", "sword_attack"])
	var source_digest_before := _sha256(SOURCE_PATH)
	var builder := MotionLibraryBuilder.new()
	var result: Dictionary = builder.build_from_scene(
		SOURCE_PATH,
		clips,
		OUTPUT_PATH,
		&"motionlib:humanoid.v1.core@1",
		&"humanoid.v1"
	)
	builder.free()
	assert_true(result.get("accepted", false))
	assert_eq(result.get("clip_refs", PackedStringArray()).size(), 6)
	assert_eq(result.get("track_counts", {}).get("walking2", -1), 204)
	assert_almost_eq(float(result.get("duration_seconds", {}).get("walking2", -1.0)), 0.566666667, 0.000001)
	assert_true(ResourceLoader.exists(OUTPUT_PATH))
	var library := ResourceLoader.load(OUTPUT_PATH) as AnimationLibrary
	assert_true(library != null)
	for clip_name in clips:
		assert_true(library.has_animation(clip_name))
	assert_eq(source_digest_before, _sha256(SOURCE_PATH))
	library = null
	quit(0)

func _sha256(path: String) -> String:
	return FileAccess.get_sha256(path)

func assert_true(value: bool) -> void:
	if not value:
		push_error("assert_true failed")
		quit(1)

func assert_eq(actual, expected) -> void:
	if actual != expected:
		push_error("assert_eq failed: %s != %s" % [str(actual), str(expected)])
		quit(1)

func assert_almost_eq(actual: float, expected: float, tolerance: float) -> void:
	if abs(actual - expected) > tolerance:
		push_error("assert_almost_eq failed: %f != %f" % [actual, expected])
		quit(1)
