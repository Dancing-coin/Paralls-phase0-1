extends SceneTree

const BuilderRef = preload("res://scripts/qualification/MotionLibraryBuilder.gd")

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 1:
		push_error("Pass a native motion library manifest resource path after --")
		quit(1)
		return
	var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	var profile: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(str(manifest.get("skeleton_profile_ref", ""))))
	var source := str(profile.get("source_model_path", ""))
	if FileAccess.get_sha256(source).to_upper() != str(manifest.get("source_digest_sha256", "")):
		push_error("Native library source digest mismatch")
		quit(1)
		return
	var clips := PackedStringArray()
	for action: Dictionary in manifest.get("semantic_actions", {}).values():
		var clip := str(action.get("clip_ref", ""))
		if not clips.has(clip):
			clips.append(clip)
	var builder := BuilderRef.new()
	var output := str(manifest.get("animation_library_ref", ""))
	var result: Dictionary = builder.build_from_scene(source, clips, output, StringName(str(manifest.get("motion_library_id", ""))), StringName(str(profile.get("canonical_profile_id", ""))))
	builder.free()
	if not bool(result.get("accepted", false)):
		push_error(str(result))
		quit(1)
		return
	var library := load(output) as AnimationLibrary
	for action: Dictionary in manifest.get("semantic_actions", {}).values():
		var animation := library.get_animation(StringName(str(action.get("clip_ref", ""))))
		animation.loop_mode = Animation.LOOP_LINEAR if bool(action.get("loop", false)) else Animation.LOOP_NONE
	var error := ResourceSaver.save(library, output)
	print("native_motion_library_build=", result, " save_error=", error)
	quit(0 if error == OK else 1)
