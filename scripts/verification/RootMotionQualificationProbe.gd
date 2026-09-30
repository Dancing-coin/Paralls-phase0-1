extends Node

## Measures root tracks from imported Godot package scenes. Evidence only.

const PACKAGE_IDS := ["female_bandage_external", "female_jk_external", "female_t_external"]
const ROOT_BONE_NAMES := ["root.x", "root", "Root", "hips", "Hips"]
const EPSILON := 0.0001

func _ready() -> void:
	_run()

func _run() -> void:
	var packages: Dictionary = {}
	var ok := true
	for package_id in PACKAGE_IDS:
		var measured := _measure_package(package_id)
		packages[package_id] = measured
		ok = ok and not str(measured.get("source_digest_sha256", "")).is_empty() and not measured.has("error")
	var result := {"contract": "root_motion_qualification.v1", "qualified": false, "policy": "hold", "production_admission": "closed_until_calibrated", "packages": packages, "probe_ok": ok}
	print("root_motion_qualification:%s" % JSON.stringify(result))
	get_tree().quit(0 if ok else 1)

func _measure_package(package_id: String) -> Dictionary:
	var manifest := _read_json("res://assets/active/%s/manifest.json" % package_id)
	var source_path := str(manifest.get("source_model_path", ""))
	var package := {"package_id": package_id, "source_model_path": source_path, "manifest_source_digest_sha256": str(manifest.get("source", {}).get("digest_sha256", "")).to_upper(), "source_digest_sha256": _sha256(source_path), "axis": {"forward": str(manifest.get("forward_axis", "")), "up": str(manifest.get("up_axis", ""))}, "unit_scale": float(manifest.get("unit_scale", 0.0)), "root_profile": manifest.get("root_motion_profile", {}), "clips": {}, "imported_space": "godot_animation_track_local"}
	if source_path.is_empty() or not ResourceLoader.exists(source_path):
		package["error"] = "source_model_missing"
		return package
	var packed := load(source_path) as PackedScene
	if packed == null:
		package["error"] = "source_model_not_packed_scene"
		return package
	var instance := packed.instantiate()
	var animation_player := _find_animation_player(instance)
	package["skeleton_present"] = _find_skeleton(instance) != null
	if animation_player == null:
		package["error"] = "animation_player_missing"
		instance.free()
		return package
	var locomotion: Dictionary = manifest.get("locomotion_map", {})
	var aliases: Dictionary = manifest.get("clip_aliases", {})
	var refs: Dictionary = {}
	for tag in ["idle", "walk_forward", "run_forward", "jump_start", "jump_loop", "jump_land"]:
		var clip_ref := str(locomotion.get(tag, ""))
		if clip_ref.is_empty() and aliases.has(tag): clip_ref = str(aliases[tag])
		if not clip_ref.is_empty(): refs[tag] = clip_ref
	for tag in refs:
		var clip_ref := str(refs[tag])
		(package["clips"] as Dictionary)[str(tag)] = _measure_clip(_resolve_animation(animation_player, clip_ref), clip_ref, str(tag), package)
	instance.free()
	return package

