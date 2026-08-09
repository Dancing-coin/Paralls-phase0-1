extends Node

class_name ArchiveDoorEmbodiedActionHost

const ACTION_CONTROLLER := preload("res://scripts/interaction/EmbodiedActionController.gd")
const PLAYBACK_ADAPTER := preload("res://scripts/interaction/EmbodiedActionPlaybackAdapter.gd")
const ACTION_ASSET_REGISTRY := preload("res://scripts/character/CharacterEmbodimentAssetRegistry.gd")
const ACTION_ATOM_CATALOG := preload("res://scripts/character/DefaultSceneActionAtomCatalog.gd")
const PHASE0_PLAYER_BRIDGE := preload("res://scripts/player/Phase0PlayerBridge.gd")

const OBJECT_ID := "obj_archive_door"
const AFFORDANCE_ID := "affordance:obj_archive_door:open"
const STANCE_TOLERANCE_M := 0.12
const FACING_TOLERANCE_RAD := 0.10
const CONTACT_TOLERANCE_M := 0.08
const IK_SOLVER_SETTLE_PHYSICS_TICKS := 6
const CUSTOM_REACH_SETTLE_PHYSICS_TICKS := 30
const CONTACT_SETTLE_TIMEOUT_MS := 750

@export_node_path("Node") var player_bridge_path := NodePath("../Phase0InputBridge")
@export_node_path("Node") var character_replica_path := NodePath("../CharacterReplica")
@export_node_path("Node") var door_bridge_path := NodePath("../../DefaultSceneArchiveDoorAffordanceBridge")

var _controller = ACTION_CONTROLLER.new()
var _playback_adapter = PLAYBACK_ADAPTER.new()
var _action_asset_registry = ACTION_ASSET_REGISTRY.new()
var _active := false
var _awaiting_authority_result := false
var _request: Dictionary = {}
var _grant: Dictionary = {}
var _registry_binding: Dictionary = {}
var _pending_submission: Dictionary = {}
var _pending_authority_attempt: Dictionary = {}
var _source_sequence := 0
var _stage := "idle"
var _stance_lease_ref := ""
var _received_action_request_count := 0
var _last_transition := "idle"
var _last_error_code := ""
var _last_contact_measurement: Dictionary = {}
var _contact_process_count := 0
var _fallback_reach_requested := false
var _ik_solver_settle_ticks := 0
var _custom_reach_requested := false
var _custom_reach_settle_ticks := 0
var _contact_started_at_ms := 0


func _ready() -> void:
	ACTION_ATOM_CATALOG.register_into(_action_asset_registry)
	_playback_adapter.configure_playback_host(_character_replica())
	var bus := _get_bus()
	if bus == null:
		return
	if bus.has_signal("embodied_action_request_received"):
		bus.embodied_action_request_received.connect(_on_embodied_action_request_received)
	if bus.has_signal("archive_door_request_registered"):
		bus.archive_door_request_registered.connect(_on_archive_door_request_registered)
	if bus.has_signal("world_result_received"):
		bus.world_result_received.connect(_on_world_result_received)
	if bus.has_signal("embodied_settlement_result_received"):
		bus.embodied_settlement_result_received.connect(_on_embodied_settlement_result_received)
	if bus.has_signal("embodied_cancel_directive_received"):
		bus.embodied_cancel_directive_received.connect(_on_embodied_cancel_directive_received)
	if bus.has_signal("embodied_resync_projection_received"):
		bus.embodied_resync_projection_received.connect(_on_embodied_resync_projection_received)


func _physics_process(_delta: float) -> void:
	if not _active:
		return
	if _stage == "navigate":
		_process_navigate()
	elif _stage == "align":
		_process_align()
	elif _stage == "contact":
		_process_contact()


func _on_archive_door_request_registered(payload: Dictionary) -> void:
	if str(payload.get("target_object_id", "")) != OBJECT_ID:
		return
	if str(payload.get("interaction_type", "")) != "open":
		return
	_pending_submission = payload.duplicate(true)


func _on_embodied_action_request_received(payload: Dictionary) -> void:
	_received_action_request_count += 1
	if _active or _awaiting_authority_result:
		_set_runtime_status("action_request_ignored_active")
		return
	var request: Variant = payload.get("request", {})
	var grant: Variant = payload.get("grant", {})
	if not (request is Dictionary) or not (grant is Dictionary):
		_set_runtime_status("action_request_invalid_payload")
		return
	if str(request.get("target_ref", "")) != OBJECT_ID:
		_set_runtime_status("action_request_ignored_target")
		return
	if str(request.get("affordance_id", "")) != AFFORDANCE_ID:
		_set_runtime_status("action_request_ignored_affordance")
		return
	_set_runtime_status("action_request_accepted")
	_begin_attempt(request, grant)


