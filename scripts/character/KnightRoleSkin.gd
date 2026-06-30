extends Node3D

const CharacterPresentationInputRef = preload("res://scripts/character/CharacterPresentationInput.gd")

@export var locomotion_amplitude_scale := 0.75

# AnimationTree integration note:
# `AnimationNodeStateMachinePlayback` and `animation_state_playback.travel(...)`
# are intentionally deferred until a separate Godot-runtime-verified change.

const CLIP_MAP := {
	"idle": "idle_guard",
	"walk": "walk_guard",
	"run": "run_charge",
	"jump": "jump_command",
	"fall": "alert_recoil",
	"guard": "idle_guard",
	"observe": "observe_watch",
	"speak": "speak_order",
	"inspect": "inspect_relic",
	"alert": "alert_recoil",
	"greeting_nod": "observe_watch",
	"ambient": "ambient_patrol",
	"sword_swing": "idle_guard",
	"shield_block": "idle_guard",
}

const LOOPING_CLIPS := {
	"ambient_patrol": true,
	"idle_guard": true,
	"walk_guard": true,
	"run_charge": true,
	"observe_watch": true,
}

const ONE_SHOT_CLIPS := {
	"speak_order": true,
	"inspect_relic": true,
	"alert_recoil": true,
	"jump_command": true,
}

const MOTION_PROFILE := {
	"default": {
		"playback_speed": 1.0,
		"distance_scale": 1.0,
	},
	"amble": {
		"playback_speed": 0.68,
		"distance_scale": 1.05,
	},
	"walk": {
		"playback_speed": 1.02,
		"distance_scale": 2.75,
	},
	"brisk_walk": {
		"playback_speed": 1.24,
		"distance_scale": 3.55,
	},
	"run": {
		"playback_speed": 1.22,
		"distance_scale": 4.6,
	},
	"crouch_idle": {
		"playback_speed": 0.82,
		"distance_scale": 1.0,
	},
	"crouch_walk": {
		"playback_speed": 0.58,
		"distance_scale": 1.45,
	},
	"jump_two_foot": {
		"playback_speed": 1.0,
		"distance_scale": 1.0,
	},
	"jump_single_leg": {
		"playback_speed": 1.18,
		"distance_scale": 1.12,
	},
}

const REFINEMENT_PROFILE := {
	"amble": {
		"hips_pitch": 0.12,
		"hips_roll": 0.08,
		"hips_yaw": 0.06,
		"hips_bob": 0.018,
		"hips_shift": 0.008,
		"spine_yaw": 0.07,
		"spine_roll": 0.04,
		"spine_pitch": 0.03,
		"thigh_lift": 0.22,
		"thigh_back": 0.16,
		"thigh_splay": 0.05,
		"shin_bend": 0.42,
		"toe_lift": 0.22,
		"toe_drop": 0.08,
		"arm_swing": 0.18,
		"arm_roll": 0.05,
		"elbow_bend": 0.10,
		"head_nod": 0.05,
		"head_yaw": 0.03,
		"neck_roll": 0.02,
		"hand_swing": 0.08,
		"hand_roll": 0.10,
	},
	"walk": {
		"hips_pitch": 0.26,
		"hips_roll": 0.16,
		"hips_yaw": 0.12,
		"hips_bob": 0.042,
		"hips_shift": 0.02,
		"spine_yaw": 0.15,
		"spine_roll": 0.08,
		"spine_pitch": 0.08,
		"thigh_lift": 0.72,
		"thigh_back": 0.38,
		"thigh_splay": 0.12,
		"shin_bend": 1.34,
		"toe_lift": 0.62,
		"toe_drop": 0.22,
		"arm_swing": 0.56,
		"arm_roll": 0.18,
		"elbow_bend": 0.28,
		"head_nod": 0.08,
		"head_yaw": 0.04,
		"neck_roll": 0.03,
		"hand_swing": 0.16,
		"hand_roll": 0.18,
	},
	"brisk_walk": {
		"hips_pitch": 0.32,
		"hips_roll": 0.18,
		"hips_yaw": 0.16,
		"hips_bob": 0.05,
		"hips_shift": 0.024,
		"spine_yaw": 0.18,
		"spine_roll": 0.1,
		"spine_pitch": 0.1,
		"thigh_lift": 0.86,
		"thigh_back": 0.48,
		"thigh_splay": 0.14,
		"shin_bend": 1.48,
		"toe_lift": 0.7,
		"toe_drop": 0.24,
		"arm_swing": 0.66,
		"arm_roll": 0.2,
		"elbow_bend": 0.32,
		"head_nod": 0.1,
		"head_yaw": 0.05,
		"neck_roll": 0.04,
		"hand_swing": 0.2,
		"hand_roll": 0.22,
	},
	"run": {
		"hips_pitch": 0.28,
		"hips_roll": 0.12,
		"hips_yaw": 0.16,
		"hips_bob": 0.032,
		"hips_shift": 0.016,
		"spine_yaw": 0.16,
		"spine_roll": 0.08,
		"spine_pitch": 0.06,
		"thigh_lift": 0.46,
		"thigh_back": 0.32,
		"thigh_splay": 0.1,
		"shin_bend": 0.92,
		"toe_lift": 0.38,
		"toe_drop": 0.14,
		"arm_swing": 0.62,
		"arm_roll": 0.18,
		"elbow_bend": 0.3,
		"head_nod": 0.07,
		"head_yaw": 0.04,
		"neck_roll": 0.03,
		"hand_swing": 0.18,
		"hand_roll": 0.2,
	},
	"crouch_walk": {
		"hips_pitch": 0.12,
		"hips_roll": 0.06,
		"hips_yaw": 0.06,
		"hips_bob": 0.016,
		"hips_shift": 0.01,
		"spine_yaw": 0.06,
		"spine_roll": 0.04,
		"spine_pitch": 0.06,
		"thigh_lift": 0.24,
		"thigh_back": 0.16,
		"thigh_splay": 0.06,
		"shin_bend": 0.52,
		"toe_lift": 0.22,
		"toe_drop": 0.08,
		"arm_swing": 0.16,
		"arm_roll": 0.05,
		"elbow_bend": 0.1,
		"head_nod": 0.03,
		"head_yaw": 0.02,
		"neck_roll": 0.02,
		"hand_swing": 0.06,
		"hand_roll": 0.08,
	},
}

