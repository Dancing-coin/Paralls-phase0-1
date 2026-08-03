extends Node

class_name InteractionSessionSlotConsumer

signal participant_observation_emitted(payload)

const TERMINAL_STATES: Array[String] = ["committed", "rejected", "cancelled", "interrupted", "expired"]
const FORBIDDEN_SAFE_PROJECTION_FIELDS: Array[String] = [
	"participant_private_terms",
	"private_participant_terms",
	"vla_prompt_context",
	"raw_private_memory",
	"full_skeletal_artifact",
	"world_truth_claim",
]

var session_id := ""
var participant_ref := ""
var state := "idle"
var slot_id := ""
var reservation_ref := ""
var reservation_state := "released"
var last_global_sequence := 0
var accepted_event_count := 0
var rejected_event_count := 0
var private_terms_rejected := false
var participant_observation_count := 0
var sync_status := "idle"
var event_trace: Array[Dictionary] = []


func configure(local_participant_ref: String) -> void:
	participant_ref = local_participant_ref


func consume_authority_event(payload: Dictionary) -> Dictionary:
	var privacy_check := _reject_private_projection(payload)
	if not bool(privacy_check.get("accepted", false)):
		private_terms_rejected = true
		rejected_event_count += 1
		return privacy_check

	var sequence := int(payload.get("global_sequence", 0))
	if sequence <= last_global_sequence:
		rejected_event_count += 1
		return {"accepted": false, "error_code": "global_sequence_not_monotonic"}

	var payload_session_id := str(payload.get("session_id", ""))
	if session_id != "" and payload_session_id != session_id:
		rejected_event_count += 1
		return {"accepted": false, "error_code": "session_id_mismatch"}

	var event_type := str(payload.get("event_type", ""))
	var next_state := str(payload.get("state", state))
	if event_type == "":
		rejected_event_count += 1
		return {"accepted": false, "error_code": "event_type_required"}

	last_global_sequence = sequence
	session_id = payload_session_id
	state = next_state
	sync_status = str(payload.get("sync_status", state))
	_apply_slot_projection(payload)
	accepted_event_count += 1
	event_trace.append({
		"event_type": event_type,
		"global_sequence": sequence,
		"state": state,
		"slot_id": slot_id,
		"reservation_state": reservation_state,
	})
	return {
		"accepted": true,
		"error_code": "",
		"session_id": session_id,
		"state": state,
		"sync_status": sync_status,
		"slot_id": slot_id,
		"reservation_state": reservation_state,
	}


func build_terminal_participation_observation(terminal_status: String = "completed") -> Dictionary:
	if state != "realizing":
		return {"accepted": false, "error_code": "session_not_realizing"}
	if session_id == "" or participant_ref == "" or slot_id == "":
		return {"accepted": false, "error_code": "slot_not_assigned"}
	var payload := {
		"session_id": session_id,
		"participant_ref": participant_ref,
		"slot_id": slot_id,
		"reservation_ref": reservation_ref,
		"terminal_status": terminal_status,
		"attempt_ref": "attempt:%s:%s" % [session_id, participant_ref],
		"payload_digest": "sha256:%s:%s:%s" % [session_id, participant_ref, terminal_status],
		"source_sequence": participant_observation_count + 1,
		"local_observation_ref": "local_session_observation:%s:%s:%s" % [session_id, participant_ref, participant_observation_count + 1],
	}
	participant_observation_count += 1
	emit_signal("participant_observation_emitted", payload)
	return {"accepted": true, "payload": payload}


func _apply_slot_projection(payload: Dictionary) -> void:
	var assignments: Array = payload.get("slot_assignments", [])
	for item: Variant in assignments:
		if typeof(item) != TYPE_DICTIONARY:
			continue
		var assignment: Dictionary = item
		if str(assignment.get("participant_ref", "")) != participant_ref:
			continue
		slot_id = str(assignment.get("slot_id", ""))
		reservation_ref = str(assignment.get("reservation_ref", ""))
		reservation_state = str(assignment.get("reservation_state", "reserved"))
	if TERMINAL_STATES.has(state):
		reservation_state = "released"


func _reject_private_projection(payload: Dictionary) -> Dictionary:
	for field_name: String in FORBIDDEN_SAFE_PROJECTION_FIELDS:
		if payload.has(field_name):
			return {"accepted": false, "error_code": "private_terms_rejected", "field": field_name}
	return {"accepted": true, "error_code": ""}