func _on_world_result_received(payload: Dictionary) -> void:
	if str(payload.get("result_type", "")) != "constraint_state_result":
		return
	if str(payload.get("target_object_id", "")) != OBJECT_ID:
		return
	if _pending_submission.is_empty():
		return
	if str(payload.get("correlation_id", "")) != str(_pending_submission.get("correlation_id", "")):
		return
	recover_without_grant(str(payload.get("constraint_code", "preflight_rejected")))


func _on_embodied_settlement_result_received(payload: Dictionary) -> void:
	if not _matches_pending_authority(payload):
		return
	var outcome := str(payload.get("outcome", ""))
	var settlement_status := str(payload.get("settlement_status", ""))
	var error_code := str(payload.get("error_code", "authority_settlement_rejected"))
	if outcome == "committed" or settlement_status == "applied":
		_pending_authority_attempt.clear()
		_awaiting_authority_result = false
		return
	_recover_after_authority_result(error_code)
	if error_code == "binding_revision_mismatch" or error_code == "door_state_stale" or error_code == "revision_conflict":
		_emit_resync_request(error_code)


func _on_embodied_cancel_directive_received(payload: Dictionary) -> void:
	if not _active and not _matches_pending_authority(payload):
		return
	_recover_after_authority_result(str(payload.get("reason", "authority_cancelled")))


func _on_embodied_resync_projection_received(payload: Dictionary) -> void:
	if not _active and _pending_authority_attempt.is_empty():
		return
	_recover_after_authority_result(str(payload.get("reason", "authority_grant_required_after_resync")))


func _begin_attempt(request: Dictionary, grant: Dictionary) -> void:
	var bridge := _door_bridge()
	if bridge == null or not bridge.has_method("runtime_binding"):
		_set_runtime_status("registry_binding_unavailable", "registry_binding_unavailable")
		recover_without_grant("registry_binding_unavailable")
		return
	_registry_binding = bridge.runtime_binding()
	if _registry_binding.is_empty():
		_set_runtime_status("registry_binding_unavailable", "registry_binding_unavailable")
		recover_without_grant("registry_binding_unavailable")
		return
	_request = request.duplicate(true)
	_request["realization_metadata"] = {
		"primitive_action_tags": ["start_move", "turn_to_target", "raise_hand", "tap_contact", "recover_balance"],
	}
	_grant = grant.duplicate(true)
	_source_sequence = 0
	_last_contact_measurement.clear()
	_contact_process_count = 0
	_fallback_reach_requested = false
	_ik_solver_settle_ticks = 0
	_custom_reach_requested = false
	_custom_reach_settle_ticks = 0
	_contact_started_at_ms = 0
	var started: Dictionary = _controller.start_realtime_attempt(
		_request,
		_grant,
		{
			"entity_ref": OBJECT_ID,
			"binding_revision": int(_request.get("binding_revision", 0)),
			"local_binding": {"collider_refs": ["collider:obj_archive_door:body"]},
		},
		_action_asset_registry,
		_playback_adapter,
	)
	if not bool(started.get("accepted", false)):
		var start_error := str(started.get("error_code", "local_phase_rejected"))
		_set_runtime_status("controller_start_rejected", start_error)
		recover_without_grant(start_error)
		return
	_pending_submission.clear()
	_active = true
	if not _advance_phase("acquire_target"):
		_set_runtime_status("initial_phase_rejected", "local_phase_rejected")
		_finalize_local_failure("failed_precondition", "local_phase_rejected")
		return
	var player := get_parent() as CharacterBody3D
	var attempt_id := str(_request.get("interaction_attempt_id", ""))
	if player == null:
		_set_runtime_status("player_body_unavailable", "player_body_unavailable")
		_finalize_local_failure("failed_navigation", "player_body_unavailable")
		return
	if bridge == null or not bridge.has_method("reserve_stance_lease") or not bool(bridge.call("reserve_stance_lease", player, attempt_id)):
		_set_runtime_status("stance_occupied", "stance_occupied")
		_finalize_local_failure("failed_precondition", "stance_occupied")
		return
	_stance_lease_ref = attempt_id
	if not _advance_phase("reserve_stance") or not _advance_phase("plan_approach") or not _advance_phase("navigate"):
		_set_runtime_status("initial_phase_rejected", "local_phase_rejected")
		_finalize_local_failure("failed_precondition", "local_phase_rejected")
		return
	_stage = "navigate"
	_set_runtime_status("navigate_started")


