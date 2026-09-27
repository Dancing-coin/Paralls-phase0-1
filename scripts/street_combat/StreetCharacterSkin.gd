extends Node3D

@export var package_id := ""

var _manifest: Dictionary = {}
var _animation_player: AnimationPlayer
var _skeleton: Skeleton3D
var _current_clip := ""
var _motion_profile := "default"
var _recoil_tween: Tween
var _action_locked := false
var _action_unlock_time := 0.0

const IDLE_PLAYBACK_SPEED := 0.45


func _ready() -> void:
	var manifest_path := "res://assets/active/%s/manifest.json" % package_id
	var file := FileAccess.open(manifest_path, FileAccess.READ)
	if file != null:
		var parsed: Variant = JSON.parse_string(file.get_as_text())
		if parsed is Dictionary:
			_manifest = parsed
	_animation_player = _find_descendant(self, "AnimationPlayer") as AnimationPlayer
	_skeleton = _find_descendant(self, "Skeleton3D") as Skeleton3D
	_stabilize_idle_root_height()
	set_state("idle")


func _process(_delta: float) -> void:
	if not _action_locked or Time.get_ticks_msec() / 1000.0 < _action_unlock_time:
		return
	_action_locked = false
	_action_unlock_time = 0.0
	set_state("idle")


func _find_descendant(node: Node, type_name: String) -> Node:
	for child in node.get_children():
		if child.is_class(type_name):
			return child
		var found := _find_descendant(child, type_name)
		if found != null:
			return found
	return null


func _stabilize_idle_root_height() -> void:
	if _animation_player == null:
		return
	for library_name in _animation_player.get_animation_library_list():
		var library := _animation_player.get_animation_library(library_name)
		for animation_name in library.get_animation_list():
			if str(animation_name).to_lower() != "idle":
				continue
			var animation := library.get_animation(animation_name)
			if animation == null:
				continue
			for track_index in animation.get_track_count():
				if animation.track_get_type(track_index) != Animation.TYPE_POSITION_3D:
					continue
				if not str(animation.track_get_path(track_index)).to_lower().ends_with(":root.x"):
					continue
				if animation.track_get_key_count(track_index) == 0:
					continue
				var first_value: Variant = animation.track_get_key_value(track_index, 0)
				if not (first_value is Vector3):
					continue
				var locked_height := (first_value as Vector3).y
				for key_index in animation.track_get_key_count(track_index):
					var value: Variant = animation.track_get_key_value(track_index, key_index)
					if value is Vector3:
						var stable_value := value as Vector3
						stable_value.y = locked_height
						animation.track_set_key_value(track_index, key_index, stable_value)


func has_qualified_skeleton() -> bool:
	if _skeleton == null or _manifest.is_empty():
		return false
	var mapping: Dictionary = _manifest.get("canonical_mapping", {}).get("bones", {})
	for key in ["pelvis", "spine", "head", "left_upper_arm", "left_lower_arm", "left_hand", "right_upper_arm", "right_lower_arm", "right_hand", "left_upper_leg", "left_lower_leg", "left_foot", "right_upper_leg", "right_lower_leg", "right_foot"]:
		if _skeleton.find_bone(str(mapping.get(key, ""))) < 0:
			return false
	return true


func has_clip(clip: String) -> bool:
	return not _resolve_animation(clip).is_empty()


func _resolve_animation(clip: String) -> String:
	if _animation_player == null:
		return ""
	for candidate in _animation_player.get_animation_list():
		if str(candidate).to_lower() == clip.to_lower() or str(candidate).to_lower().ends_with("/" + clip.to_lower()):
			return str(candidate)
	return ""


func _play(clip: String, playback_speed: float = 1.0) -> bool:
	var resolved := _resolve_animation(clip)
	if resolved.is_empty():
		return false
	if _animation_player.current_animation != resolved or not _animation_player.is_playing():
		_animation_player.play(resolved, -1.0, playback_speed, false)
	_current_clip = resolved
	return true


func _play_action(clip: String) -> bool:
	if not _play(clip):
		return false
	var animation := _animation_player.get_animation(_current_clip)
	var duration := animation.length if animation != null else 0.0
	_action_locked = true
	_action_unlock_time = Time.get_ticks_msec() / 1000.0 + max(duration, 0.1)
	return true


func configure_role(_actor_id: String) -> void:
	pass


func set_state(state_name: String) -> void:
	var aliases: Dictionary = _manifest.get("clip_aliases", {})
	match state_name:
		"walk":
			if not _action_locked:
				_play(str(aliases.get("walk_forward", "walking")))
		"run":
			if not _action_locked:
				_play(str(aliases.get("run_forward", "running")))
		"jump":
			if not _action_locked:
				_play(str(aliases.get("jump_start", "jump")))
		"attack", "alert": _play_action(_attack_clip())
		_:
			if not _action_locked:
				_play(str(aliases.get("idle", "idle")), IDLE_PLAYBACK_SPEED)


func set_guard_stance(normalized_position: float = 0.34) -> bool:
	"""Hold a readable guard frame without creating an attack or authority event."""
	var resolved := _resolve_animation(_attack_clip())
	if resolved.is_empty() or _animation_player == null:
		return false
	var animation := _animation_player.get_animation(resolved)
	if animation == null:
		return false
	_animation_player.play(resolved)
	_animation_player.seek(clamp(normalized_position, 0.0, 1.0) * animation.length, true)
	_animation_player.pause()
	_current_clip = resolved
	_action_locked = true
	_action_unlock_time = INF
	return true


func ensure_guard_stance(normalized_position: float = 0.34) -> void:
	if _action_locked:
		return
	if not _current_clip.to_lower().ends_with("idle"):
		return
	set_guard_stance(normalized_position)


func set_motion_profile(state_name: String, profile_name: String) -> void:
	_motion_profile = profile_name
	set_state(state_name)


func play_qualified_profile(profile: Dictionary) -> Dictionary:
	var clip := str(profile.get("clip_ref", ""))
	var accepted := _play_action(clip)
	return {"accepted": accepted, "played_clip": _current_clip if accepted else "", "semantic_action_id": str(profile.get("semantic_action_id", ""))}


func play_reviewed_action_atom(_action_tag: String, animation_clip_ref: String, _phase: String) -> Dictionary:
	var accepted := _play_action(animation_clip_ref)
	return {"accepted": accepted, "played_clip": _current_clip if accepted else ""}


func restore_reviewed_action_playback() -> void:
	_action_locked = false
	_action_unlock_time = 0.0
	set_state("idle")


func play_recoil() -> void:
	if _recoil_tween != null and _recoil_tween.is_running():
		_recoil_tween.kill()
	rotation.z = 0.0
	_recoil_tween = create_tween()
	_recoil_tween.tween_property(self, "rotation:z", 0.16, 0.08)
	_recoil_tween.tween_property(self, "rotation:z", 0.0, 0.3)


func consume_root_motion_delta() -> Vector3:
	return Vector3.ZERO


func reset_root_motion() -> void:
	pass


func get_current_clip_name() -> String:
	return _current_clip


func get_current_motion_profile_name() -> String:
	return _motion_profile


func _attack_clip() -> String:
	for action in _manifest.get("actions", []):
		if str(action.get("semantic_action_id", "")) == "action:melee.unarmed_punch":
			return str(action.get("clip_ref", ""))
	return ""
