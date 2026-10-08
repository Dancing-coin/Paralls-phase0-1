extends "res://scripts/character/CharacterPresentationAdapter.gd"

var RoleAnimationControllerRef = load("res://scripts/character/RoleAnimationController.gd")
var RootMotionSamplerRef = load("res://scripts/character/RootMotionSampler.gd")
var CharacterPresentationRuntimeRef = load("res://scripts/character/CharacterPresentationRuntime.gd")
const CharacterEmbodimentAssetRegistryRef = preload("res://scripts/character/CharacterEmbodimentAssetRegistry.gd")

@export var package_id := ""
@export var motion_library_id := ""
@export_file("*.json") var manifest_path := ""
@export_file("*.json") var qualification_report_path := ""

var asset_registry: RefCounted
var _registration_status: Dictionary = {}

var _manifest: Dictionary = {}
var _animation_player: AnimationPlayer
var _skeleton: Skeleton3D
var _current_clip := ""
var _motion_profile := "default"
var _mounted_motion_library_id := ""
var _mounted_realization_mode := ""
var _uses_shared_motion_library := false
var _fallback_applied := false
var _fallback_reason := ""
var _root_motion_consumed_tick := -1
var _root_motion_consume_count := 0
var _recoil_tween: Tween
var animation_controller: Node
var presentation_runtime: RefCounted
var root_motion_sampler: Node

func _ready() -> void:
	var resolved_manifest_path := manifest_path if not manifest_path.is_empty() else "res://assets/active/%s/manifest.json" % package_id
	var file := FileAccess.open(resolved_manifest_path, FileAccess.READ)
	if file != null:
		var parsed: Variant = JSON.parse_string(file.get_as_text())
		if parsed is Dictionary:
			_manifest = parsed
	var alignment := apply_visual_alignment(_manifest)
	if not bool(alignment.get("accepted", false)):
		_registration_status = alignment
		push_error("Character package visual alignment failed: %s" % str(alignment))
		return
	_animation_player = _find_descendant(self, "AnimationPlayer") as AnimationPlayer
	_skeleton = _find_descendant(self, "Skeleton3D") as Skeleton3D
	asset_registry = CharacterEmbodimentAssetRegistryRef.new()
	if not qualification_report_path.is_empty():
		_registration_status = asset_registry.register_project_presentation_package(StringName(package_id), resolved_manifest_path, qualification_report_path, _animation_player, _skeleton)
		if not bool(_registration_status.get("accepted", false)):
			push_error("Character package registration failed: %s" % str(_registration_status))
	_mount_declared_motion_library()
	animation_controller = get_node_or_null("RoleAnimationController") as Node
	if animation_controller == null:
		animation_controller = RoleAnimationControllerRef.new()
		animation_controller.name = "RoleAnimationController"
		add_child(animation_controller)
	animation_controller.state_clip_candidates = _manifest.get("presentation_states", {})
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


func apply_visual_alignment(manifest: Dictionary) -> Dictionary:
	# Source-axis metadata describes the imported package; explicit calibration
	# overrides legacy metadata. Actor forward is always local -Z.
	if str(manifest.get("up_axis", "+y")).to_lower() != "+y":
		return {"accepted": false, "reason": "visual_up_axis_unsupported"}
	var source_axis := str(manifest.get("forward_axis", "-z")).to_lower()
	var axis_yaw := {"-z": 0.0, "+z": 180.0, "+x": 90.0, "-x": -90.0}
	if not axis_yaw.has(source_axis):
		return {"accepted": false, "reason": "visual_forward_axis_unsupported"}
	var calibration: Variant = manifest.get("presentation_alignment", {})
	if not (calibration is Dictionary):
		return {"accepted": false, "reason": "visual_alignment_invalid"}
	var yaw: Variant = calibration.get("visual_yaw_degrees", axis_yaw[source_axis])
	if not (yaw is float or yaw is int) or not is_finite(float(yaw)):
		return {"accepted": false, "reason": "visual_yaw_invalid"}
	# Assign instead of accumulating, including when a legacy scene has an offset.
	rotation.y = deg_to_rad(float(yaw))
	return {"accepted": true, "visual_yaw_degrees": float(yaw), "actor_forward_axis": "-z"}