const VARIANT_CONFIG := {
	"char_a": {
		"cape": Color(0.56, 0.14, 0.12, 1.0),
		"cloth": Color(0.68, 0.18, 0.16, 1.0),
		"hood": Color(0.24, 0.08, 0.07, 1.0),
		"focus": Color(0.96, 0.82, 0.34, 1.0),
		"scale": Vector3(1.01, 1.01, 1.01),
		"hide_hood": false,
		"shield_in_hand": true,
	},
	"char_b": {
		"cape": Color(0.18, 0.26, 0.20, 1.0),
		"cloth": Color(0.24, 0.34, 0.26, 1.0),
		"hood": Color(0.14, 0.18, 0.14, 1.0),
		"focus": Color(0.64, 0.9, 0.72, 1.0),
		"scale": Vector3(0.99, 0.99, 0.99),
		"hide_hood": false,
		"shield_in_hand": false,
	},
	"char_c": {
		"cape": Color(0.14, 0.26, 0.54, 1.0),
		"cloth": Color(0.18, 0.32, 0.68, 1.0),
		"hood": Color(0.11, 0.16, 0.28, 1.0),
		"focus": Color(0.46, 0.8, 1.0, 1.0),
		"scale": Vector3(1.03, 1.03, 1.03),
		"hide_hood": true,
		"shield_in_hand": true,
	},
}

@onready var knight_scene: Node3D = $KnightScene
@onready var animation_player: AnimationPlayer = $KnightScene/AnimationPlayer
@onready var skeleton: Skeleton3D = $KnightScene/KnightArmature/Skeleton3D
@onready var combat_modifier: SkeletonModifier3D = $KnightScene/KnightArmature/Skeleton3D/KnightCombatModifier
var hips_bone := -1
var neck_bone := -1
var head_bone := -1
var spine_lower_bone := -1
var spine_upper_bone := -1
var left_thigh_bone := -1
var right_thigh_bone := -1
var left_shin_bone := -1
var right_shin_bone := -1
var left_upper_arm_bone := -1
var right_upper_arm_bone := -1
var left_forearm_bone := -1
var right_forearm_bone := -1
var left_hand_bone := -1
var right_hand_bone := -1
var left_foot_bone := -1
var right_foot_bone := -1
var base_bone_rotations: Dictionary = {}
var base_bone_positions: Dictionary = {}
var role_actor_id := "char_a"
var current_clip := ""
var focus_overlay: StandardMaterial3D
var base_knight_scene_position := Vector3.ZERO
var base_knight_scene_rotation := Vector3.ZERO
var root_motion_rest_position := Vector3.ZERO
var last_root_motion_sample := Vector3.ZERO
var last_root_motion_time := 0.0
var pending_root_motion := Vector3.ZERO
var root_motion_initialized := false
var current_root_motion_track_index := -1
var current_motion_profile := "default"
var current_distance_scale := 1.0
var sword_swing_timer := 0.0
var shield_block_timer := 0.0
var move_x := 0.0
var move_y := 0.0
var speed := 0.0
var presentation_gait := "walk"
var current_presentation_contract: Dictionary = {}
var last_stage2_role_state := ""
var last_stage2_motion_profile := ""
func _ready() -> void:
	_configure_animation_loops()
	_cache_pose_refinement_bones()
	base_knight_scene_position = knight_scene.position
	base_knight_scene_rotation = knight_scene.rotation
	_configure_combat_modifier()
	configure_role(role_actor_id)
	set_motion_profile("guard", "default")