func _process_navigate() -> void:
	var stance := _registry_binding.get("approach_stance") as Marker3D
	var player := get_parent() as CharacterBody3D
	var player_bridge := _player_bridge()
	var bridge := _door_bridge()
	if stance == null or player == null or player_bridge == null:
		_finalize_local_failure("failed_navigation", "approach_stance_unavailable")
		return
	if bridge != null and bridge.has_method("is_approach_obstructed"):
		if bool(bridge.call("is_approach_obstructed", player.global_position, stance.global_position, [player])):
			_finalize_local_failure("failed_navigation", "approach_obstructed")
			return
	var offset := stance.global_position - player.global_position
	offset.y = 0.0
	if offset.length() > STANCE_TOLERANCE_M:
		player_bridge.set_forced_player_motion(offset.normalized(), true)
		return
	player_bridge.clear_forced_player_motion()
	if not _advance_phase("align"):
		_finalize_local_failure("failed_precondition", "local_phase_rejected")
		return
	var contact := _registry_binding.get("contact_anchor") as Marker3D
	if contact == null:
		_finalize_local_failure("failed_alignment", "contact_anchor_unavailable")
		return
	var facing := contact.global_position - player.global_position
	facing.y = 0.0
	if facing.length() <= 0.001:
		_finalize_local_failure("failed_alignment", "contact_anchor_invalid")
		return
	player_bridge.set_forced_facing_yaw(atan2(facing.x, facing.z))
	_stage = "align"


func _process_align() -> void:
	var player := get_parent() as CharacterBody3D
	if player == null:
		_finalize_local_failure("failed_alignment", "player_body_unavailable")
		return
	var contact := _registry_binding.get("contact_anchor") as Marker3D
	if contact == null:
		_finalize_local_failure("failed_alignment", "contact_anchor_unavailable")
		return
	var facing := contact.global_position - player.global_position
	facing.y = 0.0
	var desired_yaw := atan2(facing.x, facing.z)
	var player_bridge := _player_bridge()
	if player_bridge != null:
		player_bridge.set_forced_facing_yaw(desired_yaw)
	if absf(wrapf(player.rotation.y - desired_yaw, -PI, PI)) > FACING_TOLERANCE_RAD:
		return
	if player_bridge != null:
		player_bridge.clear_forced_facing_yaw()
	var replica := _character_replica()
	if replica == null or not replica.has_method("begin_right_hand_reach"):
		_finalize_local_failure("failed_alignment", "ik_chain_unavailable")
		return
	var reach_started: Variant = replica.call("begin_right_hand_reach", contact.global_position, CONTACT_TOLERANCE_M)
	if not (reach_started is Dictionary) or not bool((reach_started as Dictionary).get("available", false)):
		var error_code := "ik_chain_unavailable"
		if reach_started is Dictionary:
			error_code = str((reach_started as Dictionary).get("error_code", error_code))
		_finalize_local_failure("failed_alignment", error_code)
		return
	if not _advance_phase("prepare") or not _advance_phase("execute_contact"):
		_finalize_local_failure("failed_precondition", "local_phase_rejected")
		return
	_contact_started_at_ms = Time.get_ticks_msec()
	_stage = "contact"


