extends RefCounted

class_name VisualPatchProvider

var provider_kind := "visual_patch"
var provider_role := "sampling_only"
var heavy_inference_allowed := false
var heavy_scene_scan_allowed := false
var max_samples_per_second := 8

func build_query_input_ref(subject_id: String, camera_pose: Dictionary, target_ref: String = "") -> Dictionary:
	return {
		"provider_kind": provider_kind,
		"ref_id": "visual_patch:%s:%s" % [subject_id, Time.get_ticks_msec()],
		"summary": "actor-local visual patch sample",
		"retention": "ref_only",
		"camera_pose": camera_pose,
		"target_ref": target_ref,
		"feeds_query_frame": true,
		"provider_role": provider_role,
	}

func can_sample(now_msec: int, last_sample_msec: int) -> bool:
	var min_interval := int(1000.0 / float(max_samples_per_second))
	return now_msec - last_sample_msec >= min_interval
