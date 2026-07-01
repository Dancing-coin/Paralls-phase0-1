extends RefCounted

class_name AuditoryContextProvider

var provider_kind := "auditory_context"
var provider_role := "sampling_only"
var heavy_inference_allowed := false
var time_window_ms := 1500

func build_query_input_ref(subject_id: String, source_refs: Array[String], ambient_noise: String = "quiet") -> Dictionary:
	return {
		"provider_kind": provider_kind,
		"ref_id": "auditory_context:%s:%s" % [subject_id, Time.get_ticks_msec()],
		"summary": "short auditory time window",
		"retention": "ref_only",
		"source_refs": source_refs,
		"ambient_noise": ambient_noise,
		"time_window_ms": time_window_ms,
		"feeds_query_frame": true,
		"provider_role": provider_role,
	}