func _process_contact() -> void:
	if not _active or _stage != "contact":
		return
	_contact_process_count += 1
	var contact := _registry_binding.get("contact_anchor") as Marker3D
	var replica := _character_replica()
	if contact == null or replica == null or not replica.has_method("measure_right_hand_to_anchor"):
		_finalize_local_failure("failed_alignment", "ik_chain_unavailable")
		return
	var measurement: Variant = replica.call("measure_right_hand_to_anchor", contact.global_position)
	if measurement is Dictionary:
		_last_contact_measurement = (measurement as Dictionary).duplicate(true)
	else:
		_last_contact_measurement = {"available": false, "error_code": "invalid_ik_measurement"}
	if not (measurement is Dictionary) or not bool((measurement as Dictionary).get("available", false)):
		var error_code := "ik_chain_unavailable"
		if measurement is Dictionary:
			error_code = str((measurement as Dictionary).get("error_code", error_code))
		_finalize_local_failure("failed_alignment", error_code)
		return
	var distance_m := float((measurement as Dictionary).get("distance_m", INF))
	var runtime_kind := str((measurement as Dictionary).get("runtime_kind", ""))
	var within_settle_window := _contact_started_at_ms > 0 and Time.get_ticks_msec() - _contact_started_at_ms < CONTACT_SETTLE_TIMEOUT_MS
	if runtime_kind == "skeleton_ik_3d" and _ik_solver_settle_ticks < IK_SOLVER_SETTLE_PHYSICS_TICKS and within_settle_window:
		_ik_solver_settle_ticks += 1
		return
	if runtime_kind == "archive_door_reach_modifier" and _custom_reach_settle_ticks < CUSTOM_REACH_SETTLE_PHYSICS_TICKS and within_settle_window:
		_custom_reach_settle_ticks += 1
		return
	if distance_m > CONTACT_TOLERANCE_M:
		if not _fallback_reach_requested and runtime_kind == "skeleton_ik_3d" and replica.has_method("begin_right_hand_modifier_reach"):
			var fallback_started: Variant = replica.call("begin_right_hand_modifier_reach", contact.global_position, CONTACT_TOLERANCE_M)
			if fallback_started is Dictionary and bool((fallback_started as Dictionary).get("available", false)):
				_fallback_reach_requested = true
				return
		if not _custom_reach_requested and runtime_kind == "skeleton_modifier_fallback" and replica.has_method("begin_archive_door_reach_modifier"):
			var custom_reach_started: Variant = replica.call("begin_archive_door_reach_modifier", contact.global_position, CONTACT_TOLERANCE_M)
			if custom_reach_started is Dictionary and bool((custom_reach_started as Dictionary).get("available", false)):
				_custom_reach_requested = true
				_custom_reach_settle_ticks = 0
				return
		_finalize_local_failure("failed_alignment", "ik_alignment_tolerance_exceeded")
		return
	if not _advance_phase("observe") or not _advance_phase("recover"):
		_finalize_local_failure("failed_precondition", "local_phase_rejected")
		return
	_finish_attempt("contact_observed", "", true, distance_m)


func _advance_phase(phase: String) -> bool:
	var result: Dictionary = _controller.advance_realtime_attempt(phase)
	if not bool(result.get("accepted", false)):
		_set_runtime_status("phase_rejected:%s" % phase, str(result.get("error_code", "local_phase_rejected")))
		return false
	_source_sequence += 1
	_set_runtime_status("phase:%s" % phase)
	var bus := _get_bus()
	if bus != null and bus.has_signal("embodied_phase_event_emitted"):
		bus.emit_signal("embodied_phase_event_emitted", {
			"grant_id": str(_grant.get("grant_id", "")),
			"connection_epoch": int(_grant.get("connection_epoch", 0)),
			"source_sequence": _source_sequence,
			"payload_digest": "sha256:archive-door:%s:%s" % [str(_request.get("interaction_attempt_id", "")), phase],
		})
	return true


func _finish_attempt(
	terminal_status: String,
	failure_code: String,
	contact_observed: bool,
	hand_alignment_error_m: float = INF
) -> void:
	_set_runtime_status("terminal:%s" % terminal_status, failure_code)
	_clear_local_ownership()
	var contact_observation := {}
	if contact_observed:
		contact_observation = {
			"contact_ref": "contact:%s" % str(_request.get("interaction_attempt_id", "")),
			"actor_contact_ref": "collider:char_c:hand_r",
			"target_collider_ref": "collider:obj_archive_door:body",
			"contact_window_ref": "window:archive_door:local",
			"observation_rule_ref": "observation_rule:archive_door_contact:v1",
			"hand_alignment_error_m": hand_alignment_error_m,
		}
	var outcome: Dictionary = _controller.finish_realtime_attempt(
		terminal_status,
		failure_code,
		contact_observed,
		contact_observation
	)
	outcome["terminal_sequence"] = _source_sequence + 1
	outcome["payload_digest"] = "sha256:archive-door-outcome:%s" % str(_request.get("interaction_attempt_id", ""))
	_pending_authority_attempt = {
		"interaction_attempt_id": str(_request.get("interaction_attempt_id", "")),
		"correlation_id": str(_request.get("correlation_id", "")),
	}
	_awaiting_authority_result = true
	var bus := _get_bus()
	if bus != null and bus.has_signal("embodied_local_outcome_emitted"):
		bus.emit_signal("embodied_local_outcome_emitted", outcome)
	_active = false
	_stage = "idle"
	_request.clear()
	_grant.clear()
	_registry_binding.clear()
	_stance_lease_ref = ""


