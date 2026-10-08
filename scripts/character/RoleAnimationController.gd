extends Node

## External-controller style animation state machine adapter.
## Uses AnimationTree when one is present and falls back to AnimationPlayer so
## imported GLBs remain usable even when their package has no authored tree.

@export var cross_fade_seconds := 0.18
@export var default_playback_speed := 1.0

var animation_player: AnimationPlayer
var animation_tree: AnimationTree
var state_machine: AnimationNodeStateMachine
var current_state := "idle"
var current_clip := ""
var action_locked := false
var action_unlock_time := 0.0
var held_pose := false
var locomotion_state := "idle"
var pending_recovery_state := "idle"
var _last_presentation_signature := ""
var _states: Dictionary = {}
var state_clip_candidates: Dictionary = {}

const CANONICAL_CLIP_CANDIDATES := {
	"idle": ["idle"],
	"walk": ["walking2", "walking", "walk"],
	"run": ["running", "run"],
	"jump": ["jump", "air_jump"],
	"boxing": ["boxing", "fight_punch", "fight_kick"],
	"sword_attack": ["sword attack", "sword_attack"],
}

func bind(root: Node) -> void:
	animation_player = _find_descendant(root, "AnimationPlayer") as AnimationPlayer
	animation_tree = _find_descendant(root, "AnimationTree") as AnimationTree
	if animation_player == null:
		return
	_configure_loops()
	if animation_tree == null:
		animation_tree = AnimationTree.new()
		animation_tree.name = "AnimationTree"
		root.add_child(animation_tree)
	animation_tree.anim_player = animation_tree.get_path_to(animation_player)
	_build_state_machine()
	animation_tree.active = true
	var playback := animation_tree.get("parameters/playback") as AnimationNodeStateMachinePlayback
	if playback != null and _states.has("idle"):
		playback.start("idle")

func _process(_delta: float) -> void:
	if held_pose:
		return
	if action_locked and action_unlock_time != INF and Time.get_ticks_msec() / 1000.0 >= action_unlock_time:
		action_locked = false
		action_unlock_time = 0.0
		recover_to_locomotion(pending_recovery_state)

func apply_presentation_state(state: Dictionary) -> Dictionary:
	if animation_player == null or state_machine == null:
		return {"accepted": false, "state": "idle", "reason": "animation_binding_missing"}
	var gait := str(state.get("locomotion_intent", state.get("gait", "idle")))
	if gait not in ["idle", "walk", "run", "jump"]:
		gait = "idle"
	var action_id := str(state.get("action_id", ""))
	var signature := "%s|%s|%s|%s" % [gait, action_id, str(state.get("guard_hold", false)), str(state.get("cancel", false))]
	if signature == _last_presentation_signature and not bool(state.get("cancel", false)):
		return {"accepted": true, "state": current_state, "clip_ref": current_clip, "action_locked": action_locked, "reason": "unchanged"}
	_last_presentation_signature = signature
	if bool(state.get("cancel", false)):
		cancel_action()
		recover_to_locomotion(gait)
		return {"accepted": true, "state": current_state, "clip_ref": current_clip, "action_locked": action_locked, "reason": "cancelled"}
	if bool(state.get("guard_hold", false)):
		var held := hold_state("boxing", "", float(state.get("hold_position", 0.34)))
		return {"accepted": held, "state": current_state if held else "idle", "clip_ref": current_clip if held else "", "action_locked": action_locked, "reason": "guard_hold" if held else "guard_clip_missing"}
	if action_id in ["boxing", "action:melee.unarmed_punch"]:
		pending_recovery_state = gait
		var boxed := play_action("boxing", "boxing")
		return {"accepted": boxed, "state": current_state if boxed else "idle", "clip_ref": current_clip if boxed else "", "action_locked": action_locked, "reason": "action" if boxed else "action_clip_missing"}
	if action_id in ["sword_attack", "action:melee.sword_slash"]:
		pending_recovery_state = gait
		var sword := play_action("sword_attack", "sword_attack")
		return {"accepted": sword, "state": current_state if sword else "idle", "clip_ref": current_clip if sword else "", "action_locked": action_locked, "reason": "action" if sword else "action_clip_missing"}
	pending_recovery_state = gait
	var locomotion_ok := recover_to_locomotion(gait)
	return {"accepted": locomotion_ok, "state": current_state if locomotion_ok else "idle", "clip_ref": current_clip if locomotion_ok else "", "action_locked": action_locked, "reason": "locomotion" if locomotion_ok else "locomotion_clip_missing"}

