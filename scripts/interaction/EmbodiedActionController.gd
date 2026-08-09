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
const PHASE_ACTION_TAGS := {
	"plan_approach": ["start_move"],
	"navigate": ["step_left", "step_right", "backstep"],
	"align": ["turn_to_target", "stop_move"],
	"prepare": ["raise_hand", "reach_forward", "grip", "offer_item", "receive_item"],
	"execute_contact": ["kick_contact", "push_contact", "tap_contact", "brace_contact", "release"],
	"recover": ["recover_balance", "reset_guard", "return_idle", "abort_contact"],
}
const LOCAL_ROOT_MOTION_WINDOW_PHASES: Array[String] = ["align", "prepare", "execute_contact", "recover"]

var current_phase := "idle"
var active_attempt_id := ""
var active_controller_grant_id := ""
var active_connection_epoch := 0
var active_outcome_nonce := ""
var local_ownership_restored := true
var selected_realization_route := ""
var selected_action_atoms: Array[Dictionary] = []
var phase_action_atoms: Dictionary = {}
var trace_events: Array[Dictionary] = []
var active_playback_adapter: Node
var realtime_attempt_active := false
var realtime_request: Dictionary = {}
var realtime_grant: Dictionary = {}
var realtime_registry_binding: Dictionary = {}
var realtime_next_phase_index := 0


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


func run_attempt(
	request: Dictionary,
	grant: Dictionary,
	registry_binding: Dictionary,
	scenario: String = "success",
	action_asset_registry: CharacterEmbodimentAssetRegistry = null,
	playback_adapter: Node = null
) -> Dictionary:
	# Every request owns its local playback binding, including failed preflight.
	active_playback_adapter = playback_adapter
	var allowed := can_start_attempt(request, grant)
	if not bool(allowed.get("accepted", false)):
		return _terminal_outcome(request, grant, registry_binding, "failed_precondition", str(allowed.get("error_code", "")), false)
	active_attempt_id = str(request.get("interaction_attempt_id", ""))
	active_controller_grant_id = str(grant.get("grant_id", ""))
	active_connection_epoch = int(grant.get("connection_epoch", 0))
	active_outcome_nonce = str(grant.get("one_time_outcome_nonce", ""))
	selected_realization_route = str(request.get("realization_route", ""))
	selected_action_atoms.clear()
	phase_action_atoms.clear()
	if action_asset_registry != null:
		var action_selection := select_action_atoms(request, action_asset_registry)
		if str(action_selection.get("status", "")) != "available":
			return _terminal_outcome(
				request,
				grant,
				registry_binding,
				"failed_precondition",
				"action_assets_unavailable",
				false
			)
	elif _has_requested_action_atoms(request):
		return _terminal_outcome(
			request,
			grant,
			registry_binding,
			"failed_precondition",
			"action_assets_unavailable",
			false
		)
	local_ownership_restored = false
	trace_events.clear()
	current_phase = "idle"
	for phase: String in ORDERED_PHASES:
		if phase == "terminal":
			break
		var playback := _enter_phase(phase)
		if not bool(playback.get("accepted", false)):
			return _terminal_outcome(
				request,
				grant,
				registry_binding,
				"failed_precondition",
				"local_playback_unavailable",
				false
			)
		var terminal := _terminal_for_scenario(scenario, phase)
		if terminal != "":
			return _terminal_outcome(request, grant, registry_binding, terminal, _failure_for_terminal(terminal, scenario), terminal == "contact_observed")
	return _terminal_outcome(request, grant, registry_binding, "contact_observed", "", true)


