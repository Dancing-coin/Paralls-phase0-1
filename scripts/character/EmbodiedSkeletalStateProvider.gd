extends RefCounted

class_name EmbodiedSkeletalStateProvider

var provider_kind := "embodied_skeletal_state"
var provider_role := "local_skeletal_truth_provider"
var full_bone_snapshot_to_backend_allowed := false

func build_high_level_state(posture: String, gait: String, balance: String, active_behavior: String = "") -> Dictionary:
	return {
		"posture": posture,
		"gait": gait,
		"balance": balance,
		"active_behavior": active_behavior,
	}

func build_mid_level_parameters(anchor_refs: Dictionary, facing_vectors: Dictionary, reach_envelope: String, pose_features: Array[String]) -> Dictionary:
	return {
		"anchor_refs": anchor_refs,
		"facing_vectors": facing_vectors,
		"reach_envelope": reach_envelope,
		"pose_features": pose_features,
	}

func build_low_level_snapshot_ref(snapshot_ref: String, bone_count: int) -> Dictionary:
	return {
		"snapshot_ref": snapshot_ref,
		"bone_count": bone_count,
		"retention": "debug_replay_only",
	}

func build_main_chain_payload(actor_id: String, high_level_state: Dictionary, mid_level_parameters: Dictionary) -> Dictionary:
	return {
		"provider_kind": provider_kind,
		"actor_id": actor_id,
		"high_level_state": high_level_state,
		"mid_level_parameters": mid_level_parameters,
	}