func cancel_action() -> void:
	action_locked = false
	action_unlock_time = 0.0
	release_hold()

func recover_to_locomotion(state_name: String = "idle") -> bool:
	var normalized := state_name if state_name in ["idle", "walk", "run", "jump"] else "idle"
	locomotion_state = normalized
	return play_state(normalized, "", false)

func play_state(state_name: String, clip_ref: String = "", one_shot: bool = false, speed: float = 1.0) -> bool:
	if action_locked and not one_shot:
		return false
	if held_pose:
		release_hold()
	var clip := _resolve_clip(clip_ref if not clip_ref.is_empty() else state_name)
	if clip.is_empty() or not _states.has(state_name):
		return false
	var playback_speed := speed if abs(speed) > 0.001 else default_playback_speed
	if not one_shot and not held_pose and current_state == state_name and current_clip == clip:
		return true
	current_state = state_name
	current_clip = clip
	if not one_shot and state_name in ["idle", "walk", "run", "jump"]:
		locomotion_state = state_name
	if animation_tree != null and state_machine != null:
		var playback := animation_tree.get("parameters/playback") as AnimationNodeStateMachinePlayback
		if playback != null:
			playback.travel(state_name)
			animation_tree.advance(0.0)
	else:
		animation_player.play(clip, cross_fade_seconds, playback_speed, false)
	if one_shot:
		var animation := animation_player.get_animation(clip)
		var duration := animation.length if animation != null else 0.1
		action_locked = true
		action_unlock_time = Time.get_ticks_msec() / 1000.0 + max(duration / max(abs(playback_speed), 0.01), 0.1)
		if animation_tree != null:
			animation_tree.advance(0.0)
	return true

func play_action(clip_ref: String, state_name: String = "action") -> bool:
	var resolved_state := state_name_for_clip(clip_ref)
	if state_name != "action" and _states.has(state_name):
		resolved_state = state_name
	return play_state(resolved_state, clip_ref, true, 1.0)

func hold_state(state_name: String, clip_ref: String = "", normalized_position: float = 0.34) -> bool:
	"""Enter a state through AnimationTree and hold its pose at a normalized frame."""
	var accepted := play_state(state_name, clip_ref, false, 1.0)
	if not accepted or animation_player == null:
		return false
	var clip := current_clip
	var animation := animation_player.get_animation(clip)
	if animation == null:
		return false
	animation_player.seek(clamp(normalized_position, 0.0, 1.0) * animation.length, true)
	animation_player.set_speed_scale(0.0)
	held_pose = true
	action_locked = true
	action_unlock_time = INF
	return true

func release_hold() -> void:
	held_pose = false
	action_locked = false
	action_unlock_time = 0.0
	if animation_player != null:
		animation_player.set_speed_scale(default_playback_speed)

func restore() -> void:
	cancel_action()
	pending_recovery_state = "idle"
	recover_to_locomotion("idle")
	if animation_player != null:
		animation_player.set_speed_scale(default_playback_speed)

func is_locked() -> bool:
	return action_locked

func get_current_clip_name() -> String:
	return current_clip

func is_animation_tree_active() -> bool:
	return animation_tree != null and animation_tree.active and state_machine != null

func get_animation_tree_path() -> NodePath:
	return animation_tree.get_path_to(animation_player) if animation_tree != null and animation_player != null else NodePath()

func has_valid_animation_player_binding() -> bool:
	return is_animation_tree_active() and animation_tree.anim_player == get_animation_tree_path()

func get_playback_state() -> String:
	if animation_tree == null:
		return ""
	var playback := animation_tree.get("parameters/playback") as AnimationNodeStateMachinePlayback
	return playback.get_current_node() if playback != null else ""

func get_available_states() -> PackedStringArray:
	var result := PackedStringArray()
	for state_name in _states.keys():
		result.append(str(state_name))
	return result

func get_available_clips() -> PackedStringArray:
	var result := PackedStringArray()
	for clip_ref in _states.values():
		if not result.has(str(clip_ref)):
			result.append(str(clip_ref))
	return result

func state_name_for_clip(clip_ref: String) -> String:
	var resolved := _resolve_clip(clip_ref)
	if resolved.is_empty():
		resolved = clip_ref
	for state_name in _states.keys():
		if str(_states[state_name]).to_lower() == resolved.to_lower():
			return str(state_name)
	var clip_name := resolved.get_file().to_lower()
	for state_name in CANONICAL_CLIP_CANDIDATES:
		for candidate in CANONICAL_CLIP_CANDIDATES[state_name]:
			if clip_name == str(candidate).to_lower():
				return state_name
	return _normalize_state_name(resolved)