func mount_motion_library(library: AnimationLibrary, library_id: StringName, realization_mode: String = "shared_library") -> bool:
	if _animation_player == null or library == null or String(library_id).is_empty():
		_fallback_applied = true
		_fallback_reason = "shared_library_unavailable"
		return false
	if _animation_player.has_animation_library(&"central"):
		_animation_player.remove_animation_library(&"central")
	_animation_player.add_animation_library(&"central", library)
	if not _animation_player.has_animation_library(&"central"):
		_fallback_applied = true
		_fallback_reason = "shared_library_mount_failed"
		return false
	_mounted_motion_library_id = String(library_id)
	_mounted_realization_mode = realization_mode
	_uses_shared_motion_library = realization_mode == "shared_library"
	return true


func get_mounted_motion_library_id() -> String:
	return _mounted_motion_library_id


func uses_shared_motion_library() -> bool:
	return _uses_shared_motion_library


func get_mounted_realization_mode() -> String:
	return _mounted_realization_mode


func is_fallback_applied() -> bool:
	return _fallback_applied


func get_fallback_reason() -> String:
	return _fallback_reason


func resolve_motion_realization(semantic_action_id: String, claims: Array[StringName] = []) -> Dictionary:
	if asset_registry == null:
		return {"accepted": false, "reason": _registration_status.get("reason", "package_not_initialized")}
	return asset_registry.resolve_motion_realization(StringName(package_id), StringName(semantic_action_id), claims)


func get_registration_status() -> Dictionary:
	return _registration_status.duplicate(true)


func play_semantic_action(semantic_action_id: String, state_name: String, profile_name: String = "default", playback_speed: float = 1.0, provided_realization: Dictionary = {}) -> Dictionary:
	var realization := provided_realization.duplicate(true) if not provided_realization.is_empty() else resolve_motion_realization(semantic_action_id)
	if not bool(realization.get("accepted", false)):
		_fallback_applied = true
		_fallback_reason = str(realization.get("reason", "semantic_action_unavailable"))
		return realization
	if bool(realization.get("fallback_applied", false)):
		_fallback_applied = true
		_fallback_reason = str(realization.get("reason", "shared_library_unavailable"))
	_motion_profile = profile_name
	var clip_ref := str(realization.get("clip_ref", ""))
	var is_one_shot := state_name in ["boxing", "attack", "sword_attack"]
	var played := _play_action(clip_ref) if is_one_shot else _play(clip_ref, playback_speed)
	realization["playback_accepted"] = played
	if played:
		realization["played_clip"] = _current_clip
	return realization


func _mount_declared_motion_library() -> void:
	var declared_id := str(_manifest.get("motion_library_id", motion_library_id))
	if declared_id.is_empty():
		_fallback_applied = true
		_fallback_reason = "motion_library_id_missing"
		return
	var claims: Array[StringName] = []
	var realization: Dictionary = asset_registry.resolve_motion_realization(StringName(package_id), &"action:locomotion.idle", claims)
	if bool(realization.get("accepted", false)):
		var resolved_library: AnimationLibrary = realization.get("animation_library", null) as AnimationLibrary
		if resolved_library != null and mount_motion_library(resolved_library, StringName(str(realization.get("motion_library_id", declared_id))), str(realization.get("realization_mode", "shared_library"))):
			return
	var inventory: Array[Dictionary] = asset_registry.inventory_motion_libraries()
	for entry: Dictionary in inventory:
		if str(entry.get("motion_library_id", "")) != declared_id:
			continue
		var library: AnimationLibrary = entry.get("animation_library", null) as AnimationLibrary
		if mount_motion_library(library, StringName(declared_id), str(entry.get("realization_mode", "shared_library"))):
			return
	_fallback_applied = true
	_fallback_reason = "shared_library_unavailable"


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
	if not _resolve_animation(clip).is_empty():
		return true
	var aliases: Dictionary = _manifest.get("clip_aliases", {})
	var alias_key: String = str({
		"idle": "idle",
		"walk": "walk_forward",
		"run": "run_forward",
		"jump": "jump_start",
		"boxing": "boxing",
		"sword_attack": "sword_attack",
	}.get(clip, ""))
	if not alias_key.is_empty():
		return not _resolve_animation(str(aliases.get(alias_key, clip))).is_empty()
	return false


