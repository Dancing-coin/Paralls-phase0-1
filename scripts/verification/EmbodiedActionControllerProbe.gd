extends Node

const CONTROLLER := preload("res://scripts/interaction/EmbodiedActionController.gd")


func _ready() -> void:
	call_deferred("_run_probe")


func _run_probe() -> void:
	var controller = CONTROLLER.new()
	add_child(controller)
	var request := _request()
	var grant := _grant()
	var binding := _binding()
	var scenarios := ["success", "no_path", "miss", "fixed_target", "target_moved", "cancelled", "failed_alignment", "occupied_stance"]
	var outcomes := {}
	for scenario: String in scenarios:
		outcomes[scenario] = controller.run_attempt(request.duplicate(true), grant.duplicate(true), binding.duplicate(true), scenario)
	var probe_nodes: Dictionary = controller.build_runtime_probe_nodes()
	var expected_status := {
		"success": "contact_observed",
		"no_path": "failed_navigation",
		"miss": "missed_contact",
		"fixed_target": "failed_precondition",
		"target_moved": "interrupted",
		"cancelled": "aborted",
		"failed_alignment": "failed_alignment",
		"occupied_stance": "failed_precondition",
	}
	var ok := true
	for scenario: String in scenarios:
		var outcome: Dictionary = outcomes.get(scenario, {})
		ok = ok and str(outcome.get("terminal_status", "")) == str(expected_status[scenario])
		ok = ok and bool(outcome.get("local_ownership_restored", false))
		ok = ok and str(outcome.get("controller_grant_id", "")) != ""
		ok = ok and int(outcome.get("connection_epoch", 0)) == 1
		ok = ok and str(outcome.get("outcome_nonce", "")) != ""
	ok = ok and outcomes["success"].has("contact_observation")
	ok = ok and not outcomes["miss"].has("contact_observation")
	ok = ok and str(probe_nodes.get("navigation_agent_class", "")) == "NavigationAgent3D"
	ok = ok and str(probe_nodes.get("collision_shape_class", "")) == "CollisionShape3D"
	var report := {
		"status": "godot-runtime-embodied-action-controller-verified" if ok else "godot-runtime-embodied-action-controller-failed",
		"outcomes": outcomes,
		"probe_nodes": probe_nodes,
		"route_gate": {
			"selected_realization_route": controller.selected_realization_route,
			"legacy_character_actor_status_used": false,
		},
	}
	var report_path := _write_json(".harness/verification/embodied-action-controller-godot-runtime.json", report)
	print("embodied_action_controller_probe:artifact=%s" % report_path)
	print("embodied_action_controller_probe:verified=%s" % str(ok).to_lower())
	get_tree().quit(0 if ok else 1)


func _request() -> Dictionary:
	return {
		"request_id": "embodied_request:kick:1",
		"interaction_attempt_id": "attempt:kick-chair:runtime",
		"actor_id": "char_a",
		"target_ref": "entity:scene_demo:chair_01",
		"action_semantic": "kick",
		"affordance_id": "affordance:chair_01:kick",
		"authority_preflight_ref": "preflight:kick-chair:runtime",
		"policy_revision": 2,
		"scene_revision": 5,
		"binding_revision": 7,
		"required_anchor_roles": ["approach_stance", "contact"],
		"execution_profile_ref": "execution_profile:kick:v1",
		"expiration_tick": 2000,
		"causation_id": "cause:kick-chair:runtime",
		"correlation_id": "corr:kick-chair:runtime",
		"realization_route": "embodied_controller_v1",
		"settlement_writer_kind": "esm_compatibility_adapter",
	}


func _grant() -> Dictionary:
	return {
		"grant_id": "grant:kick-chair:runtime:1",
		"connection_epoch": 1,
		"one_time_outcome_nonce": "nonce:kick-chair:runtime",
	}


func _binding() -> Dictionary:
	return {
		"entity_ref": "entity:scene_demo:chair_01",
		"local_binding": {
			"collider_refs": ["collider:chair_01:body"],
		},
	}


func _write_json(relative_path: String, payload: Dictionary) -> String:
	var path := ProjectSettings.globalize_path("res://" + relative_path)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return ""
	file.store_string(JSON.stringify(payload, "\t"))
	file.close()
	return path