func _process(delta: float) -> void:
	_capture_root_motion()
	_apply_locomotion_pose_refinement()
	_update_action_pose_overlays(delta)
	_sync_combat_modifier()

func configure_role(actor_name: String) -> void:
	role_actor_id = actor_name
	if knight_scene == null:
		return
	var config: Dictionary = VARIANT_CONFIG.get(role_actor_id, VARIANT_CONFIG["char_a"])
	knight_scene.scale = config.get("scale", Vector3.ONE)
	_apply_variant_tint(["cape"], config.get("cape", Color.WHITE), 0.32)
	_apply_variant_tint(["cloth", "skirt_inner"], config.get("cloth", Color.WHITE), 0.3)
	_apply_variant_tint(["hood_outer", "hood_inner", "gabardine"], config.get("hood", Color.WHITE), 0.22)
	_set_optional_node_visible("hood_outer", not bool(config.get("hide_hood", false)))
	_set_optional_node_visible("shield_in_hand", bool(config.get("shield_in_hand", true)))
	_set_optional_node_visible("shield", not bool(config.get("shield_in_hand", true)))
	_rebuild_focus_overlay(config.get("focus", Color(0.95, 0.84, 0.32, 1.0)))

func set_state(state_name: String) -> void:
	if animation_player == null:
		return
	_trigger_action_pose_overlay(state_name)
	var clip_name := str(CLIP_MAP.get(state_name, state_name))
	if not animation_player.has_animation(clip_name):
		clip_name = "idle_guard"
	var should_restart := ONE_SHOT_CLIPS.has(clip_name)
	if current_clip == clip_name and animation_player.is_playing() and not should_restart:
		return
	var animation: Animation = animation_player.get_animation(clip_name)
	if animation:
		animation.loop_mode = Animation.LOOP_LINEAR if LOOPING_CLIPS.has(clip_name) else Animation.LOOP_NONE
		current_root_motion_track_index = _resolve_root_motion_track(animation)
	else:
		current_root_motion_track_index = -1
	animation_player.play(clip_name, 0.16)
	if should_restart:
		animation_player.seek(0.0, true)
	current_clip = clip_name
	_reset_root_motion_tracking()
	_apply_motion_profile("default")

func set_motion_profile(state_name: String, profile_name: String) -> void:
	set_state(state_name)
	_apply_motion_profile(profile_name)

func set_focus_highlight(is_focused: bool) -> void:
	if knight_scene == null:
		return
	for mesh_name: String in [
		"helmet",
		"cape",
		"hood_outer",
		"shield_in_hand",
		"sword_in_hand",
	]:
		var mesh := _find_mesh(mesh_name)
		if mesh:
			mesh.material_overlay = focus_overlay if is_focused else null

func apply_presentation_input(next_input: Dictionary) -> void:
	current_presentation_contract = CharacterPresentationInputRef.normalize(next_input)
	var move_local_actual := CharacterPresentationInputRef.get_motion_move_local_actual(current_presentation_contract)
	var velocity_world := CharacterPresentationInputRef.get_motion_velocity_world(current_presentation_contract)
	var focus_target_id := CharacterPresentationInputRef.get_focus_target_id(current_presentation_contract)
	var presentation_gait_actual := CharacterPresentationInputRef.get_motion_gait_actual(current_presentation_contract)
	var requested_action := CharacterPresentationInputRef.get_requested_action(current_presentation_contract)
	var active_command_type := CharacterPresentationInputRef.get_active_command_type(current_presentation_contract)
	var equipment_gait_hint := CharacterPresentationInputRef.get_equipment_gait_hint(current_presentation_contract)
	move_x = float(move_local_actual.x)
	move_y = float(move_local_actual.y)
	speed = float(velocity_world.length())
	set_focus_highlight(not focus_target_id.is_empty())
	presentation_gait = presentation_gait_actual
	if not requested_action.is_empty():
		presentation_gait = CharacterPresentationInputRef.get_action_gait_hint(current_presentation_contract, presentation_gait)
	elif not active_command_type.is_empty():
		presentation_gait = CharacterPresentationInputRef.get_action_gait_hint(current_presentation_contract, presentation_gait)
	elif not equipment_gait_hint.is_empty():
		presentation_gait = equipment_gait_hint
	presentation_gait = _resolve_stage2_presentation_gait(current_presentation_contract)
	var stage2_role_state := _resolve_stage2_contract_role_state(current_presentation_contract)
	var stage2_motion_profile := _resolve_stage2_motion_profile(presentation_gait)
	_apply_stage2_contract_expression(stage2_role_state, stage2_motion_profile)

