extends SkeletonModifier3D

@export var sword_in_hand_path: NodePath
@export var shield_in_hand_path: NodePath

var sword_swing_progress := 0.0
var shield_block_progress := 0.0
var sword_upper_strength := 0.0
var sword_forearm_strength := 0.0
var sword_hand_strength := 0.0
var sword_spine_strength := 0.0
var shield_upper_strength := 0.0
var shield_forearm_strength := 0.0
var shield_hand_strength := 0.0
var shield_spine_strength := 0.0

var right_upper_arm_bone := -1
var right_forearm_bone := -1
var right_hand_bone := -1
var left_upper_arm_bone := -1
var left_forearm_bone := -1
var left_hand_bone := -1
var spine_upper_bone := -1

var base_bone_rotations: Dictionary = {}
var sword_in_hand: Node3D
var shield_in_hand: Node3D
var base_sword_transform := Transform3D.IDENTITY
var base_shield_transform := Transform3D.IDENTITY
var external_right_arm_solver_active := false

func _ready() -> void:
	sword_in_hand = get_node_or_null(sword_in_hand_path)
	shield_in_hand = get_node_or_null(shield_in_hand_path)
	if sword_in_hand != null:
		base_sword_transform = sword_in_hand.transform
	if shield_in_hand != null:
		base_shield_transform = shield_in_hand.transform
	_cache_bones()

func configure_bones(bones: Dictionary) -> void:
	right_upper_arm_bone = int(bones.get("right_upper_arm_bone", -1))
	right_forearm_bone = int(bones.get("right_forearm_bone", -1))
	right_hand_bone = int(bones.get("right_hand_bone", -1))
	left_upper_arm_bone = int(bones.get("left_upper_arm_bone", -1))
	left_forearm_bone = int(bones.get("left_forearm_bone", -1))
	left_hand_bone = int(bones.get("left_hand_bone", -1))
	spine_upper_bone = int(bones.get("spine_upper_bone", -1))
	_cache_bones()


func set_external_right_arm_solver_active(enabled: bool) -> void:
	external_right_arm_solver_active = enabled

func set_sword_overlay(progress: float, upper_strength: float, forearm_strength: float, hand_strength: float, spine_strength: float) -> void:
	sword_swing_progress = clamp(progress, 0.0, 1.0)
	sword_upper_strength = upper_strength
	sword_forearm_strength = forearm_strength
	sword_hand_strength = hand_strength
	sword_spine_strength = spine_strength

func set_shield_overlay(progress: float, upper_strength: float, forearm_strength: float, hand_strength: float, spine_strength: float) -> void:
	shield_block_progress = clamp(progress, 0.0, 1.0)
	shield_upper_strength = upper_strength
	shield_forearm_strength = forearm_strength
	shield_hand_strength = hand_strength
	shield_spine_strength = spine_strength

func set_modifier_input(modifier_input: Dictionary) -> void:
	set_sword_overlay(
		float(modifier_input.get("sword_overlay_progress", 0.0)),
		float(modifier_input.get("sword_upper_strength", 0.0)),
		float(modifier_input.get("sword_forearm_strength", 0.0)),
		float(modifier_input.get("sword_hand_strength", 0.0)),
		float(modifier_input.get("sword_spine_strength", 0.0))
	)
	set_shield_overlay(
		float(modifier_input.get("shield_overlay_progress", 0.0)),
		float(modifier_input.get("shield_upper_strength", 0.0)),
		float(modifier_input.get("shield_forearm_strength", 0.0)),
		float(modifier_input.get("shield_hand_strength", 0.0)),
		float(modifier_input.get("shield_spine_strength", 0.0))
	)

func _process_modification() -> void:
	var skeleton := get_skeleton()
	if skeleton == null:
		return
	_restore_base_pose(skeleton)
	_apply_sword_pose(skeleton)
	_apply_shield_pose(skeleton)
	_apply_equipment_pose()

func _cache_bones() -> void:
	var skeleton := get_skeleton()
	if skeleton == null:
		return
	base_bone_rotations.clear()
	for bone_idx in [
		right_upper_arm_bone,
		right_forearm_bone,
		right_hand_bone,
		left_upper_arm_bone,
		left_forearm_bone,
		left_hand_bone,
		spine_upper_bone,
	]:
		if bone_idx >= 0:
			base_bone_rotations[bone_idx] = skeleton.get_bone_pose_rotation(bone_idx)

