extends Node

const MIRROR_BRIDGE := preload("res://scripts/interaction/GameplayMirrorBridge.gd")
const MIRROR_CONSUMER := preload("res://scripts/interaction/GameplayRuntimeStateMirrorConsumer.gd")


func _ready() -> void:
	call_deferred("_run_probe")


func _run_probe() -> void:
	var bridge = MIRROR_BRIDGE.new()
	var consumer = MIRROR_CONSUMER.new()
	add_child(bridge)
	add_child(consumer)
	bridge.register_consumer("actor:visible", consumer)
	var bus := get_node_or_null("/root/LocalPresentationBus")
	var ok := bus != null and bridge.bind_session() == ERR_UNCONFIGURED
	if bus:
		bus.emit_signal("websocket_session_bound_received", {
			"session_ref": "ws_session:probe",
			"allowed_actor_refs": ["actor:visible"],
		})
		bus.emit_signal("gameplay_runtime_state_projection_received", _projection("actor:hidden", "facade:hidden"))
		ok = ok and consumer.accepted_projection_count == 0
		bus.emit_signal("gameplay_runtime_state_projection_received", _projection("actor:visible", "facade:visible"))
		ok = ok and consumer.accepted_projection_count == 1
		ok = ok and consumer.actor_ref == "actor:visible"
		ok = ok and consumer.visible_groups.get("core.resources", {}).get("payload", {}).get("current", 0) == 7
		bus.emit_signal("backend_disconnected", 1006)
		ok = ok and consumer.actor_ref.is_empty()
		ok = ok and consumer.visible_groups.is_empty()
		ok = ok and not bridge.has_pending_enrollment()
		ok = ok and bridge.bind_session() == ERR_UNCONFIGURED
	var delivery_consumer = MIRROR_CONSUMER.new()
	var first_delivery := delivery_consumer.consume_delivery(_delivery(2, 1, "snapshot", "facade:delivery:1"))
	var duplicate_delivery := delivery_consumer.consume_delivery(_delivery(2, 1, "snapshot", "facade:delivery:1"))
	var next_epoch := delivery_consumer.consume_delivery(_delivery(3, 1, "snapshot", "facade:delivery:2"))
	var stale_epoch := delivery_consumer.consume_delivery(_delivery(2, 2, "snapshot", "facade:delivery:stale"))
	var forward_gap := delivery_consumer.consume_delivery(_delivery(3, 3, "snapshot", "facade:delivery:gap"))
	var delta_consumer = MIRROR_CONSUMER.new()
	var base_less_delta := delta_consumer.consume_delivery(_delivery(1, 1, "delta", "facade:delta"))
	var applied_delta_consumer = MIRROR_CONSUMER.new()
	var base_projection := _projection("actor:visible", "facade:delta:base")
	base_projection["snapshot_checksum"] = "sha256:base"
	base_projection["schema_capabilities"] = ["gameplay_runtime_state.godot.v1"]
	var base_snapshot := applied_delta_consumer.consume_delivery({
		"delivery_kind": "snapshot",
		"connection_epoch": 1,
		"delivery_sequence": 1,
		"payload": base_projection,
	})
	var changed_projection := _projection("actor:visible", "facade:delta:target")
	changed_projection["schema_capabilities"] = ["gameplay_runtime_state.godot.v1"]
	changed_projection["enabled_state_groups"] = ["core.status"]
	changed_projection["removed_group_ids"] = ["core.resources"]
	changed_projection["groups"] = {"core.status": {"payload": {"current": 2}}}
	var applied_delta := applied_delta_consumer.consume_delivery({
		"delivery_kind": "delta",
		"connection_epoch": 1,
		"delivery_sequence": 2,
		"base_facade_revision": "facade:delta:base",
		"base_snapshot_checksum": "sha256:base",
		"target_snapshot_checksum": "sha256:target",
		"payload": changed_projection,
	})
	ok = ok and bool(first_delivery.get("accepted", false))
	ok = ok and duplicate_delivery.get("error_code", "") == "mirror_sequence_duplicate"
	ok = ok and bool(next_epoch.get("accepted", false))
	ok = ok and stale_epoch.get("error_code", "") == "mirror_sequence_stale"
	ok = ok and forward_gap.get("error_code", "") == "mirror_sequence_gap"
	ok = ok and delivery_consumer.resync_required
	ok = ok and base_less_delta.get("error_code", "") == "mirror_delta_base_required"
	ok = ok and bool(base_snapshot.get("accepted", false))
	ok = ok and bool(applied_delta.get("accepted", false))
	ok = ok and applied_delta_consumer.facade_revision == "facade:delta:target"
	ok = ok and applied_delta_consumer.visible_groups.has("core.status") and not applied_delta_consumer.visible_groups.has("core.resources")
	var report := {
		"status": "godot-runtime-gameplay-mirror-bridge-verified" if ok else "godot-runtime-gameplay-mirror-bridge-failed",
		"accepted_projection_count": consumer.accepted_projection_count,
		"actor_ref_after_disconnect": consumer.actor_ref,
		"visible_groups_after_disconnect": consumer.visible_groups,
	}
	var artifact := _write_json(".harness/verification/gameplay-mirror-bridge-godot-runtime.json", report)
	print("gameplay_mirror_bridge_probe:artifact=%s" % artifact)
	print("gameplay_mirror_bridge_probe:verified=%s" % str(ok).to_lower())
	get_tree().quit(0 if ok else 1)


func _projection(actor_ref: String, facade_revision: String) -> Dictionary:
	return {
		"projection_kind": "gameplay_runtime_state.godot.v1",
		"actor_ref": actor_ref,
		"facade_revision": facade_revision,
		"groups": {"core.resources": {"payload": {"current": 7}}},
	}


func _delivery(epoch: int, sequence: int, delivery_kind: String, facade_revision: String) -> Dictionary:
	return {
		"delivery_kind": delivery_kind,
		"connection_epoch": epoch,
		"delivery_sequence": sequence,
		"payload": _projection("actor:visible", facade_revision),
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
