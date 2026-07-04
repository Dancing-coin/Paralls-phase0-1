extends RefCounted

class_name EnvironmentFieldProvider

const ProviderSampleBaseRef = preload("res://scripts/character/ProviderSampleBase.gd")

var provider_kind := "environment_field"
var provider_role := "sampling_only"
var heavy_voxelization_allowed := false
var heavy_scene_scan_allowed := false
var max_field_refs_per_sample := 16

func build_query_input_ref(
	zone_id: String,
	light_refs: Array[String],
	occlusion_refs: Array[String],
	hazard_refs: Array[String],
	passability_refs: Array[String],
	local_field_refs: Array[String]
) -> Dictionary:
	var runtime_field_ref := "runtime://environment/%s/field/%s" % [zone_id, Time.get_ticks_msec()]
	var runtime_refs: Array[String] = [runtime_field_ref]
	runtime_refs.append_array(light_refs)
	runtime_refs.append_array(occlusion_refs)
	runtime_refs.append_array(hazard_refs)
	runtime_refs.append_array(passability_refs)
	runtime_refs.append_array(local_field_refs)
	return ProviderSampleBaseRef.attach_sample_metadata({
		"provider_kind": provider_kind,
		"ref_id": runtime_field_ref,
		"summary": "bounded local environment field refs",
		"retention": "ref_only",
		"zone_id": zone_id,
		"light_refs": light_refs.slice(0, max_field_refs_per_sample),
		"occlusion_refs": occlusion_refs.slice(0, max_field_refs_per_sample),
		"hazard_refs": hazard_refs.slice(0, max_field_refs_per_sample),
		"passability_refs": passability_refs.slice(0, max_field_refs_per_sample),
		"local_field_refs": local_field_refs.slice(0, max_field_refs_per_sample),
		"runtime_source_refs": runtime_refs.slice(0, max_field_refs_per_sample),
		"feeds_query_frame": true,
		"provider_role": provider_role,
	}, "runtime://environment/%s" % zone_id, "ok", "")


func build_failure_ref(zone_id: String, error: String) -> Dictionary:
	return ProviderSampleBaseRef.build_failure_sample(provider_kind, "runtime://environment/%s" % zone_id, error)
