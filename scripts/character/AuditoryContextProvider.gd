extends RefCounted

class_name AuditoryContextProvider

const ProviderSampleBaseRef = preload("res://scripts/character/ProviderSampleBase.gd")

var provider_kind := "auditory_context"
var provider_role := "sampling_only"
var heavy_inference_allowed := false
var time_window_ms := 1500

func build_query_input_ref(subject_id: String, source_refs: Array[String], ambient_noise: String = "quiet") -> Dictionary:
	var runtime_window_ref := "runtime://auditory/%s/window/%s" % [subject_id, Time.get_ticks_msec()]
	return ProviderSampleBaseRef.attach_sample_metadata({
		"provider_kind": provider_kind,
		"ref_id": runtime_window_ref,
		"summary": "short auditory time window",
		"retention": "ref_only",
		"source_refs": source_refs,
		"runtime_source_refs": [runtime_window_ref] + source_refs,
		"ambient_noise": ambient_noise,
		"time_window_ms": time_window_ms,
		"feeds_query_frame": true,
		"provider_role": provider_role,
	}, "runtime://auditory/%s" % subject_id, "ok", "")
