extends Node
class_name MotionLibraryBuilder

func build_from_scene(
	source_scene_path: String,
	clip_names: PackedStringArray,
	output_path: String,
	library_id: StringName,
	skeleton_profile_id: StringName
) -> Dictionary:
	var result: Dictionary = _empty_result()
	result["library_id"] = String(library_id)
	if String(library_id).is_empty():
		return _reject(result, "library_id is required")
	if skeleton_profile_id != &"humanoid.v1":
		return _reject(result, "unsupported skeleton profile: %s" % String(skeleton_profile_id))
	if clip_names.is_empty():
		return _reject(result, "clip_names is empty")
	var seen := {}
	for clip_name in clip_names:
		if seen.has(clip_name):
			return _reject(result, "duplicate semantic clip: %s" % clip_name)
		seen[clip_name] = true
	var packed_scene := ResourceLoader.load(source_scene_path) as PackedScene
	if packed_scene == null:
		return _reject(result, "source scene could not be loaded: %s" % source_scene_path)
	var source_instance := packed_scene.instantiate()
	if source_instance == null:
		return _reject(result, "source scene could not be instantiated: %s" % source_scene_path)
	var animation_player := source_instance.find_child("AnimationPlayer", true, false) as AnimationPlayer
	if animation_player == null:
		source_instance.free()
		return _reject(result, "source scene has no AnimationPlayer")
	var source_library: AnimationLibrary = null
	for library_name in animation_player.get_animation_library_list():
		var candidate := animation_player.get_animation_library(library_name)
		if candidate != null:
			source_library = candidate
			break
	if source_library == null:
		source_instance.free()
		return _reject(result, "source AnimationPlayer has no AnimationLibrary")
	var allowed_bones := _allowed_track_bones(source_instance, source_scene_path)
	var output_library := AnimationLibrary.new()
	var refs := PackedStringArray()
	var track_counts: Dictionary = {}
	var duration_seconds: Dictionary = {}
	for clip_name in clip_names:
		var source_clip_name := _source_clip_name(source_library, clip_name)
		if source_clip_name.is_empty():
			source_instance.free()
			return _reject(result, "missing approved clip: %s" % clip_name)
		var source_animation := source_library.get_animation(source_clip_name)
		if source_animation == null:
			source_instance.free()
			return _reject(result, "clip is not an Animation resource: %s" % clip_name)
		if source_animation.get_track_count() == 0:
			source_instance.free()
			return _reject(result, "clip has no tracks: %s" % clip_name)
		if not _validate_animation_tracks(source_animation, allowed_bones):
			source_instance.free()
			return _reject(result, "clip has non humanoid.v1 canonical bone path: %s" % clip_name)
		var copied_animation := source_animation.duplicate(true) as Animation
		if copied_animation == null:
			source_instance.free()
			return _reject(result, "clip could not be duplicated: %s" % clip_name)
		if output_library.add_animation(clip_name, copied_animation) != OK:
			source_instance.free()
			return _reject(result, "clip could not be added to output library: %s" % clip_name)
		refs.append(clip_name)
		var bone_count := _unique_bone_count(copied_animation)
		track_counts[clip_name] = bone_count * 3
		duration_seconds[clip_name] = copied_animation.length
	source_instance.free()
	output_library.resource_name = String(library_id)
	var save_error := ResourceSaver.save(output_library, output_path)
	if save_error != OK:
		return _reject(result, "could not save AnimationLibrary (%s): %s" % [save_error, output_path])
	result["accepted"] = true
	result["clip_refs"] = refs
	result["track_counts"] = track_counts
	result["duration_seconds"] = duration_seconds
	return result

func _source_clip_name(source_library: AnimationLibrary, clip_name: StringName) -> StringName:
	if source_library.has_animation(clip_name):
		return clip_name
	var aliases := {
		&"sword_attack": &"sword attack",
	}
	var alias: StringName = aliases.get(clip_name, &"")
	if not alias.is_empty() and source_library.has_animation(alias):
		return alias
	return &""

func _empty_result() -> Dictionary:
	return {
		"accepted": false,
		"library_id": "",
		"clip_refs": PackedStringArray(),
		"track_counts": {},
		"duration_seconds": {},
		"rejection_reason": "",
	}

func _reject(result: Dictionary, reason: String) -> Dictionary:
	result["accepted"] = false
	result["rejection_reason"] = reason
	return result

func _allowed_track_bones(source_instance: Node, source_scene_path: String) -> Dictionary:
	var names := {}
	var skeleton := source_instance.find_child("Skeleton3D", true, false) as Skeleton3D
	if skeleton != null:
		for index in skeleton.get_bone_count():
			names[skeleton.get_bone_name(index)] = true
	var manifest_path := source_scene_path.get_base_dir().path_join("manifest.json")
	if FileAccess.file_exists(manifest_path):
		var file := FileAccess.open(manifest_path, FileAccess.READ)
		if file != null:
			var parsed = JSON.parse_string(file.get_as_text())
			if parsed is Dictionary:
				var mapping = parsed.get("canonical_mapping", {}).get("bones", {})
				if mapping is Dictionary:
					for source_name in mapping.values():
						names[str(source_name)] = true
	return names

func _validate_animation_tracks(animation: Animation, allowed_bones: Dictionary) -> bool:
	var seen_bones := {}
	for index in animation.get_track_count():
		if animation.track_get_key_count(index) == 0:
			return false
		var path_text := String(animation.track_get_path(index))
		var separator := path_text.rfind(":")
		if separator < 0:
			return false
		var bone_name := path_text.substr(separator + 1)
		if bone_name.is_empty() or not allowed_bones.has(bone_name):
			return false
		seen_bones[bone_name] = true
	return not seen_bones.is_empty()

func _unique_bone_count(animation: Animation) -> int:
	var names := {}
	for index in animation.get_track_count():
		var path_text := String(animation.track_get_path(index))
		var separator := path_text.rfind(":")
		if separator >= 0:
			names[path_text.substr(separator + 1)] = true
	return names.size()