func _resolve_stage2_presentation_gait(contract: Dictionary) -> String:
	var presentation_gait := CharacterPresentationInputRef.get_motion_gait_actual(contract)
	var requested_action := CharacterPresentationInputRef.get_requested_action(contract)
	if not requested_action.is_empty():
		return CharacterPresentationInputRef.get_action_gait_hint(contract, presentation_gait)
	var active_command_type := CharacterPresentationInputRef.get_active_command_type(contract)
	if not active_command_type.is_empty():
		return CharacterPresentationInputRef.get_action_gait_hint(contract, presentation_gait)
	var equipment_gait_hint := CharacterPresentationInputRef.get_equipment_gait_hint(contract)
	if not equipment_gait_hint.is_empty():
		return equipment_gait_hint
	return presentation_gait

func _resolve_stage2_contract_role_state(contract: Dictionary) -> String:
	var contact_phase := CharacterPresentationInputRef.get_contact_phase(contract)
	if contact_phase == "greeting":
		return "greeting_nod"
	var requested_action := CharacterPresentationInputRef.get_requested_action(contract)
	if not requested_action.is_empty():
		return _map_stage2_action_to_role_state(requested_action)
	var active_command_type := CharacterPresentationInputRef.get_active_command_type(contract)
	if active_command_type.is_empty():
		return ""
	return _map_stage2_action_to_role_state(active_command_type)

func _map_stage2_action_to_role_state(action_name: String) -> String:
	match action_name:
		"dialogue", "talk", "speak", "brief_dialogue_response", "speak_public", "speak_private", "share_info", "withhold":
			return "speak"
		"inspect", "interact", "inspect_object":
			return "inspect"
		"observe", "focus", "observe_target":
			return "observe"
		"alert", "attention_shift":
			return "alert"
		"approach", "follow_target", "seek_private_distance", "withdraw", "break_contact", "reposition_step":
			return "walk"
		"jump", "sword_swing", "shield_block":
			return action_name
		_:
			return ""

func _resolve_stage2_motion_profile(presentation_gait_name: String) -> String:
	match presentation_gait_name:
		"amble":
			return "amble"
		"walk":
			return "walk"
		"brisk_walk":
			return "brisk_walk"
		"run":
			return "run"
		"crouch_idle":
			return "crouch_idle"
		"crouch_walk":
			return "crouch_walk"
		"jump_single_leg":
			return "jump_single_leg"
		"jump_two_foot":
			return "jump_two_foot"
		_:
			return "default"

func _apply_stage2_contract_expression(role_state_name: String, motion_profile_name: String) -> void:
	if role_state_name.is_empty():
		last_stage2_role_state = ""
		last_stage2_motion_profile = ""
		return
	if role_state_name != last_stage2_role_state:
		last_stage2_role_state = role_state_name
		last_stage2_motion_profile = motion_profile_name
		set_motion_profile(role_state_name, motion_profile_name)
		return
	if motion_profile_name == last_stage2_motion_profile:
		return
	last_stage2_motion_profile = motion_profile_name
	_apply_motion_profile(motion_profile_name)

func _configure_animation_loops() -> void:
	if animation_player == null:
		return
	for clip_name: String in animation_player.get_animation_list():
		var animation: Animation = animation_player.get_animation(clip_name)
		if animation == null:
			continue
		animation.loop_mode = Animation.LOOP_LINEAR if LOOPING_CLIPS.has(clip_name) else Animation.LOOP_NONE

func _apply_variant_tint(mesh_names: Array[String], tint: Color, blend: float) -> void:
	for mesh_name: String in mesh_names:
		var mesh := _find_mesh(mesh_name)
		if mesh == null or mesh.mesh == null:
			continue
		for surface_idx: int in range(mesh.mesh.get_surface_count()):
			var base_material: Material = mesh.get_active_material(surface_idx)
			if base_material == null:
				base_material = mesh.mesh.surface_get_material(surface_idx)
			if base_material == null:
				continue
			var duplicated := base_material.duplicate() as StandardMaterial3D
			if duplicated == null:
				continue
			duplicated.albedo_color = duplicated.albedo_color.lerp(tint, blend)
			mesh.set_surface_override_material(surface_idx, duplicated)

func consume_root_motion_delta() -> Vector3:
	var delta := pending_root_motion * current_distance_scale
	pending_root_motion = Vector3.ZERO
	return delta

func reset_root_motion() -> void:
	pending_root_motion = Vector3.ZERO
	_reset_root_motion_tracking()

func _set_optional_node_visible(node_name: String, is_visible: bool) -> void:
	var target := knight_scene.find_child(node_name, true, false)
	if target is Node3D:
		(target as Node3D).visible = is_visible

func _rebuild_focus_overlay(accent_color: Color) -> void:
	focus_overlay = StandardMaterial3D.new()
	focus_overlay.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	focus_overlay.albedo_color = Color(accent_color.r, accent_color.g, accent_color.b, 0.22)
	focus_overlay.emission_enabled = true
	focus_overlay.emission = accent_color
	focus_overlay.emission_energy_multiplier = 0.9
	focus_overlay.shading_mode = BaseMaterial3D.SHADING_MODE_PER_PIXEL

func _find_mesh(node_name: String) -> MeshInstance3D:
	var target := knight_scene.find_child(node_name, true, false)
	if target is MeshInstance3D:
		return target as MeshInstance3D
	return null

