extends Node3D

var RoleAnimationControllerRef = load("res://scripts/character/RoleAnimationController.gd")
var RootMotionSamplerRef = load("res://scripts/character/RootMotionSampler.gd")
var CharacterPresentationRuntimeRef = load("res://scripts/character/CharacterPresentationRuntime.gd")

@export var package_id := ""

var _manifest: Dictionary = {}
var _animation_player: AnimationPlayer
var _skeleton: Skeleton3D
var _current_clip := ""
var _motion_profile := "default"
var _recoil_tween: Tween
var animation_controller: Node
var presentation_runtime: RefCounted
var root_motion_sampler: Node

func _ready() -> void:
	var manifest_path := "res://assets/active/%s/manifest.json" % package_id
	var file := FileAccess.open(manifest_path, FileAccess.READ)
	if file != null:
		var parsed: Variant = JSON.parse_string(file.get_as_text())
		if parsed is Dictionary:
			_manifest = parsed
	_animation_player = _find_descendant(self, "AnimationPlayer") as AnimationPlayer
	_skeleton = _find_descendant(self, "Skeleton3D") as Skeleton3D
	animation_controller = get_node_or_null("RoleAnimationController") as Node
	if animation_controller == null:
		animation_controller = RoleAnimationControllerRef.new()
		animation_controller.name = "RoleAnimationController"
		add_child(animation_controller)
	animation_controller.bind(self)
	presentation_runtime = CharacterPresentationRuntimeRef.new()
	presentation_runtime.bind(animation_controller)
	root_motion_sampler = get_node_or_null("RootMotionSampler") as Node
	if root_motion_sampler == null:
		root_motion_sampler = RootMotionSamplerRef.new()
		root_motion_sampler.name = "RootMotionSampler"
		add_child(root_motion_sampler)
	root_motion_sampler.bind(self)
	set_state("idle")


func _find_descendant(node: Node, type_name: String) -> Node:
	for child in node.get_children():
		if child.is_class(type_name):
			return child
		var found := _find_descendant(child, type_name)
		if found != null:
			return found
	return null


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
	if resolved.is_empty() or animation_controller == null:
		return false
	var state_name := _state_name_for_clip(resolved)
	if not animation_controller.play_state(state_name, resolved, false, playback_speed):
		return false
	_current_clip = resolved
	return true


func _play_action(clip: String) -> bool:
	var resolved := _resolve_animation(clip)
	if resolved.is_empty() or animation_controller == null:
		return false
	var state_name := _state_name_for_clip(resolved)
	var accepted: bool = animation_controller.play_action(resolved, state_name)
	if accepted:
		_current_clip = str(animation_controller.get_current_clip_name())
	return accepted


func configure_role(_actor_id: String) -> void:
	pass


func set_state(state_name: String) -> void:
	match state_name:
		"idle", "walk", "run", "jump": play_locomotion_state(state_name)
		"boxing", "attack", "alert": play_action_state("boxing")
		"sword_attack": play_action_state("sword_attack")
		_:
			if not play_source_state(state_name):
				play_locomotion_state("idle")


func play_locomotion_state(state_name: String) -> bool:
	var aliases: Dictionary = _manifest.get("clip_aliases", {})
	var clip := ""
	var playback_speed := 1.0
	match state_name:
		"walk":
			clip = str(aliases.get("walk_forward", "walking"))
		"run":
			clip = str(aliases.get("run_forward", "running"))
		"jump":
			clip = str(aliases.get("jump_start", "jump"))
		_:
			if animation_controller != null and animation_controller.is_locked():
				return false
			return _play(str(aliases.get("idle", "idle")))
	if animation_controller != null and animation_controller.is_locked():
		return false
	return _play(clip, playback_speed)


func play_action_state(state_name: String) -> bool:
	if state_name == "sword_attack":
		return _play_action(_sword_clip())
	if state_name == "boxing" or state_name == "attack":
		return _play_action(_attack_clip())
	return play_source_state(state_name, true)


func play_source_state(state_name: String, one_shot: bool = true, playback_speed: float = 1.0) -> bool:
	var resolved := _resolve_animation(state_name.replace("_", " "))
	if resolved.is_empty():
		resolved = _resolve_animation(state_name)
	if resolved.is_empty() or animation_controller == null:
		return false
	var normalized_state: String = animation_controller.state_name_for_clip(resolved) if animation_controller.has_method("state_name_for_clip") else _state_name_for_clip(resolved)
	if not animation_controller.get_available_states().has(normalized_state):
		return false
	var animation := _animation_player.get_animation(resolved) if _animation_player != null else null
	var looping: bool = animation != null and animation.loop_mode == Animation.LOOP_LINEAR
	var effective_one_shot := one_shot and not looping
	var accepted: bool = animation_controller.play_state(normalized_state, resolved, effective_one_shot, playback_speed)
	if not accepted:
		return false
	_current_clip = resolved
	return true


