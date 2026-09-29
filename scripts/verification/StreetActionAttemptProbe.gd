extends RefCounted
class_name StreetActionAttemptProbe

const REQUIRED_ATTEMPT_FIELDS := [
	"attempt_id", "idempotency_key", "expected_revisions", "connection_epoch",
	"client_sequence", "physics_tick", "causation_id", "correlation_id",
	"physics_evidence_refs", "physics_evidence_digest", "action_descriptor_digest",
]

static func inspect_attempt(attempt: Dictionary) -> Dictionary:
	var missing: Array[String] = []
	for field in REQUIRED_ATTEMPT_FIELDS:
		if not attempt.has(field):
			missing.append(field)
	var digest := str(attempt.get("physics_evidence_digest", ""))
	var descriptor_digest := str(attempt.get("action_descriptor_digest", ""))
	return {
		"passed": missing.is_empty() and int(attempt.get("connection_epoch", 0)) >= 1 and int(attempt.get("client_sequence", 0)) >= 1 and not digest.is_empty() and not descriptor_digest.is_empty(),
		"missing_fields": missing,
		"attempt_digest": _digest(attempt),
		"authority_only": not attempt.has("damage") and not attempt.has("hit") and not attempt.has("hit_confirmed"),
	}

static func write_marker(attempts: Array[Dictionary], path: String) -> Dictionary:
	var observations: Array[Dictionary] = []
	for attempt in attempts:
		observations.append(inspect_attempt(attempt))
	var result := {
		"probe": "street_action_attempt",
		"accepted_marker": observations.any(func(value: Dictionary) -> bool: return bool(value.get("passed", false))),
		"observations": observations,
	}
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(result))
		file.close()
	return result

static func _digest(value: Dictionary) -> String:
	return "sha256:" + JSON.stringify(value).sha256_text()