func _capture_root_motion() -> void:
	if animation_player == null or current_clip.is_empty():
		return
	if not animation_player.is_playing():
		root_motion_initialized = false
		last_root_motion_sample = Vector3.ZERO
		last_root_motion_time = 0.0
		return

	var animation: Animation = animation_player.get_animation(current_clip)
	if animation == null or current_root_motion_track_index < 0:
		root_motion_initialized = false
		return

	var current_time: float = animation_player.current_animation_position
	var current_sample: Vector3 = animation.position_track_interpolate(current_root_motion_track_index, current_time)
	if current_time < last_root_motion_time:
		root_motion_initialized = false
	if not root_motion_initialized:
		root_motion_rest_position = current_sample
		last_root_motion_sample = current_sample
		last_root_motion_time = current_time
		root_motion_initialized = true
		return

	var local_delta: Vector3 = current_sample - last_root_motion_sample
	pending_root_motion += local_delta
	last_root_motion_sample = current_sample
	last_root_motion_time = current_time

func _reset_root_motion_tracking() -> void:
	last_root_motion_sample = Vector3.ZERO
	root_motion_rest_position = Vector3.ZERO
	pending_root_motion = Vector3.ZERO
	last_root_motion_time = 0.0
	root_motion_initialized = false

func get_current_clip_name() -> String:
	return current_clip

func get_current_motion_profile_name() -> String:
	return current_motion_profile

func _resolve_root_motion_track(animation: Animation) -> int:
	var fallback_track := -1
	for track_idx: int in range(animation.get_track_count()):
		if animation.track_get_type(track_idx) != Animation.TYPE_POSITION_3D:
			continue
		var track_path := str(animation.track_get_path(track_idx))
		if track_path.contains("KnightArmature"):
			return track_idx
		if track_path.contains("Armature") or track_path.contains("Root"):
			fallback_track = track_idx
	return fallback_track

func _apply_motion_profile(profile_name: String) -> void:
	var profile: Dictionary = MOTION_PROFILE.get(profile_name, MOTION_PROFILE["default"])
	current_motion_profile = profile_name if MOTION_PROFILE.has(profile_name) else "default"
	current_distance_scale = float(profile.get("distance_scale", 1.0))
	if animation_player:
		animation_player.speed_scale = float(profile.get("playback_speed", 1.0))

func _cache_pose_refinement_bones() -> void:
	if skeleton == null:
		return
	hips_bone = _find_first_bone(["DEF-hips", "hips", "mixamorig_Hips", "Bip001 Pelvis"])
	neck_bone = _find_first_bone(["DEF-neck", "neck", "mixamorig_Neck", "Bip001 Neck"])
	head_bone = _find_first_bone(["DEF-head", "head", "mixamorig_Head", "Bip001 Head"])
	spine_lower_bone = _find_first_bone(["DEF-spine", "spine", "mixamorig_Spine", "Bip001 Spine"])
	spine_upper_bone = _find_first_bone(["DEF-spine.001", "DEF-spine.002", "spine.001", "spine.002", "mixamorig_Spine1", "mixamorig_Spine2", "Bip001 Spine1", "Bip001 Spine2"])
	left_thigh_bone = _find_first_bone(["DEF-thigh.L", "thigh.L", "mixamorig_LeftUpLeg", "Bip001 L Thigh"])
	right_thigh_bone = _find_first_bone(["DEF-thigh.R", "thigh.R", "mixamorig_RightUpLeg", "Bip001 R Thigh"])
	left_shin_bone = _find_first_bone(["DEF-shin.L", "shin.L", "mixamorig_LeftLeg", "Bip001 L Calf"])
	right_shin_bone = _find_first_bone(["DEF-shin.R", "shin.R", "mixamorig_RightLeg", "Bip001 R Calf"])
	left_upper_arm_bone = _find_first_bone(["DEF-upper_arm.L", "upper_arm.L", "mixamorig_LeftArm", "Bip001 L UpperArm"])
	right_upper_arm_bone = _find_first_bone(["DEF-upper_arm.R", "upper_arm.R", "mixamorig_RightArm", "Bip001 R UpperArm"])
	left_forearm_bone = _find_first_bone(["DEF-forearm.L", "forearm.L", "mixamorig_LeftForeArm", "Bip001 L Forearm"])
	right_forearm_bone = _find_first_bone(["DEF-forearm.R", "forearm.R", "mixamorig_RightForeArm", "Bip001 R Forearm"])
	left_hand_bone = _find_first_bone(["DEF-hand.L", "hand.L", "mixamorig_LeftHand", "Bip001 L Hand"])
	right_hand_bone = _find_first_bone(["DEF-hand.R", "hand.R", "mixamorig_RightHand", "Bip001 R Hand"])
	left_foot_bone = _find_first_bone(["DEF-foot.L", "foot.L", "mixamorig_LeftFoot", "Bip001 L Foot"])
	right_foot_bone = _find_first_bone(["DEF-foot.R", "foot.R", "mixamorig_RightFoot", "Bip001 R Foot"])
	for bone_idx in [hips_bone, neck_bone, head_bone, spine_lower_bone, spine_upper_bone, left_thigh_bone, right_thigh_bone, left_shin_bone, right_shin_bone, left_upper_arm_bone, right_upper_arm_bone, left_forearm_bone, right_forearm_bone, left_hand_bone, right_hand_bone, left_foot_bone, right_foot_bone]:
		if bone_idx >= 0:
			base_bone_rotations[bone_idx] = skeleton.get_bone_pose_rotation(bone_idx)
			base_bone_positions[bone_idx] = skeleton.get_bone_pose_position(bone_idx)
	_configure_combat_modifier()

