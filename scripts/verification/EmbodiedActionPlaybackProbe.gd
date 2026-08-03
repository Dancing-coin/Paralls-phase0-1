extends Node

const ACTION_ASSET_REGISTRY := preload("res://scripts/character/CharacterEmbodimentAssetRegistry.gd")
const ACTION_CATALOG := preload("res://scripts/character/DefaultSceneActionAtomCatalog.gd")
const CONTROLLER := preload("res://scripts/interaction/EmbodiedActionController.gd")
const PLAYBACK_ADAPTER := preload("res://scripts/interaction/EmbodiedActionPlaybackAdapter.gd")
const KNIGHT_ROLE_SKIN := preload("res://scenes/phase0/KnightRoleSkin.tscn")


func _ready() -> void:
	call_deferred("_run_probe")


func _run_probe() -> void:
	var skin := KNIGHT_ROLE_SKIN.instantiate()
	add_child(skin)
	var registry = ACTION_ASSET_REGISTRY.new()
	var catalog_result: Dictionary = ACTION_CATALOG.register_into(registry)
	var adapter = PLAYBACK_ADAPTER.new()
	adapter.configure_playback_host(skin)
	add_child(adapter)
	var controller = CONTROLLER.new()
	add_child(controller)
	var outcome: Dictionary = controller.run_attempt(_request(), _grant(), _binding(), "success", registry, adapter)
	var phase_trace_count_before_rejected_route: int = adapter.phase_playback_trace.size()
	var rejected_route_request := _request()
	rejected_route_request["realization_route"] = "legacy_character_replica"
	var rejected_route_outcome: Dictionary = controller.run_attempt(
		rejected_route_request,
		_grant(),
		_binding(),
		"success",
		registry
	)
	var adapter_not_reused_after_route_rejection: bool = adapter.phase_playback_trace.size() == phase_trace_count_before_rejected_route
	var phase_playback: Array = adapter.phase_playback_trace
	var expected_phases := ["plan_approach", "align", "prepare", "execute_contact", "recover"]
	var observed_phases: Array[String] = []
	for entry: Dictionary in phase_playback:
		if not entry.get("action_tags", []).is_empty():
			observed_phases.append(str(entry.get("phase", "")))
	var report := {
		"status": "godot-runtime-embodied-action-playback-verified",
		"catalog_result": catalog_result,
		"outcome": outcome,
		"rejected_route_outcome": rejected_route_outcome,
		"adapter_not_reused_after_route_rejection": adapter_not_reused_after_route_rejection,
		"phase_playback": phase_playback,
		"skin_clip_after_recovery": skin.get_current_clip_name(),
		"local_ownership_restored": adapter.local_ownership_restored,
	}
	var ok: bool = str(catalog_result.get("status", "")) == "available" \
		and str(outcome.get("terminal_status", "")) == "contact_observed" \
		and observed_phases == expected_phases \
		and skin.get_current_clip_name() == "idle_guard" \
		and adapter.local_ownership_restored \
		and adapter_not_reused_after_route_rejection \
		and not outcome.has("settlement_ref")
	var report_path := _write_json(".harness/verification/embodied-action-playback-godot-runtime.json", report)
	print("embodied_action_playback_probe:artifact=%s" % report_path)
	print("embodied_action_playback_probe:verified=%s" % str(ok).to_lower())
	get_tree().quit(0 if ok else 1)


func _request() -> Dictionary:
	return {
		"interaction_attempt_id": "attempt:default-scene:playback",
		"actor_id": "char_c",
		"target_ref": "entity:scene_demo:chair_01",
		"binding_revision": 1,
		"causation_id": "cause:default-scene:playback",
		"correlation_id": "corr:default-scene:playback",
		"realization_route": "embodied_controller_v1",
		"skill_realization_metadata": {
			"primitive_action_tags": ["start_move", "turn_to_target", "raise_hand", "tap_contact", "recover_balance"],
			"primitive_realization_keys": ["look_at_target"],
		},
	}


func _grant() -> Dictionary:
	return {"grant_id": "grant:default-scene:playback", "connection_epoch": 1, "one_time_outcome_nonce": "nonce:default-scene:playback"}


func _binding() -> Dictionary:
	return {"entity_ref": "entity:scene_demo:chair_01", "local_binding": {"collider_refs": ["collider:chair_01:body"]}}


func _write_json(relative_path: String, payload: Dictionary) -> String:
	var path := ProjectSettings.globalize_path("res://" + relative_path)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return ""
	file.store_string(JSON.stringify(payload, "\t"))
	file.close()
	return path
