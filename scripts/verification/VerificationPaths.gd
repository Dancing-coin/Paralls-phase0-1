extends RefCounted


static func resolve(logical_path: String) -> String:
	var reference := logical_path.trim_prefix("res://").replace("\\", "/")
	var prefix := ".harness/verification/"
	var evidence_root := OS.get_environment("HARNESS_EVIDENCE_ROOT").replace("\\", "/").simplify_path()
	var attempt_root := OS.get_environment("HARNESS_ATTEMPT_ROOT").replace("\\", "/").simplify_path()
	if not reference.begins_with(prefix) or not evidence_root.is_absolute_path():
		push_error("harness_verification_path:missing_context_or_invalid_reference")
		return ""
	var relative := reference.trim_prefix(prefix)
	if relative.is_empty() or relative.is_absolute_path() or relative.split("/").has("..") or relative.contains(":"):
		push_error("harness_verification_path:reference_outside_evidence_root")
		return ""
	var output_root := evidence_root
	if not attempt_root.is_empty() and attempt_root != ".":
		if not attempt_root.begins_with(evidence_root.trim_suffix("/") + "/"):
			push_error("harness_verification_path:attempt_outside_evidence_root")
			return ""
		output_root = attempt_root
	return output_root.path_join(relative)