func recover_without_grant(reason: String) -> void:
	_set_runtime_status("recovery_without_grant", reason)
	_clear_local_ownership()
	_play_recover_balance()
	_pending_submission.clear()
	_pending_authority_attempt.clear()
	_awaiting_authority_result = false
	_active = false
	_stage = "idle"
	_request.clear()
	_grant.clear()
	_registry_binding.clear()
	_source_sequence = 0
	if not reason.is_empty():
		_bus_log("archive_door_preflight_rejected:%s" % reason)


func _recover_after_authority_result(reason: String) -> void:
	_set_runtime_status("authority_recovery", reason)
	_clear_local_ownership()
	_play_recover_balance()
	_pending_authority_attempt.clear()
	_awaiting_authority_result = false
	_active = false
	_stage = "idle"
	_request.clear()
	_grant.clear()
	_registry_binding.clear()
	_source_sequence = 0
	if not reason.is_empty():
		_bus_log("archive_door_authority_recovery:%s" % reason)


func _finalize_local_failure(terminal_status: String, failure_code: String) -> void:
	_finish_attempt(terminal_status, failure_code, false)


func _clear_local_ownership() -> void:
	var player_bridge := _player_bridge()
	if player_bridge != null:
		player_bridge.clear_forced_player_motion()
		player_bridge.clear_forced_facing_yaw()
	var bridge := _door_bridge()
	var player := get_parent() as CharacterBody3D
	if bridge != null and bridge.has_method("release_stance_lease") and player != null:
		bridge.call("release_stance_lease", player, _stance_lease_ref)
	var replica := _character_replica()
	if replica != null and replica.has_method("clear_right_hand_reach"):
		replica.call("clear_right_hand_reach")
	_stance_lease_ref = ""


func _play_recover_balance() -> void:
	var selection: Dictionary = _action_asset_registry.resolve_action_atoms(["recover_balance"], [])
	var atoms: Array[Dictionary] = []
	for atom: Dictionary in selection.get("selected_action_atoms", []):
		atoms.append(atom.duplicate(true))
	if atoms.is_empty():
		return
	_playback_adapter.begin_phase("recover", atoms)
	_playback_adapter.restore_local_ownership()


func _emit_resync_request(reason: String) -> void:
	var bus := _get_bus()
	if bus == null or not bus.has_signal("embodied_resync_request_emitted"):
		return
	bus.emit_signal("embodied_resync_request_emitted", {
		"interaction_attempt_id": str(_pending_authority_attempt.get("interaction_attempt_id", "")),
		"reason": reason,
	})


func _matches_pending_authority(payload: Dictionary) -> bool:
	if _pending_authority_attempt.is_empty():
		return false
	var attempt_id := str(payload.get("interaction_attempt_id", ""))
	if not attempt_id.is_empty() and attempt_id == str(_pending_authority_attempt.get("interaction_attempt_id", "")):
		return true
	var correlation_id := str(payload.get("correlation_id", ""))
	return not correlation_id.is_empty() and correlation_id == str(_pending_authority_attempt.get("correlation_id", ""))


func _player_bridge() -> Node:
	return get_node_or_null(player_bridge_path)


func _character_replica() -> Node:
	return get_node_or_null(character_replica_path)


func _door_bridge() -> Node:
	return get_node_or_null(door_bridge_path)


func _get_bus() -> Node:
	return get_node_or_null("/root/LocalPresentationBus")


func _bus_log(message: String) -> void:
	var bus := _get_bus()
	if bus != null and bus.has_method("log_debug"):
		bus.log_debug(message)


func runtime_status() -> Dictionary:
	return {
		"received_action_request_count": _received_action_request_count,
		"active": _active,
		"awaiting_authority_result": _awaiting_authority_result,
		"stage": _stage,
		"last_transition": _last_transition,
		"last_error_code": _last_error_code,
		"last_contact_measurement": _last_contact_measurement.duplicate(true),
		"contact_process_count": _contact_process_count,
	}


func _set_runtime_status(transition: String, error_code: String = "") -> void:
	_last_transition = transition
	_last_error_code = error_code