func _measure_clip(animation: Animation, requested_ref: String, tag: String, package: Dictionary) -> Dictionary:
	var result := {"requested_clip": requested_ref, "tag": tag, "duration_seconds": 0.0, "cadence": {"sample_count": 0, "min_interval_seconds": 0.0, "max_interval_seconds": 0.0, "mean_interval_seconds": 0.0}, "envelope": {"start_local": Vector3.ZERO, "end_local": Vector3.ZERO, "net_displacement": Vector3.ZERO, "net_displacement_magnitude": 0.0, "max_abs_vertical_displacement": 0.0, "max_distance_from_start": 0.0}, "root_track_path": "", "root_track_present": false, "support": {"imported_space": true, "finite_values": false, "skeleton_present": bool(package.get("skeleton_present", false))}, "classification": "in_place", "policy": "hold", "qualified": false, "rejection_reason": "zero_displacement_in_place"}
	if animation == null:
		result["rejection_reason"] = "clip_missing_from_imported_animation_player"
		return result
	result["duration_seconds"] = animation.length
	var root_track := _find_root_track(animation)
	if root_track < 0: return result
	result["root_track_present"] = true
	result["root_track_path"] = str(animation.track_get_path(root_track))
	var key_count := animation.track_get_key_count(root_track)
	(result["cadence"] as Dictionary)["sample_count"] = key_count
	if key_count < 2:
		result["rejection_reason"] = "root_track_insufficient_samples"
		return result
	var positions: Array[Vector3] = []
	var times: Array[float] = []
	var finite_values := true
	for key_index in key_count:
		var value: Variant = animation.track_get_key_value(root_track, key_index)
		var position := value as Vector3 if value is Vector3 else Vector3.ZERO
		if not value is Vector3 or not _finite_vector(position): finite_values = false
		positions.append(position)
		times.append(animation.track_get_key_time(root_track, key_index))
	(result["support"] as Dictionary)["finite_values"] = finite_values
	if not finite_values:
		result["rejection_reason"] = "malformed_root_track_value"
		return result
	var intervals: Array[float] = []
	for index in range(1, times.size()): intervals.append(max(times[index] - times[index - 1], 0.0))
	if not intervals.is_empty():
		var cadence: Dictionary = result["cadence"]
		cadence["min_interval_seconds"] = _array_min(intervals)
		cadence["max_interval_seconds"] = _array_max(intervals)
		cadence["mean_interval_seconds"] = _array_sum(intervals) / float(intervals.size())
	var start := positions[0]
	var end := positions[positions.size() - 1]
	var net := end - start
	var max_height := 0.0
	var max_distance := 0.0
	for position in positions:
		max_height = max(max_height, abs(position.y - start.y))
		max_distance = max(max_distance, position.distance_to(start))
	var envelope: Dictionary = result["envelope"]
	envelope["start_local"] = _vector_json(start)
	envelope["end_local"] = _vector_json(end)
	envelope["net_displacement"] = _vector_json(net)
	envelope["net_displacement_magnitude"] = net.length()
	envelope["max_abs_vertical_displacement"] = max_height
	envelope["max_distance_from_start"] = max_distance
	if net.length() > EPSILON:
		result["classification"] = "root_motion_candidate"
		result["rejection_reason"] = "calibration_pending"
	return result

func _resolve_animation(player: AnimationPlayer, clip_ref: String) -> Animation:
	var direct := player.get_animation(clip_ref)
	if direct != null: return direct
	for name in player.get_animation_list():
		if str(name).to_lower() == clip_ref.to_lower(): return player.get_animation(name)
	return null

func _find_root_track(animation: Animation) -> int:
	for index in animation.get_track_count():
		if animation.track_get_type(index) != Animation.TYPE_POSITION_3D: continue
		var path := str(animation.track_get_path(index)).to_lower()
		for bone_name in ROOT_BONE_NAMES:
			var needle := ":%s" % bone_name.to_lower()
			if path.ends_with(needle) or path.contains(needle + ":"): return index
	return -1

func _find_animation_player(root: Node) -> AnimationPlayer:
	if root is AnimationPlayer: return root as AnimationPlayer
	for child in root.get_children():
		var found := _find_animation_player(child)
		if found != null: return found
	return null

func _find_skeleton(root: Node) -> Skeleton3D:
	if root is Skeleton3D: return root as Skeleton3D
	for child in root.get_children():
		var found := _find_skeleton(child)
		if found != null: return found
	return null

func _read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path): return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed as Dictionary if parsed is Dictionary else {}

func _sha256(path: String) -> String:
	var bytes := FileAccess.get_file_as_bytes(path)
	if bytes.is_empty(): return ""
	var hashing := HashingContext.new()
	hashing.start(HashingContext.HASH_SHA256)
	hashing.update(bytes)
	return hashing.finish().hex_encode().to_upper()

func _finite_vector(value: Vector3) -> bool:
	return is_finite(value.x) and is_finite(value.y) and is_finite(value.z)

func _vector_json(value: Vector3) -> Dictionary:
	return {"x": value.x, "y": value.y, "z": value.z}

func _array_min(values: Array[float]) -> float:
	var result := values[0]
	for value in values: result = min(result, value)
	return result

func _array_max(values: Array[float]) -> float:
	var result := values[0]
	for value in values: result = max(result, value)
	return result

func _array_sum(values: Array[float]) -> float:
	var result := 0.0
	for value in values: result += value
	return result