func start_realtime_attempt(
	request: Dictionary,
	grant: Dictionary,
	registry_binding: Dictionary,
	action_asset_registry: CharacterEmbodimentAssetRegistry = null,
	playback_adapter: Node = null
) -> Dictionary:
	active_playback_adapter = playback_adapter
	var allowed := can_start_attempt(request, grant)
	if not bool(allowed.get("accepted", false)):
		return _terminal_outcome(request, grant, registry_binding, "failed_precondition", str(allowed.get("error_code", "")), false)
	active_attempt_id = str(request.get("interaction_attempt_id", ""))
	active_controller_grant_id = str(grant.get("grant_id", ""))
	active_connection_epoch = int(grant.get("connection_epoch", 0))
	active_outcome_nonce = str(grant.get("one_time_outcome_nonce", ""))
	selected_realization_route = str(request.get("realization_route", ""))
	selected_action_atoms.clear()
	phase_action_atoms.clear()
	if action_asset_registry != null:
		var action_selection := select_action_atoms(request, action_asset_registry)
		if str(action_selection.get("status", "")) != "available":
			return _terminal_outcome(request, grant, registry_binding, "failed_precondition", "action_assets_unavailable", false)
	elif _has_requested_action_atoms(request):
		return _terminal_outcome(request, grant, registry_binding, "failed_precondition", "action_assets_unavailable", false)
	local_ownership_restored = false
	trace_events.clear()
	current_phase = "idle"
	realtime_attempt_active = true
	realtime_request = request.duplicate(true)
	realtime_grant = grant.duplicate(true)
	realtime_registry_binding = registry_binding.duplicate(true)
	realtime_next_phase_index = 0
	return {
		"accepted": true,
		"interaction_attempt_id": active_attempt_id,
		"phase": current_phase,
	}


func advance_realtime_attempt(phase: String) -> Dictionary:
	if not realtime_attempt_active:
		return {"accepted": false, "error_code": "realtime_attempt_inactive"}
	if realtime_next_phase_index >= ORDERED_PHASES.size() - 1:
		return {"accepted": false, "error_code": "realtime_phase_exhausted"}
	var expected_phase := str(ORDERED_PHASES[realtime_next_phase_index])
	if phase != expected_phase:
		return {"accepted": false, "error_code": "realtime_phase_out_of_order", "expected_phase": expected_phase}
	var playback := _enter_phase(phase)
	if not bool(playback.get("accepted", false)):
		return finish_realtime_attempt("failed_precondition", "local_playback_unavailable", false)
	realtime_next_phase_index += 1
	return {
		"accepted": true,
		"phase": phase,
		"trace_event": trace_events.back().duplicate(true),
	}


func finish_realtime_attempt(
	terminal_status: String,
	failure_code: String = "",
	contact_observed: bool = false,
	contact_observation_override: Dictionary = {},
	object_observation_override: Dictionary = {}
) -> Dictionary:
	var request := realtime_request if not realtime_request.is_empty() else {
		"interaction_attempt_id": active_attempt_id,
	}
	var grant := realtime_grant if not realtime_grant.is_empty() else {
		"grant_id": active_controller_grant_id,
		"connection_epoch": active_connection_epoch,
		"one_time_outcome_nonce": active_outcome_nonce,
	}
	var outcome := _terminal_outcome(
		request,
		grant,
		realtime_registry_binding,
		terminal_status,
		failure_code,
		contact_observed
	)
	if contact_observed:
		# Realtime callers must explicitly attest any world observation; the legacy
		# terminal helper's chair claim is not valid for the door contact handoff.
		outcome.erase("object_observation")
		if not contact_observation_override.is_empty():
			outcome["contact_observation"] = contact_observation_override.duplicate(true)
		if not object_observation_override.is_empty():
			outcome["object_observation"] = object_observation_override.duplicate(true)
	realtime_attempt_active = false
	realtime_request.clear()
	realtime_grant.clear()
	realtime_registry_binding.clear()
	realtime_next_phase_index = 0
	return outcome


func select_action_atoms(request: Dictionary, action_asset_registry: CharacterEmbodimentAssetRegistry) -> Dictionary:
	var realization_metadata: Dictionary = request.get("skill_realization_metadata", {})
	if realization_metadata.is_empty():
		realization_metadata = request.get("realization_metadata", {})
	var selection := action_asset_registry.resolve_action_atoms(
		realization_metadata.get("primitive_action_tags", []),
		realization_metadata.get("primitive_realization_keys", [])
	)
	selected_action_atoms.clear()
	for atom: Dictionary in selection.get("selected_action_atoms", []):
		selected_action_atoms.append(atom.duplicate(true))
	return selection