func get_source_animation_states() -> PackedStringArray:
	if animation_controller != null and animation_controller.has_method("get_available_states"):
		return animation_controller.get_available_states()
	return PackedStringArray()


func get_source_animation_clips() -> PackedStringArray:
	if animation_controller != null and animation_controller.has_method("get_available_clips"):
		return animation_controller.get_available_clips()
	return PackedStringArray()


func set_guard_stance(normalized_position: float = 0.34) -> bool:
	if animation_controller == null:
		return false
	var accepted: bool = animation_controller.hold_state("boxing", "", normalized_position)
	if accepted:
		_current_clip = str(animation_controller.get_current_clip_name())
	return accepted

func ensure_guard_stance(normalized_position: float = 0.34) -> void:
	if animation_controller == null or animation_controller.is_locked():
		return
	set_guard_stance(normalized_position)

func is_animation_tree_active() -> bool:
	return animation_controller != null and animation_controller.has_method("is_animation_tree_active") and animation_controller.is_animation_tree_active()


func get_animation_tree_path() -> NodePath:
	return animation_controller.get_animation_tree_path() if animation_controller != null and animation_controller.has_method("get_animation_tree_path") else NodePath()


func has_valid_animation_player_binding() -> bool:
	return animation_controller != null and animation_controller.has_method("has_valid_animation_player_binding") and animation_controller.has_valid_animation_player_binding()


func get_playback_state() -> String:
	return str(animation_controller.get_playback_state()) if animation_controller != null and animation_controller.has_method("get_playback_state") else ""


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
	if animation_controller != null:
		animation_controller.restore()
	_current_clip = str(animation_controller.get_current_clip_name()) if animation_controller != null else ""

func apply_presentation_input(input: Dictionary) -> Dictionary:
	if presentation_runtime == null:
		return {"accepted": false, "state": "idle", "reason": "presentation_runtime_missing"}
	var result: Dictionary = presentation_runtime.apply_presentation_input(input)
	_current_clip = str(result.get("clip_ref", _current_clip))
	return result

func play_recoil() -> void:
	if _recoil_tween != null and _recoil_tween.is_running():
		_recoil_tween.kill()
	rotation.z = 0.0
	_recoil_tween = create_tween()
	_recoil_tween.tween_property(self, "rotation:z", 0.16, 0.08)
	_recoil_tween.tween_property(self, "rotation:z", 0.0, 0.3)


func consume_root_motion_delta() -> Vector3:
	if root_motion_sampler == null:
		return Vector3.ZERO
	return root_motion_sampler.consume_delta()


func reset_root_motion() -> void:
	if root_motion_sampler != null:
		root_motion_sampler.reset()

func has_root_motion_track(clip_ref: String) -> bool:
	return root_motion_sampler != null and root_motion_sampler.has_method("has_root_track") and bool(root_motion_sampler.has_root_track(_resolve_animation(clip_ref)))


func get_current_clip_name() -> String:
	return _current_clip


func get_current_motion_profile_name() -> String:
	return _motion_profile


func _attack_clip() -> String:
	for action in _manifest.get("actions", []):
		if str(action.get("semantic_action_id", "")) == "action:melee.unarmed_punch":
			return str(action.get("clip_ref", ""))
	return ""

func _sword_clip() -> String:
	for action in _manifest.get("actions", []):
		var semantic := str(action.get("semantic_action_id", ""))
		if semantic == "action:melee.sword_slash" or semantic == "action:melee.sword_attack":
			return str(action.get("clip_ref", ""))
	for candidate in ["sword attack", "SWORD ATTACK", "sword_attack"]:
		if has_clip(candidate):
			return candidate
	return ""

func _state_name_for_clip(clip: String) -> String:
	if animation_controller != null and animation_controller.has_method("state_name_for_clip"):
		return animation_controller.state_name_for_clip(clip)
	var lower := clip.to_lower()
	if lower.ends_with("walking") or lower.ends_with("walk"):
		return "walk"
	if lower.ends_with("running") or lower.ends_with("run"):
		return "run"
	if lower.ends_with("jump"):
		return "jump"
	if lower.ends_with("sword attack") or lower.ends_with("sword_attack"):
		return "sword_attack"
	if lower.ends_with("boxing") or lower.ends_with("fight_punch"):
		return "boxing"
	return lower.replace(" ", "_")
