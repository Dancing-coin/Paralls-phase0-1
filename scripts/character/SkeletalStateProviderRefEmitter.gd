extends RefCounted

class_name SkeletalStateProviderRefEmitter

const ProviderSampleBaseRef = preload("res://scripts/character/ProviderSampleBase.gd")

var provider_kind := "skeletal_state"
var provider_role := "sampling_only"
var heavy_inference_allowed := false
var heavy_voxelization_allowed := false
var full_bone_snapshot_to_main_chain_allowed := false

func build_query_input_ref(
	actor_id: String,
	high_mid_source_ref: String,
	debug_snapshot_ref: String = "",
	bone_count: int = 0
) -> Dictionary:
	var now := Time.get_ticks_msec()
	var runtime_ref := "runtime://embodied_skeletal/%s/high_mid/%s" % [actor_id, now]
	var runtime_refs: Array[String] = [runtime_ref, high_mid_source_ref]
	if debug_snapshot_ref != "":
		runtime_refs.append(debug_snapshot_ref)
	return ProviderSampleBaseRef.attach_sample_metadata({
		"provider_kind": provider_kind,
		"ref_id": runtime_ref,
		"summary": "high and mid-level skeletal refs with debug replay snapshot ref only",
		"retention": "ref_only",
		"runtime_source_refs": runtime_refs,
		"high_mid_source_ref": high_mid_source_ref,
		"debug_snapshot_ref": debug_snapshot_ref,
		"debug_snapshot_retention": "debug_replay_only",
		"bone_count": bone_count,
		"feeds_query_frame": true,
		"provider_role": provider_role,
	}, "runtime://embodied_skeletal/%s" % actor_id, "ok", "")


func build_failure_ref(actor_id: String, error: String) -> Dictionary:
	return ProviderSampleBaseRef.build_failure_sample(provider_kind, "runtime://embodied_skeletal/%s" % actor_id, error)