func _configure_loops() -> void:
	if not state_clip_candidates.is_empty():
		return
	for library_name in animation_player.get_animation_library_list():
		var library := animation_player.get_animation_library(library_name)
		for animation_name in library.get_animation_list():
			var animation := library.get_animation(animation_name)
			if animation == null:
				continue
			var lower := str(animation_name).to_lower()
			if lower in ["idle", "walking2", "walking", "running", "walk", "run"]:
				animation.loop_mode = Animation.LOOP_LINEAR
			else:
				animation.loop_mode = Animation.LOOP_NONE

func _build_state_machine() -> void:
	state_machine = AnimationNodeStateMachine.new()
	_states.clear()
	var candidates := CANONICAL_CLIP_CANDIDATES if state_clip_candidates.is_empty() else state_clip_candidates
	for state_name in candidates:
		var clip := _resolve_clip_from_candidates(candidates[state_name])
		if clip.is_empty():
			continue
		var node := AnimationNodeAnimation.new()
		node.animation = clip
		state_machine.add_node(state_name, node)
		_states[state_name] = clip
	for from_state in _states.keys():
		for to_state in _states.keys():
			if from_state == to_state:
				continue
			var transition := AnimationNodeStateMachineTransition.new()
			transition.switch_mode = AnimationNodeStateMachineTransition.SWITCH_MODE_IMMEDIATE
			transition.advance_mode = AnimationNodeStateMachineTransition.ADVANCE_MODE_ENABLED
			transition.xfade_time = cross_fade_seconds
			state_machine.add_transition(from_state, to_state, transition)
	animation_tree.tree_root = state_machine

func _resolve_clip(state_or_clip: String) -> String:
	if _states.has(state_or_clip):
		return str(_states[state_or_clip])
	return _resolve_clip_from_candidates([state_or_clip])

func _resolve_clip_from_candidates(candidates: Array) -> String:
	if animation_player == null:
		return ""
	for candidate in candidates:
		var central_name := str(candidate)
		var central_names: Array[String] = [central_name]
		if central_name.contains(" "):
			central_names.append(central_name.replace(" ", "_"))
			central_names.append(central_name.replace(" ", "_").to_lower())
		elif central_name.contains("_"):
			central_names.append(central_name.replace("_", " "))
			central_names.append(central_name.replace("_", " ").to_lower())
		var normalized_central_name := central_name.to_lower()
		if not central_names.has(normalized_central_name):
			central_names.append(normalized_central_name)
		for candidate_variant in central_names:
			var central_candidate := candidate_variant if candidate_variant.begins_with("central/") else "central/%s" % candidate_variant
			if animation_player.has_animation(StringName(central_candidate)):
				return central_candidate
	for candidate in candidates:
		var candidate_name := str(candidate)
		var candidate_names: Array[String] = [candidate_name]
		if candidate_name.contains(" "):
			candidate_names.append(candidate_name.replace(" ", "_"))
			candidate_names.append(candidate_name.replace(" ", "_").to_lower())
		elif candidate_name.contains("_"):
			candidate_names.append(candidate_name.replace("_", " "))
			candidate_names.append(candidate_name.replace("_", " ").to_lower())
		var normalized_candidate_name := candidate_name.to_lower()
		if not candidate_names.has(normalized_candidate_name):
			candidate_names.append(normalized_candidate_name)
		for candidate_variant in candidate_names:
			for clip in animation_player.get_animation_list():
				if str(clip).to_lower() == candidate_variant.to_lower() or str(clip).to_lower().ends_with("/" + candidate_variant.to_lower()):
					return str(clip)
	return ""

func _normalize_state_name(clip_ref: String) -> String:
	var state := clip_ref.to_lower().strip_edges()
	state = state.replace("/", "_").replace(" ", "_").replace("-", "_")
	while state.contains("__"):
		state = state.replace("__", "_")
	while state.begins_with("_"):
		state = state.substr(1)
	while state.ends_with("_"):
		state = state.substr(0, state.length() - 1)
	return state

func _find_descendant(node: Node, type_name: String) -> Node:
	for child in node.get_children():
		if child.is_class(type_name):
			return child
		var found := _find_descendant(child, type_name)
		if found != null:
			return found
	return null
