extends RefCounted
class_name StreetActionAttemptProbe

const REQUIRED_ATTEMPT_FIELDS := [
	"attempt_id", "actor_ref", "action_instance_id", "semantic_action_id",
	"target_refs", "contact_marker_id", "idempotency_key", "expected_revisions",
	"connection_epoch", "client_sequence", "physics_tick", "causation_id",
	"correlation_id", "physics_evidence_refs", "physics_evidence_digest",
	"action_descriptor_digest", "authority_route", "command_version", "source",
	"privacy_scope",
]

static func inspect_attempt(attempt: Dictionary) -> Dictionary:
	var missing: Array[String] = []
	for field in REQUIRED_ATTEMPT_FIELDS:
		if not attempt.has(field):
			missing.append(field)
	var digest := str(attempt.get("physics_evidence_digest", ""))
	var descriptor_digest := str(attempt.get("action_descriptor_digest", ""))
	var authority_only := _authority_only(attempt)
	var evidence_refs: Variant = attempt.get("physics_evidence_refs", [])
	var evidence_present := evidence_refs is Array and not (evidence_refs as Array).is_empty() and (evidence_refs as Array).all(func(value: Variant) -> bool: return not str(value).strip_edges().is_empty())
	return {
		"passed": missing.is_empty() and int(attempt.get("connection_epoch", 0)) >= 1 and int(attempt.get("client_sequence", 0)) >= 1 and _is_sha256_digest(digest) and _is_sha256_digest(descriptor_digest) and evidence_present and authority_only,
		"missing_fields": missing,
		"attempt_digest": _digest(attempt),
		"authority_only": authority_only,
		"evidence_present": evidence_present,
	}

static func compare_authority_replay(results: Dictionary) -> Dictionary:
	var accepted_result := _authority_result(results.get("accepted", {}))
	var duplicate_result := _authority_result(results.get("duplicate", {}))
	var stale_result := _authority_result(results.get("stale", {}))
	var disconnected_result := _authority_result(results.get("disconnected", {}))
	var reconnect_blocked_result := _authority_result(results.get("reconnect_blocked", {}))
	var recovered_result := _authority_result(results.get("recovered", {}))
	var accepted := str(accepted_result.get("outcome", "")) == "committed"
	var duplicate_replayed := accepted and str(duplicate_result.get("outcome", "")) == "committed" and str(duplicate_result.get("transaction_id", "")) == str(accepted_result.get("transaction_id", ""))
	var stale_rejected := str(stale_result.get("outcome", "")) == "rejected" and str(stale_result.get("failed_code", "")) in ["revision_conflict", "client_sequence_stale", "connection_epoch_stale"]
	var disconnected_rejected := str(disconnected_result.get("outcome", "")) == "rejected" and str(disconnected_result.get("failed_code", "")) == "transport_disconnected"
	var reconnect_blocked := str(reconnect_blocked_result.get("outcome", "")) == "rejected" and str(reconnect_blocked_result.get("failed_code", "")) == "recovery_required"
	var recovery_committed := str(recovered_result.get("outcome", "")) == "committed"
	return {
		"accepted": accepted,
		"duplicate_replayed": duplicate_replayed,
		"stale_rejected": stale_rejected,
		"disconnected_rejected": disconnected_rejected,
		"reconnect_blocked": reconnect_blocked,
		"recovery_committed": recovery_committed,
		"passed": accepted and duplicate_replayed and stale_rejected and disconnected_rejected and reconnect_blocked and recovery_committed,
	}

static func write_marker(attempts: Array[Dictionary], path: String, result_matrix: Dictionary = {}) -> Dictionary:
	var observations: Array[Dictionary] = []
	for attempt in attempts:
		observations.append(inspect_attempt(attempt))
	var replay := compare_authority_replay(result_matrix) if not result_matrix.is_empty() else {
		"accepted": false,
		"duplicate_replayed": false,
		"stale_rejected": false,
		"disconnected_rejected": false,
		"reconnect_blocked": false,
		"recovery_committed": false,
		"passed": false,
	}
	var result := {
		"probe": "street_action_attempt",
		"accepted_marker": observations.any(func(value: Dictionary) -> bool: return bool(value.get("passed", false))) and (result_matrix.is_empty() or bool(replay.get("passed", false))),
		"observations": observations,
		"authority_replay": replay,
	}
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(result))
		file.close()
	return result

static func _authority_only(attempt: Dictionary) -> bool:
	for field in ["damage", "hit", "hit_confirmed", "ammo", "ammo_delta", "projectile", "projectile_id", "ballistic_truth", "pose", "transform", "velocity", "world_truth_claim", "final_world_state"]:
		if attempt.has(field):
			return false
	return true

static func _is_sha256_digest(value: String) -> bool:
	if value.length() != 71 or not value.begins_with("sha256:"):
		return false
	for character in value.substr(7):
		if not ("0123456789abcdefABCDEF".contains(character)):
			return false
	return true

static func _authority_result(value: Variant) -> Dictionary:
	if not (value is Dictionary):
		return {}
	var payload: Dictionary = value
	var nested: Variant = payload.get("authority_result", payload)
	return nested if nested is Dictionary else {}

static func _digest(value: Dictionary) -> String:
	return "sha256:" + JSON.stringify(value).sha256_text()
