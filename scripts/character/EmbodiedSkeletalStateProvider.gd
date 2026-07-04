extends RefCounted

class_name EmbodiedSkeletalStateProvider

var provider_kind := "embodied_skeletal_state"
var provider_role := "local_skeletal_truth_provider"
var full_bone_snapshot_to_backend_allowed := false
var retention := "debug_replay_only"

func bind_runtime(actor_node: Node, skeleton: Skeleton3D = null) -> Dictionary:
	var replica := _find_character_replica(actor_node)
	var bound_skeleton := skeleton if skeleton != null else _find_first_skeleton(actor_node)
	return {
		"actor_node_path": str(actor_node.get_path()) if actor_node != null else "",
		"character_replica_path": str(replica.get_path()) if replica != null else "",
		"skeleton_path": str(bound_skeleton.get_path()) if bound_skeleton != null else "",
		"bone_count": bound_skeleton.get_bone_count() if bound_skeleton != null else 0,
		"runtime_binding_verified": actor_node != null and replica != null and bound_skeleton != null,
	}

func build_high_level_state(posture: String, gait: String, balance: String, active_behavior: String = "") -> Dictionary:
	return {
		"posture": posture,
		"gait": gait,
		"balance": balance,
		"strain": "nominal",
		"active_behavior": active_behavior,
		"hand_readiness": "available",
	}

func build_mid_level_parameters(
	anchor_refs: Dictionary,
	facing_vectors: Dictionary,
	reach_envelope: String,
	pose_features: Array[String],
	balance_hints: Array[String] = [],
	strain_hints: Array[String] = [],
	hand_readiness: Dictionary = {},
	contact_candidate_refs: Array[String] = []
) -> Dictionary:
	return {
		"anchor_refs": anchor_refs,
		"facing_vectors": facing_vectors,
		"reach_envelope": reach_envelope,
		"balance_hints": balance_hints,
		"strain_hints": strain_hints,
		"hand_readiness": hand_readiness,
		"contact_candidate_refs": contact_candidate_refs,
		"pose_features": pose_features,
	}

func build_low_level_snapshot_ref(snapshot_ref: String, bone_count: int) -> Dictionary:
	return {
		"snapshot_ref": snapshot_ref,
		"bone_count": bone_count,
		"retention": "debug_replay_only",
	}

func write_debug_snapshot_artifact(
	actor_id: String,
	skeleton: Skeleton3D,
	trace_refs: Array[String],
	relative_path: String = ""
) -> Dictionary:
	var now := Time.get_ticks_msec()
	var path_suffix := relative_path
	if path_suffix == "":
		path_suffix = ".harness/verification/skeletal-replay-%s-%s.json" % [actor_id, now]
	var bones: Array[Dictionary] = []
	if skeleton != null:
		for index in range(skeleton.get_bone_count()):
			var pose := skeleton.get_bone_pose(index)
			bones.append({
				"index": index,
				"name": skeleton.get_bone_name(index),
				"origin": [pose.origin.x, pose.origin.y, pose.origin.z],
			})
	var payload := {
		"actor_id": actor_id,
		"skeleton_source_ref": "runtime://node%s" % str(skeleton.get_path()) if skeleton != null else "",
		"bone_count": bones.size(),
		"timestamp": now,
		"retention": "debug_replay_only",
		"trace_refs": trace_refs,
		"bones": bones,
	}
	var path := ProjectSettings.globalize_path("res://" + path_suffix)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(payload, "\t"))
		file.close()
	return {
		"snapshot_ref": "runtime://artifact/%s" % path,
		"artifact_path": path,
		"bone_count": bones.size(),
		"retention": "debug_replay_only",
		"trace_refs": trace_refs,
	}

func build_main_chain_payload(actor_id: String, high_level_state: Dictionary, mid_level_parameters: Dictionary) -> Dictionary:
	return {
		"provider_kind": provider_kind,
		"actor_id": actor_id,
		"runtime_source_refs": ["runtime://embodied_skeletal/%s/high_mid/%s" % [actor_id, Time.get_ticks_msec()]],
		"high_level_state": high_level_state,
		"mid_level_parameters": mid_level_parameters,
	}

func build_main_chain_payload_from_runtime(actor_id: String, actor_node: Node, trace_refs: Array[String] = []) -> Dictionary:
	var binding := bind_runtime(actor_node)
	var high := build_high_level_state("standing", "idle", "stable", "runtime_probe")
	var skeleton := _find_first_skeleton(actor_node)
	var anchor_refs := {
		"actor_root": "runtime://node%s" % str(actor_node.get_path()) if actor_node != null else "",
		"skeleton": "runtime://node%s" % str(skeleton.get_path()) if skeleton != null else "",
	}
	var facing_vectors := {"actor_forward": [0.0, 0.0, -1.0]}
	if actor_node is Node3D:
		var node3d := actor_node as Node3D
		facing_vectors["actor_forward"] = [-node3d.global_basis.z.x, -node3d.global_basis.z.y, -node3d.global_basis.z.z]
	var mid := build_mid_level_parameters(
		anchor_refs,
		facing_vectors,
		"arm_length_local",
		["standing", "hands_available"],
		["center_of_mass_within_support"],
		["no_high_strain"],
		{"left": "available", "right": "available"},
		["runtime://contact_candidate/%s/floor" % actor_id]
	)
	var payload := build_main_chain_payload(actor_id, high, mid)
	payload["runtime_binding"] = binding
	payload["trace_refs"] = trace_refs
	return payload

func _find_character_replica(root: Node) -> Node:
	if root == null:
		return null
	if root.name == "CharacterReplica":
		return root
	var direct := root.get_node_or_null("CharacterReplica")
	if direct != null:
		return direct
	for child: Node in root.get_children():
		var found := _find_character_replica(child)
		if found != null:
			return found
	return null

func _find_first_skeleton(root: Node) -> Skeleton3D:
	if root == null:
		return null
	if root is Skeleton3D:
		return root as Skeleton3D
	for child: Node in root.get_children():
		var found := _find_first_skeleton(child)
		if found != null:
			return found
	return null