func _restore_base_pose(skeleton: Skeleton3D) -> void:
	for bone_idx in base_bone_rotations.keys():
		if external_right_arm_solver_active and int(bone_idx) in [right_upper_arm_bone, right_forearm_bone, right_hand_bone]:
			continue
		skeleton.set_bone_pose_rotation(int(bone_idx), base_bone_rotations[bone_idx])

func _apply_sword_pose(skeleton: Skeleton3D) -> void:
	if sword_swing_progress <= 0.0 or external_right_arm_solver_active:
		return
	var swing_phase: float = sin(sword_swing_progress * PI)
	var slash_phase: float = sin(sword_swing_progress * TAU - PI * 0.35)
	_apply_overlay_rotation(
		skeleton,
		right_upper_arm_bone,
		Quaternion(Vector3.RIGHT, sword_upper_strength * swing_phase) * Quaternion(Vector3.UP, -1.32 * slash_phase) * Quaternion(Vector3.BACK, -1.08 * swing_phase)
	)
	_apply_overlay_rotation(
		skeleton,
		right_forearm_bone,
		Quaternion(Vector3.RIGHT, sword_forearm_strength * swing_phase) * Quaternion(Vector3.BACK, -0.92 * slash_phase)
	)
	_apply_overlay_rotation(
		skeleton,
		right_hand_bone,
		Quaternion(Vector3.RIGHT, sword_hand_strength * swing_phase) * Quaternion(Vector3.BACK, -1.58 * slash_phase)
	)
	_apply_overlay_rotation(
		skeleton,
		spine_upper_bone,
		Quaternion(Vector3.UP, -sword_spine_strength * swing_phase) * Quaternion(Vector3.BACK, -0.34 * slash_phase) * Quaternion(Vector3.RIGHT, 0.28 * swing_phase)
	)

func _apply_shield_pose(skeleton: Skeleton3D) -> void:
	if shield_block_progress <= 0.0:
		return
	var raise_phase: float = sin(shield_block_progress * PI)
	var brace_phase: float = min(shield_block_progress * 1.8, 1.0)
	_apply_overlay_rotation(
		skeleton,
		left_upper_arm_bone,
		Quaternion(Vector3.RIGHT, shield_upper_strength * raise_phase) * Quaternion(Vector3.UP, 1.28 * brace_phase) * Quaternion(Vector3.BACK, 1.05 * brace_phase)
	)
	_apply_overlay_rotation(
		skeleton,
		left_forearm_bone,
		Quaternion(Vector3.RIGHT, shield_forearm_strength * brace_phase) * Quaternion(Vector3.BACK, 0.82 * raise_phase)
	)
	_apply_overlay_rotation(
		skeleton,
		left_hand_bone,
		Quaternion(Vector3.RIGHT, shield_hand_strength * brace_phase) * Quaternion(Vector3.BACK, 1.12 * raise_phase)
	)
	_apply_overlay_rotation(
		skeleton,
		spine_upper_bone,
		Quaternion(Vector3.RIGHT, shield_spine_strength * brace_phase) * Quaternion(Vector3.UP, 0.34 * brace_phase) * Quaternion(Vector3.BACK, 0.2 * brace_phase)
	)

func _apply_equipment_pose() -> void:
	if sword_in_hand != null:
		if sword_swing_progress > 0.0:
			var sword_phase: float = sin(sword_swing_progress * PI)
			sword_in_hand.rotation = base_sword_transform.basis.get_euler() + Vector3(-0.45 * sword_phase, -1.15 * sword_phase, -0.35 * sword_phase)
		else:
			sword_in_hand.transform = base_sword_transform
	if shield_in_hand != null:
		if shield_block_progress > 0.0:
			var shield_phase: float = sin(shield_block_progress * PI)
			shield_in_hand.rotation = base_shield_transform.basis.get_euler() + Vector3(-0.35 * shield_phase, 0.85 * shield_phase, 0.4 * shield_phase)
		else:
			shield_in_hand.transform = base_shield_transform

func _apply_overlay_rotation(skeleton: Skeleton3D, bone_idx: int, overlay: Quaternion) -> void:
	if bone_idx < 0 or not base_bone_rotations.has(bone_idx):
		return
	skeleton.set_bone_pose_rotation(bone_idx, base_bone_rotations[bone_idx] * overlay)
