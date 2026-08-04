extends SkeletonModifier3D


const ITERATIONS_PER_UPDATE := 6
const MAX_ROTATION_STEP_RAD := 0.45
const VECTOR_EPSILON := 0.0001

var right_upper_arm_bone := -1
var right_forearm_bone := -1
var right_hand_bone := -1
var reach_active := false
var target_world_position := Vector3.ZERO
var last_error_m := INF


func configure_bones(bones: Dictionary) -> void:
	right_upper_arm_bone = int(bones.get("right_upper_arm_bone", -1))
	right_forearm_bone = int(bones.get("right_forearm_bone", -1))
	right_hand_bone = int(bones.get("right_hand_bone", -1))


func begin_reach(anchor_world_position: Vector3) -> bool:
	if right_upper_arm_bone < 0 or right_forearm_bone < 0 or right_hand_bone < 0:
		return false
	target_world_position = anchor_world_position
	reach_active = true
	last_error_m = INF
	return true


func clear_reach() -> void:
	reach_active = false
	last_error_m = INF


func _process_modification() -> void:
	if not reach_active:
		return
	var skeleton := get_skeleton()
	if skeleton == null:
		reach_active = false
		return
	for _iteration in range(ITERATIONS_PER_UPDATE):
		_rotate_chain_bone_toward_target(skeleton, right_forearm_bone)
		_force_bone_update(skeleton)
		_rotate_chain_bone_toward_target(skeleton, right_upper_arm_bone)
		_force_bone_update(skeleton)
	last_error_m = _bone_world_position(skeleton, right_hand_bone).distance_to(target_world_position)


func _rotate_chain_bone_toward_target(skeleton: Skeleton3D, bone_idx: int) -> void:
	if bone_idx < 0:
		return
	var bone_world_position := _bone_world_position(skeleton, bone_idx)
	var hand_world_position := _bone_world_position(skeleton, right_hand_bone)
	var hand_direction := hand_world_position - bone_world_position
	var target_direction := target_world_position - bone_world_position
	if hand_direction.length() <= VECTOR_EPSILON or target_direction.length() <= VECTOR_EPSILON:
		return
	var source_world := hand_direction.normalized()
	var target_world := target_direction.normalized()
	var world_axis := source_world.cross(target_world)
	if world_axis.length() <= VECTOR_EPSILON:
		return
	var angle := acos(clamp(source_world.dot(target_world), -1.0, 1.0))
	angle = min(angle, MAX_ROTATION_STEP_RAD)
	var parent_world_basis := skeleton.global_transform.basis
	var parent_bone_idx := skeleton.get_bone_parent(bone_idx)
	if parent_bone_idx >= 0:
		parent_world_basis = skeleton.global_transform.basis * skeleton.get_bone_global_pose(parent_bone_idx).basis
	var world_correction := Basis(Quaternion(world_axis.normalized(), angle))
	var local_correction := parent_world_basis.inverse() * world_correction * parent_world_basis
	var current_rotation := skeleton.get_bone_pose_rotation(bone_idx)
	skeleton.set_bone_pose_rotation(bone_idx, local_correction.get_rotation_quaternion() * current_rotation)


func _force_bone_update(skeleton: Skeleton3D) -> void:
	if skeleton.has_method("force_update_all_bone_transforms"):
		skeleton.call("force_update_all_bone_transforms")


func _bone_world_position(skeleton: Skeleton3D, bone_idx: int) -> Vector3:
	return skeleton.global_transform * skeleton.get_bone_global_pose(bone_idx).origin