func _has_requested_action_atoms(request: Dictionary) -> bool:
	var realization_metadata: Dictionary = request.get("skill_realization_metadata", {})
	if realization_metadata.is_empty():
		realization_metadata = request.get("realization_metadata", {})
	return not realization_metadata.get("primitive_action_tags", []).is_empty() \
		or not realization_metadata.get("primitive_realization_keys", []).is_empty()


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


func _enter_phase(phase: String) -> Dictionary:
	current_phase = phase
	var local_atoms := _select_phase_action_atoms(phase)
	if local_atoms.is_empty():
		phase_action_atoms.erase(phase)
	else:
		phase_action_atoms[phase] = local_atoms
	var playback_result := {"accepted": true, "status": "not_configured"}
	if active_playback_adapter != null:
		if not active_playback_adapter.has_method("begin_phase"):
			return {"accepted": false, "status": "local_playback_unavailable"}
		playback_result = active_playback_adapter.call("begin_phase", phase, local_atoms)
		if not bool(playback_result.get("accepted", false)):
			return {"accepted": false, "status": "local_playback_unavailable"}
	trace_events.append({
		"interaction_attempt_id": active_attempt_id,
		"phase": phase,
		"trace_ref": "local_phase:%s:%s" % [active_attempt_id, phase],
		"selected_action_tags": _action_tags_for_atoms(local_atoms),
		"local_root_motion_profiles": _local_root_motion_profiles(phase, local_atoms),
		"local_execution_only": true,
	})
	return playback_result


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
	if current_phase != "recover":
		_enter_phase("recover")
	if active_playback_adapter != null and active_playback_adapter.has_method("restore_local_ownership"):
		active_playback_adapter.call("restore_local_ownership")
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
		"selected_action_tags": _selected_action_tags(),
		"phase_action_tags": _phase_action_tags(),
		"local_root_motion_phase_refs": _local_root_motion_phase_refs(),
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


func _selected_action_tags() -> Array[String]:
	return _action_tags_for_atoms(selected_action_atoms)


func _select_phase_action_atoms(phase: String) -> Array[Dictionary]:
	var allowed_tags: Array = PHASE_ACTION_TAGS.get(phase, [])
	var phase_atoms: Array[Dictionary] = []
	for atom: Dictionary in selected_action_atoms:
		if allowed_tags.has(str(atom.get("action_tag", ""))):
			phase_atoms.append(atom.duplicate(true))
	return phase_atoms


func _action_tags_for_atoms(atoms: Array[Dictionary]) -> Array[String]:
	var action_tags: Array[String] = []
	for atom: Dictionary in atoms:
		var action_tag := str(atom.get("action_tag", ""))
		if not action_tag.is_empty():
			action_tags.append(action_tag)
	return action_tags


func _local_root_motion_profiles(phase: String, atoms: Array[Dictionary]) -> Array[String]:
	if not LOCAL_ROOT_MOTION_WINDOW_PHASES.has(phase):
		return []
	var profiles: Array[String] = []
	for atom: Dictionary in atoms:
		var profile := str(atom.get("root_motion_profile", ""))
		if not profile.is_empty():
			profiles.append(profile)
	return profiles


func _phase_action_tags() -> Dictionary:
	var result := {}
	for phase: String in phase_action_atoms:
		result[phase] = _action_tags_for_atoms(phase_action_atoms[phase])
	return result


func _local_root_motion_phase_refs() -> Dictionary:
	var result := {}
	for phase: String in phase_action_atoms:
		var profiles := _local_root_motion_profiles(phase, phase_action_atoms[phase])
		if not profiles.is_empty():
			result[phase] = profiles
	return result


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