func _resolve_animation(clip: String) -> String:
	if _animation_player == null:
		return ""
	var candidates: Array[String] = [clip]
	if clip.contains(" "):
		candidates.append(clip.replace(" ", "_"))
		candidates.append(clip.replace(" ", "_").to_lower())
	elif clip.contains("_"):
		candidates.append(clip.replace("_", " "))
		candidates.append(clip.replace("_", " ").to_lower())
	var normalized_clip := clip.to_lower()
	if not candidates.has(normalized_clip):
		candidates.append(normalized_clip)
	for candidate_name in candidates:
		var central_clip := candidate_name if candidate_name.begins_with("central/") else "central/%s" % candidate_name
		if _animation_player.has_animation(StringName(central_clip)):
			return central_clip
	for candidate_name in candidates:
		for candidate in _animation_player.get_animation_list():
			if str(candidate).to_lower() == candidate_name.to_lower() or str(candidate).to_lower().ends_with("/" + candidate_name.to_lower()):
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
	if animation_controller == null:
		return
	var states: Dictionary = _manifest.get("presentation_states", {})
	if states.has(state_name):
		var clips: Array = states[state_name]
		if not clips.is_empty():
			var resolved := _resolve_animation(str(clips[0]))
			var animation := _animation_player.get_animation(resolved) if not resolved.is_empty() else null
			var one_shot := animation != null and animation.loop_mode == Animation.LOOP_NONE
			if animation_controller.play_state(state_name, resolved, one_shot):
				_current_clip = resolved
		return
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
	var semantic_action_id := str(profile.get("semantic_action_id", ""))
	if semantic_action_id == "action:melee.unarmed_punch":
		clip = "boxing"
	elif semantic_action_id == "action:melee.sword_slash":
		clip = "sword attack"
	var native_clip := _resolve_package_animation(clip)
	var accepted := false
	if not native_clip.is_empty() and animation_controller != null:
		accepted = animation_controller.play_action(native_clip, _state_name_for_clip(native_clip))
		if accepted:
			_current_clip = str(animation_controller.get_current_clip_name())
	return {"accepted": accepted, "played_clip": _current_clip if accepted else "", "semantic_action_id": str(profile.get("semantic_action_id", ""))}


func _resolve_package_animation(clip: String) -> String:
	if _animation_player == null or clip.is_empty():
		return ""
	for candidate in _animation_player.get_animation_list():
		var path := str(candidate)
		if path.begins_with("central/"):
			continue
		if path.to_lower() == clip.to_lower() or path.to_lower().ends_with("/" + clip.to_lower()):
			return path
	return ""


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
	var physics_tick := Engine.get_physics_frames()
	if _root_motion_consumed_tick == physics_tick:
		return Vector3.ZERO
	_root_motion_consumed_tick = physics_tick
	_root_motion_consume_count += 1
	return root_motion_to_actor_local(root_motion_sampler.consume_delta())


func root_motion_to_actor_local(source_delta: Vector3) -> Vector3:
	var source: Node3D = _skeleton
	if source == null:
		return Vector3.ZERO
	var ancestor := get_parent()
	while ancestor != null and not (ancestor is CharacterBody3D):
		ancestor = ancestor.get_parent()
	if ancestor == null:
		return Vector3.ZERO
	# CharacterActor later converts this actor-local contribution into world space.
	# Include the model's import transform, scale and presentation calibration once.
	return (ancestor as CharacterBody3D).global_basis.inverse() * source.global_basis * source_delta


func get_root_motion_consume_count() -> int:
	return _root_motion_consume_count

func get_root_motion_policy() -> String:
	return str(_manifest.get("root_motion_profile", {}).get("policy", "hold"))


func reset_root_motion() -> void:
	if root_motion_sampler != null:
		root_motion_sampler.reset()
	_root_motion_consumed_tick = -1
	_root_motion_consume_count = 0

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
