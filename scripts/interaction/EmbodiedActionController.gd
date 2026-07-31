extends Node

class_name EmbodiedActionController

const ORDERED_PHASES: Array[String] = [
	"acquire_target",
	"reserve_stance",
	"plan_approach",
	"navigate",
	"align",
	"prepare",
	"execute_contact",
	"observe",
	"recover",
	"terminal",
]

var current_phase := "idle"
var active_attempt_id := ""
var active_controller_grant_id := ""
var active_connection_epoch := 0
var active_outcome_nonce := ""
var local_ownership_restored := true
var selected_realization_route := ""
var trace_events: Array[Dictionary] = []


func can_start_attempt(request: Dictionary, grant: Dictionary) -> Dictionary:
	if str(request.get("realization_route", "")) != "embodied_controller_v1":
		return {"accepted": false, "error_code": "realization_route_not_embodied_controller"}
	if str(grant.get("grant_id", "")) == "":
		return {"accepted": false, "error_code": "controller_grant_required"}
	if int(grant.get("connection_epoch", 0)) <= 0:
		return {"accepted": false, "error_code": "connection_epoch_required"}
	if str(grant.get("one_time_outcome_nonce", "")) == "":
		return {"accepted": false, "error_code": "outcome_nonce_required"}
	return {"accepted": true, "error_code": ""}


func run_attempt(request: Dictionary, grant: Dictionary, registry_binding: Dictionary, scenario: String = "success") -> Dictionary:
	var allowed := can_start_attempt(request, grant)
	if not bool(allowed.get("accepted", false)):
		return _terminal_outcome(request, grant, registry_binding, "failed_precondition", str(allowed.get("error_code", "")), false)
	active_attempt_id = str(request.get("interaction_attempt_id", ""))
	active_controller_grant_id = str(grant.get("grant_id", ""))
	active_connection_epoch = int(grant.get("connection_epoch", 0))
	active_outcome_nonce = str(grant.get("one_time_outcome_nonce", ""))
	selected_realization_route = str(request.get("realization_route", ""))
	local_ownership_restored = false
	trace_events.clear()
	current_phase = "idle"
	for phase: String in ORDERED_PHASES:
		if phase == "terminal":
			break
		_enter_phase(phase)
		var terminal := _terminal_for_scenario(scenario, phase)
		if terminal != "":
			return _terminal_outcome(request, grant, registry_binding, terminal, _failure_for_terminal(terminal, scenario), terminal == "contact_observed")
	return _terminal_outcome(request, grant, registry_binding, "contact_observed", "", true)


func cancel_attempt(reason: String = "authority_cancelled") -> Dictionary:
	var request := {
		"interaction_attempt_id": active_attempt_id,
		"causation_id": "cancel:%s" % active_attempt_id,
		"correlation_id": "cancel:%s" % active_attempt_id,
	}
	var grant := {
		"grant_id": active_controller_grant_id,
		"connection_epoch": active_connection_epoch,
		"one_time_outcome_nonce": active_outcome_nonce,
	}
	return _terminal_outcome(request, grant, {}, "aborted", reason, false)


func _enter_phase(phase: String) -> void:
	current_phase = phase
	trace_events.append({
		"interaction_attempt_id": active_attempt_id,
		"phase": phase,
		"trace_ref": "local_phase:%s:%s" % [active_attempt_id, phase],
	})


func _terminal_for_scenario(scenario: String, phase: String) -> String:
	if scenario == "no_path" and phase == "plan_approach":
		return "failed_navigation"
	if scenario == "occupied_stance" and phase == "reserve_stance":
		return "failed_precondition"
	if scenario == "failed_alignment" and phase == "align":
		return "failed_alignment"
	if scenario == "miss" and phase == "execute_contact":
		return "missed_contact"
	if scenario == "fixed_target" and phase == "observe":
		return "failed_precondition"
	if scenario == "target_moved" and phase == "navigate":
		return "interrupted"
	if scenario == "cancelled" and phase == "prepare":
		return "aborted"
	return ""


func _failure_for_terminal(terminal_status: String, scenario: String) -> String:
	match terminal_status:
		"failed_navigation":
			return "no_path"
		"failed_alignment":
			return "alignment_failed"
		"missed_contact":
			return "missed_contact"
		"failed_precondition":
			return scenario
		"interrupted":
			return "target_moved"
		"aborted":
			return "authority_cancelled"
		_:
			return ""


func _terminal_outcome(
	request: Dictionary,
	grant: Dictionary,
	registry_binding: Dictionary,
	terminal_status: String,
	failure_code: String,
	contact_observed: bool
) -> Dictionary:
	_enter_phase("recover")
	current_phase = "terminal"
	local_ownership_restored = true
	var attempt_id := str(request.get("interaction_attempt_id", active_attempt_id))
	var target_ref := str(request.get("target_ref", registry_binding.get("entity_ref", "")))
	var collider_refs: Array = registry_binding.get("local_binding", {}).get("collider_refs", ["collider:chair_01:body"])
	var target_collider_ref := str(collider_refs[0]) if collider_refs.size() > 0 else "collider:unknown"
	var outcome := {
		"interaction_attempt_id": attempt_id,
		"phase": "terminal",
		"terminal_status": terminal_status,
		"observed_at": Time.get_ticks_msec(),
		"actor_pose_ref": "pose:%s:bounded:%s" % [str(request.get("actor_id", "")), attempt_id],
		"target_binding_ref": "binding:%s:%s" % [target_ref, str(request.get("binding_revision", ""))],
		"trace_refs": _trace_refs(),
		"causation_id": str(request.get("causation_id", "")),
		"correlation_id": str(request.get("correlation_id", "")),
		"controller_grant_id": str(grant.get("grant_id", "")),
		"connection_epoch": int(grant.get("connection_epoch", 0)),
		"terminal_sequence": trace_events.size() + 1,
		"outcome_nonce": str(grant.get("one_time_outcome_nonce", "")),
		"payload_digest": "sha256:%s:%s" % [attempt_id, terminal_status],
		"local_ownership_restored": local_ownership_restored,
	}
	if failure_code != "":
		outcome["failure_code"] = failure_code
	if contact_observed:
		outcome["contact_observation"] = {
			"contact_ref": "contact:%s" % attempt_id,
			"actor_contact_ref": "collider:%s:foot_r" % str(request.get("actor_id", "")),
			"target_collider_ref": target_collider_ref,
			"contact_window_ref": "window:kick:%s" % attempt_id,
		}
		outcome["object_observation"] = {
			"object_ref": target_ref,
			"previous_state": "upright",
			"observed_state": "tipped",
			"observation_rule_ref": "observation_rule:chair_tipped:v1",
		}
	return outcome


func _trace_refs() -> Array[String]:
	var refs: Array[String] = []
	for event: Dictionary in trace_events:
		refs.append(str(event.get("trace_ref", "")))
	return refs


func build_runtime_probe_nodes() -> Dictionary:
	var navigation_agent := NavigationAgent3D.new()
	var collision_shape := CollisionShape3D.new()
	var result := {
		"navigation_agent_class": navigation_agent.get_class(),
		"collision_shape_class": collision_shape.get_class(),
	}
	navigation_agent.free()
	collision_shape.free()
	return result