func _configure_combat_modifier() -> void:
	if combat_modifier == null or not combat_modifier.has_method("configure_bones"):
		return
	combat_modifier.call(
		"configure_bones",
		{
			"right_upper_arm_bone": right_upper_arm_bone,
			"right_forearm_bone": right_forearm_bone,
			"right_hand_bone": right_hand_bone,
			"left_upper_arm_bone": left_upper_arm_bone,
			"left_forearm_bone": left_forearm_bone,
			"left_hand_bone": left_hand_bone,
			"spine_upper_bone": spine_upper_bone,
		}
	)

func _find_first_bone(candidates: Array[String]) -> int:
	if skeleton == null:
		return -1
	for bone_name in candidates:
		var idx := skeleton.find_bone(bone_name)
		if idx >= 0:
			return idx
	return -1

func _apply_locomotion_pose_refinement() -> void:
	if skeleton == null:
		return
	var gait_strength := _current_gait_refinement_strength()
	if gait_strength <= 0.001:
		_restore_knight_scene_pose()
		_restore_pose_refinement_bones()
		return
	var refinement := _get_current_refinement_profile()
	var phase := animation_player.current_animation_position * animation_player.speed_scale * 6.0
	var left_phase: float = sin(phase)
	var right_phase: float = sin(phase + PI)
	_apply_knight_scene_pose(left_phase, refinement)
	_apply_hips_pose(left_phase, refinement)
	_apply_spine_pose(left_phase, refinement)
	_apply_head_pose(left_phase, refinement)
	_apply_leg_pose(left_thigh_bone, left_shin_bone, left_foot_bone, left_phase, refinement)
	_apply_leg_pose(right_thigh_bone, right_shin_bone, right_foot_bone, right_phase, refinement)
	_apply_arm_pose(left_upper_arm_bone, left_forearm_bone, right_phase, refinement)
	_apply_arm_pose(right_upper_arm_bone, right_forearm_bone, left_phase, refinement)
	_apply_hand_pose(left_hand_bone, right_phase, refinement)
	_apply_hand_pose(right_hand_bone, left_phase, refinement)

func _current_gait_refinement_strength() -> float:
	if sword_swing_timer > 0.0 or shield_block_timer > 0.0:
		return 0.0
	match current_motion_profile:
		"amble":
			return 0.18
		"walk":
			return 0.32
		"brisk_walk":
			return 0.4
		"run":
			return 0.3
		"crouch_walk":
			return 0.18
		_:
			return 0.0

func _get_current_refinement_profile() -> Dictionary:
	return REFINEMENT_PROFILE.get(current_motion_profile, REFINEMENT_PROFILE["walk"])

func _apply_knight_scene_pose(phase_value: float, profile: Dictionary) -> void:
	if knight_scene == null:
		return
	var crouch_active: bool = current_motion_profile == "crouch_walk" or current_motion_profile == "crouch_idle"
	var stance_drop: float = -0.18 if crouch_active else 0.0
	var stride_abs: float = abs(phase_value)
	var strafe_shift: float = clamp(move_x, -1.0, 1.0) * _scaled_refinement_value(0.028)
	var backpedal_pitch: float = max(-move_y, 0.0) * _scaled_refinement_value(0.12)
	knight_scene.position = base_knight_scene_position + Vector3(strafe_shift, stance_drop + stride_abs * _scaled_refinement_value(float(profile.get("hips_bob", 0.0)) * 0.9), 0.0)
	var crouch_pitch: float = 0.16 if crouch_active else 0.0
	knight_scene.rotation = base_knight_scene_rotation + Vector3(crouch_pitch + backpedal_pitch, 0.0, -strafe_shift * 2.6)

