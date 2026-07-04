extends RefCounted

class_name SpatialPatchProvider

const ProviderSampleBaseRef = preload("res://scripts/character/ProviderSampleBase.gd")

var provider_kind := "spatial_patch"
var provider_role := "sampling_only"
var heavy_voxelization_allowed := false
var heavy_scene_scan_allowed := false
var max_cells_per_patch := 64

func build_query_input_ref(subject_id: String, zone_id: String, obstacle_refs: Array[String] = [], occlusion_refs: Array[String] = []) -> Dictionary:
	var runtime_source_ref := "runtime://space/%s/occupancy/%s" % [zone_id, Time.get_ticks_msec()]
	return ProviderSampleBaseRef.attach_sample_metadata({
		"provider_kind": provider_kind,
		"ref_id": runtime_source_ref,
		"summary": "bounded local occupancy and BEV patch",
		"retention": "ref_only",
		"zone_id": zone_id,
		"obstacle_refs": obstacle_refs,
		"occlusion_refs": occlusion_refs,
		"passability_refs": ["runtime://space/%s/passability" % zone_id],
		"runtime_source_refs": [runtime_source_ref] + obstacle_refs + occlusion_refs,
		"max_cells_per_patch": max_cells_per_patch,
		"feeds_query_frame": true,
		"provider_role": provider_role,
	}, "runtime://space/%s" % zone_id, "ok", "")


func build_runtime_patch_ref(subject_id: String, zone_id: String, occupancy_artifact_ref: String, obstacle_refs: Array[String] = [], occlusion_refs: Array[String] = []) -> Dictionary:
	var payload := build_query_input_ref(subject_id, zone_id, obstacle_refs, occlusion_refs)
	payload["artifact_ref"] = occupancy_artifact_ref
	payload["retention"] = "debug_artifact"
	return payload

func clamp_patch_cells(cells: Array) -> Array:
	return cells.slice(0, max_cells_per_patch)
