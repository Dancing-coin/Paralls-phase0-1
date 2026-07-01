extends RefCounted

class_name EmbodiedStateProvider

var provider_kind := "embodied_state"
var provider_role := "sampling_only"
var heavy_inference_allowed := false

func build_query_input_ref(
	subject_id: String,
	posture: String,
	locomotion_state: String,
	grounded: bool,
	los_failure: bool = false,
	reachability_failure: bool = false
) -> Dictionary:
	var runtime_state_ref := "runtime://embodied/%s/state/%s" % [subject_id, Time.get_ticks_msec()]
	return {
		"provider_kind": provider_kind,
		"ref_id": runtime_state_ref,
		"summary": "high-level embodied state slice",
		"retention": "ref_only",
		"runtime_source_refs": [runtime_state_ref],
		"posture": posture,
		"locomotion_state": locomotion_state,
		"grounded": grounded,
		"los_failure": los_failure,
		"reachability_failure": reachability_failure,
		"feeds_query_frame": true,
		"provider_role": provider_role,
	}
