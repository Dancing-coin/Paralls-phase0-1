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
	var ok := bus != null
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


func _write_json(relative_path: String, payload: Dictionary) -> String:
	var path := ProjectSettings.globalize_path("res://" + relative_path)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		return ""
	file.store_string(JSON.stringify(payload, "\t"))
	file.close()
	return path