func _apply_hips_pose(phase_value: float, profile: Dictionary) -> void:
	if hips_bone < 0 or not base_bone_rotations.has(hips_bone):
		return
	var hips_base: Quaternion = base_bone_rotations[hips_bone]
	var hips_base_position: Vector3 = base_bone_positions.get(hips_bone, Vector3.ZERO)
	var hips_pitch: float = phase_value * _scaled_refinement_value(float(profile.get("hips_pitch", 0.0)))
	var hips_roll: float = phase_value * _scaled_refinement_value(float(profile.get("hips_roll", 0.0)))
	var hips_yaw: float = phase_value * _scaled_refinement_value(float(profile.get("hips_yaw", 0.0)))
	var hips_rot := Quaternion(Vector3.RIGHT, hips_pitch) * Quaternion(Vector3.BACK, hips_roll) * Quaternion(Vector3.UP, hips_yaw)
	skeleton.set_bone_pose_rotation(hips_bone, hips_base * hips_rot)
	var stride_abs: float = abs(phase_value)
	var hips_bob: float = stride_abs * _scaled_refinement_value(float(profile.get("hips_bob", 0.0)))
	var hips_shift: float = phase_value * _scaled_refinement_value(float(profile.get("hips_shift", 0.0)))
	skeleton.set_bone_pose_position(hips_bone, hips_base_position + Vector3(hips_shift, hips_bob, 0.0))

func _apply_spine_pose(phase_value: float, profile: Dictionary) -> void:
	if spine_lower_bone >= 0 and base_bone_rotations.has(spine_lower_bone):
		var lower_base: Quaternion = base_bone_rotations[spine_lower_bone]
		var lower_rot := Quaternion(Vector3.UP, -phase_value * _scaled_refinement_value(float(profile.get("spine_yaw", 0.0)))) * Quaternion(Vector3.BACK, -phase_value * _scaled_refinement_value(float(profile.get("spine_roll", 0.0))))
		skeleton.set_bone_pose_rotation(spine_lower_bone, lower_base * lower_rot)
	if spine_upper_bone >= 0 and base_bone_rotations.has(spine_upper_bone):
		var upper_base: Quaternion = base_bone_rotations[spine_upper_bone]
		var upper_rot := Quaternion(Vector3.UP, -phase_value * _scaled_refinement_value(float(profile.get("spine_yaw", 0.0)) * 1.25)) * Quaternion(Vector3.RIGHT, -abs(phase_value) * _scaled_refinement_value(float(profile.get("spine_pitch", 0.0))))
		skeleton.set_bone_pose_rotation(spine_upper_bone, upper_base * upper_rot)

func _apply_head_pose(phase_value: float, profile: Dictionary) -> void:
	if neck_bone >= 0 and base_bone_rotations.has(neck_bone):
		var neck_base: Quaternion = base_bone_rotations[neck_bone]
		var neck_rot := Quaternion(Vector3.BACK, -phase_value * _scaled_refinement_value(float(profile.get("neck_roll", 0.0))))
		skeleton.set_bone_pose_rotation(neck_bone, neck_base * neck_rot)
	if head_bone >= 0 and base_bone_rotations.has(head_bone):
		var head_base: Quaternion = base_bone_rotations[head_bone]
		var head_rot := Quaternion(Vector3.RIGHT, -abs(phase_value) * _scaled_refinement_value(float(profile.get("head_nod", 0.0)))) * Quaternion(Vector3.UP, -phase_value * _scaled_refinement_value(float(profile.get("head_yaw", 0.0))))
		skeleton.set_bone_pose_rotation(head_bone, head_base * head_rot)

func _apply_leg_pose(thigh_bone: int, shin_bone: int, foot_bone: int, phase_value: float, profile: Dictionary) -> void:
	if thigh_bone >= 0 and base_bone_rotations.has(thigh_bone):
		var thigh_base: Quaternion = base_bone_rotations[thigh_bone]
		var thigh_lift: float = max(phase_value, 0.0) * _scaled_refinement_value(float(profile.get("thigh_lift", 0.0)))
		var thigh_back: float = min(phase_value, 0.0) * _scaled_refinement_value(float(profile.get("thigh_back", 0.0)))
		var thigh_rot := Quaternion(Vector3.RIGHT, -(thigh_lift + thigh_back)) * Quaternion(Vector3.FORWARD, phase_value * _scaled_refinement_value(float(profile.get("thigh_splay", 0.0))))
		skeleton.set_bone_pose_rotation(thigh_bone, thigh_base * thigh_rot)
	if shin_bone >= 0 and base_bone_rotations.has(shin_bone):
		var shin_base: Quaternion = base_bone_rotations[shin_bone]
		var shin_bend: float = max(phase_value, 0.0) * _scaled_refinement_value(float(profile.get("shin_bend", 0.0)))
		var shin_rot := Quaternion(Vector3.RIGHT, shin_bend)
		skeleton.set_bone_pose_rotation(shin_bone, shin_base * shin_rot)
	if foot_bone >= 0 and base_bone_rotations.has(foot_bone):
		var foot_base: Quaternion = base_bone_rotations[foot_bone]
		var toe_lift: float = max(phase_value, 0.0) * _scaled_refinement_value(float(profile.get("toe_lift", 0.0)))
		var toe_drop: float = max(-phase_value, 0.0) * _scaled_refinement_value(float(profile.get("toe_drop", 0.0)))
		var foot_rot := Quaternion(Vector3.RIGHT, -toe_lift + toe_drop)
		skeleton.set_bone_pose_rotation(foot_bone, foot_base * foot_rot)

