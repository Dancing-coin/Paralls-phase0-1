extends RefCounted

class_name ProviderSampleBase

static func attach_sample_metadata(
	payload: Dictionary,
	stable_source_ref: String,
	sample_status: String = "ok",
	error: String = "",
	max_samples_per_second: int = 0
) -> Dictionary:
	var now := Time.get_ticks_msec()
	payload["sample_status"] = sample_status
	payload["freshness"] = "fresh" if sample_status in ["ok", "stub_artifact"] else "unknown"
	payload["throttle_state"] = "allowed" if sample_status != "throttled" else "throttled"
	payload["stable_source_ref"] = stable_source_ref
	payload["error"] = error
	payload["failure_status"] = "none" if error == "" and sample_status != "failed" else "provider_error"
	payload["expires_at"] = now + 2000
	if not payload.has("runtime_source_refs"):
		payload["runtime_source_refs"] = [stable_source_ref]
	if max_samples_per_second > 0:
		payload["max_samples_per_second"] = max_samples_per_second
	return payload


static func build_failure_sample(provider_kind: String, stable_source_ref: String, error: String) -> Dictionary:
	return attach_sample_metadata(
		{
			"provider_kind": provider_kind,
			"ref_id": "%s/failure/%s" % [stable_source_ref, Time.get_ticks_msec()],
			"summary": "structured provider failure",
			"retention": "ref_only",
			"runtime_source_refs": [stable_source_ref],
			"feeds_query_frame": true,
		},
		stable_source_ref,
		"failed",
		error
	)