func _apply_arm_pose(arm_bone: int, forearm_bone: int, phase_value: float, profile: Dictionary) -> void:
	if arm_bone < 0 or not base_bone_rotations.has(arm_bone):
		return
	var arm_base: Quaternion = base_bone_rotations[arm_bone]
	var arm_rot := Quaternion(Vector3.RIGHT, phase_value * _scaled_refinement_value(float(profile.get("arm_swing", 0.0)))) * Quaternion(Vector3.BACK, phase_value * _scaled_refinement_value(float(profile.get("arm_roll", 0.0))))
	skeleton.set_bone_pose_rotation(arm_bone, arm_base * arm_rot)
	if forearm_bone >= 0 and base_bone_rotations.has(forearm_bone):
		var forearm_base: Quaternion = base_bone_rotations[forearm_bone]
		var elbow_bend: float = max(-phase_value, 0.0) * _scaled_refinement_value(float(profile.get("elbow_bend", 0.0)))
		var forearm_rot := Quaternion(Vector3.RIGHT, elbow_bend)
		skeleton.set_bone_pose_rotation(forearm_bone, forearm_base * forearm_rot)

func _apply_hand_pose(hand_bone: int, phase_value: float, profile: Dictionary) -> void:
	if hand_bone < 0 or not base_bone_rotations.has(hand_bone):
		return
	var hand_base: Quaternion = base_bone_rotations[hand_bone]
	var hand_rot := Quaternion(Vector3.RIGHT, phase_value * _scaled_refinement_value(float(profile.get("hand_swing", 0.0)))) * Quaternion(Vector3.BACK, phase_value * _scaled_refinement_value(float(profile.get("hand_roll", 0.0))))
	skeleton.set_bone_pose_rotation(hand_bone, hand_base * hand_rot)

func _scaled_refinement_value(value: float) -> float:
	return value * locomotion_amplitude_scale

func _trigger_action_pose_overlay(state_name: String) -> void:
	match state_name:
		"sword_swing":
			sword_swing_timer = 0.78
			shield_block_timer = 0.0
			_bus_log("role_action_overlay:sword_swing")
		"shield_block":
			shield_block_timer = 0.92
			sword_swing_timer = 0.0
			_bus_log("role_action_overlay:shield_block")

func _update_action_pose_overlays(delta: float) -> void:
	sword_swing_timer = max(sword_swing_timer - delta, 0.0)
	shield_block_timer = max(shield_block_timer - delta, 0.0)

func _sync_combat_modifier() -> void:
	if combat_modifier == null:
		return
	if combat_modifier.has_method("set_modifier_input"):
		combat_modifier.call("set_modifier_input", _build_combat_modifier_input())
		return
	if not combat_modifier.has_method("set_sword_overlay"):
		return
	var modifier_input := _build_combat_modifier_input()
	combat_modifier.call(
		"set_sword_overlay",
		float(modifier_input.get("sword_overlay_progress", 0.0)),
		2.2,
		1.68,
		0.88,
		0.5
	)
	combat_modifier.call(
		"set_shield_overlay",
		float(modifier_input.get("shield_overlay_progress", 0.0)),
		-1.72,
		-1.92,
		-0.72,
		0.36
	)

func _build_combat_modifier_input() -> Dictionary:
	var sword_progress := 1.0 - (sword_swing_timer / 0.78) if sword_swing_timer > 0.0 else 0.0
	var shield_progress := 1.0 - (shield_block_timer / 0.92) if shield_block_timer > 0.0 else 0.0
	return {
		"sword_overlay_progress": sword_progress,
		"shield_overlay_progress": shield_progress,
		"sword_upper_strength": 2.2,
		"sword_forearm_strength": 1.68,
		"sword_hand_strength": 0.88,
		"sword_spine_strength": 0.5,
		"shield_upper_strength": -1.72,
		"shield_forearm_strength": -1.92,
		"shield_hand_strength": -0.72,
		"shield_spine_strength": 0.36,
	}

func _bus_log(message: String) -> void:
	var bus: Node = get_node_or_null("/root/LocalPresentationBus")
	if bus and bus.has_method("log_debug"):
		bus.log_debug(message)

func _restore_pose_refinement_bones() -> void:
	if skeleton == null:
		return
	for bone_idx in base_bone_rotations.keys():
		skeleton.set_bone_pose_rotation(int(bone_idx), base_bone_rotations[bone_idx])
		if base_bone_positions.has(bone_idx):
			skeleton.set_bone_pose_position(int(bone_idx), base_bone_positions[bone_idx])

func _restore_knight_scene_pose() -> void:
	if knight_scene == null:
		return
	knight_scene.position = base_knight_scene_position
	knight_scene.rotation = base_knight_scene_rotation
