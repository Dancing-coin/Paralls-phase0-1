extends Node

const MIRROR_BRIDGE := preload("res://scripts/interaction/GameplayMirrorBridge.gd")
const MIRROR_CONSUMER := preload("res://scripts/interaction/GameplayRuntimeStateMirrorConsumer.gd")
const VERIFICATION_ROOT := "res:/" + "/.harness/verification/"

var _mirror_bridge: GameplayMirrorBridge
var _consumer: GameplayRuntimeStateMirrorConsumer
var _actor_ref := ""
var _initial_snapshot_seen := false
var _finished := false
var _reconnecting := false
var _first_epoch := 0
var _first_actor_ref := ""
var _cleared_after_disconnect := false
var _reconnect_bound_epoch := 0
var _scenario := "reconnect"
var _backpressure_control_seen := false


func _ready() -> void:
	_scenario = OS.get_environment("PARALLS_LIVE_GAMEPLAY_MIRROR_PROBE_SCENARIO")
	var bus := get_node_or_null("/root/LocalPresentationBus")
	if bus == null:
		_finish(false, "presentation_bus_missing")
		return
	bus.backend_connected.connect(_on_backend_connected)
	bus.backend_disconnected.connect(_on_backend_disconnected)
	bus.websocket_session_bound_received.connect(_on_session_bound)
	bus.backend_ack_received.connect(_on_backend_ack)
	bus.gameplay_runtime_state_projection_received.connect(_on_projection)
	bus.gameplay_mirror_delivery_received.connect(_on_delivery)
	bus.gameplay_mirror_resync_required_received.connect(_on_resync_required)
	_mirror_bridge = MIRROR_BRIDGE.new()
	_consumer = MIRROR_CONSUMER.new()
	add_child(_mirror_bridge)
	add_child(_consumer)
	if _mirror_bridge.load_session_enrollment_from_environment() != OK:
		_finish(false, "enrollment_handoff_missing")
		return
	var backend := get_node_or_null("/root/BackendBridge")
	if backend == null or backend.connect_to_backend(OS.get_environment("PARALLS_BACKEND_WS_URL")) != OK:
		_finish(false, "backend_connect_failed")
		return
	await get_tree().create_timer(25.0).timeout
	if not _finished:
		_finish(false, "live_delivery_timeout")


func _on_backend_connected(_url: String) -> void:
	_write_stage("backend_connected")
	if _mirror_bridge.bind_session() != OK:
		_finish(false, "bind_send_failed")


func _on_backend_disconnected(_code: int) -> void:
	_write_stage("backend_disconnected")
	if _reconnecting and not _finished:
		call_deferred("_after_backend_disconnected")


func _after_backend_disconnected() -> void:
	_cleared_after_disconnect = _consumer.actor_ref.is_empty() and _consumer.visible_groups.is_empty()
	await _wait_for_reconnect_enrollment()


func _on_session_bound(payload: Dictionary) -> void:
	_write_stage("session_bound")
	if _reconnecting:
		_reconnect_bound_epoch = int(payload.get("connection_epoch", 0))
	var scope: Variant = payload.get("allowed_actor_refs", [])
	if typeof(scope) != TYPE_ARRAY or (scope as Array).is_empty():
		_finish(false, "scope_missing")
		return
	_actor_ref = str((scope as Array)[0])
	_mirror_bridge.register_consumer(_actor_ref, _consumer)
	call_deferred("_subscribe_bound_actor")


func _subscribe_bound_actor() -> void:
	if _mirror_bridge.request_subscription(_actor_ref) != OK:
		_finish(false, "subscribe_send_failed")
		return
	_write_stage("subscription_sent")


func _on_backend_ack(payload: Dictionary) -> void:
	if str(payload.get("source_type", "")) != "gameplay_mirror_subscribe":
		return
	if not bool(payload.get("accepted", false)):
		_finish(false, "subscribe_denied:%s" % str(payload.get("error_code", "unknown")))


func _on_projection(payload: Dictionary) -> void:
	if str(payload.get("actor_ref", "")) != _actor_ref:
		return
	_initial_snapshot_seen = true
	if _scenario == "gap" and _consumer.rejected_projection_count > 0:
		call_deferred("_finish_gap_resync")
		return
	if _scenario == "backpressure" and _backpressure_control_seen:
		call_deferred("_finish_backpressure_resync")
		return
	if _reconnecting:
		_write_stage("reconnect_projection")
		call_deferred("_finish_reconnect_projection")
		return
	_write_ready()
	_write_stage("initial_projection")


func _finish_reconnect_projection() -> void:
	_finish(
		_reconnect_bound_epoch > _first_epoch
		and _cleared_after_disconnect
		and _actor_ref != _first_actor_ref
		and _consumer.actor_ref == _actor_ref,
		"fresh_enrollment_reconnect_narrowed_scope_recovered"
	)


func _finish_gap_resync() -> void:
	await get_tree().process_frame
	_finish(
		not _consumer.resync_required
		and _consumer.actor_ref == _actor_ref
		and _consumer.accepted_projection_count >= 2,
		"gap_resync_scoped_snapshot_recovered"
	)


func _on_resync_required(payload: Dictionary) -> void:
	if _scenario == "backpressure" and str(payload.get("actor_ref", "")) == _actor_ref:
		_backpressure_control_seen = true


func _finish_backpressure_resync() -> void:
	await get_tree().process_frame
	_finish(
		_backpressure_control_seen
		and not _consumer.resync_required
		and _consumer.actor_ref == _actor_ref,
		"backpressure_scoped_snapshot_recovered"
	)


func _on_delivery(payload: Dictionary) -> void:
	if str(payload.get("actor_ref", "")) != _actor_ref or not _initial_snapshot_seen:
		return
	await get_tree().process_frame
	if _scenario != "reconnect":
		return
	var entries: Dictionary = _consumer.visible_groups.get("core.resources", {}).get("payload", {}).get("entries", {})
	var stamina: Dictionary = entries.get("core.stamina", {})
	if _consumer.connection_epoch < 1 or _consumer.last_delivery_sequence < 1 or int(stamina.get("current", -1)) != 6:
		_finish(false, "after_commit_delivery_invalid")
		return
	_first_epoch = _consumer.connection_epoch
	_first_actor_ref = _actor_ref
	_write_first_delivery()
	_reconnecting = true
	var backend := get_node_or_null("/root/BackendBridge")
	if backend == null:
		_finish(false, "backend_missing_before_reconnect")
		return
	backend.close_backend_connection()
	_write_stage("disconnect_requested")


func _wait_for_reconnect_enrollment() -> void:
	var handoff_path := OS.get_environment("PARALLS_GAMEPLAY_MIRROR_RECONNECT_ENROLLMENT_PATH")
	if handoff_path.is_empty():
		_finish(false, "reconnect_handoff_path_missing")
		return
	var deadline := Time.get_ticks_msec() + 12000
	while Time.get_ticks_msec() < deadline:
		if FileAccess.file_exists(handoff_path):
			var file := FileAccess.open(handoff_path, FileAccess.READ)
			var parsed: Variant = JSON.parse_string(file.get_as_text()) if file != null else null
			if typeof(parsed) == TYPE_DICTIONARY:
				_mirror_bridge.set_session_enrollment(parsed as Dictionary)
				var backend := get_node_or_null("/root/BackendBridge")
				if backend != null and backend.connect_to_backend(OS.get_environment("PARALLS_BACKEND_WS_URL")) == OK:
					_write_stage("reconnect_requested")
					return
		await get_tree().create_timer(0.1).timeout
	_finish(false, "reconnect_enrollment_handoff_timeout")


func _write_ready() -> void:
	var path := ProjectSettings.globalize_path(VERIFICATION_ROOT + "live-gameplay-mirror-ready.json")
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify({"status": "ready", "actor_ref": _actor_ref}))
		file.close()


func _write_first_delivery() -> void:
	var path := ProjectSettings.globalize_path(VERIFICATION_ROOT + "live-gameplay-mirror-first-delivery.json")
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify({"status": "first_delivery", "actor_ref": _actor_ref, "connection_epoch": _first_epoch}))
		file.close()


func _write_stage(stage: String) -> void:
	var path := ProjectSettings.globalize_path(VERIFICATION_ROOT + "live-gameplay-mirror-stage.json")
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify({"stage": stage}))
		file.close()


func _finish(ok: bool, reason: String) -> void:
	if _finished:
		return
	_finished = true
	var report := {
		"status": ("live_gap_resync_verified" if _scenario == "gap" else "live_backpressure_isolation_verified" if _scenario == "backpressure" else "live-gameplay-mirror-delivery-verified") if ok else "live-gameplay-mirror-delivery-failed",
		"reason": reason,
		"scenario": _scenario,
		"actor_ref": _actor_ref,
		"initial_snapshot_seen": _initial_snapshot_seen,
		"connection_epoch": _consumer.connection_epoch,
		"last_delivery_sequence": _consumer.last_delivery_sequence,
		"accepted_projection_count": _consumer.accepted_projection_count,
		"rejected_projection_count": _consumer.rejected_projection_count,
		"resync_required": _consumer.resync_required,
		"first_connection_epoch": _first_epoch,
		"first_actor_ref": _first_actor_ref,
		"cleared_after_disconnect": _cleared_after_disconnect,
		"reconnect_bound_epoch": _reconnect_bound_epoch,
		"facade_revision": _consumer.facade_revision,
	}
	var path := ProjectSettings.globalize_path(VERIFICATION_ROOT + "live-gameplay-mirror-runtime.json")
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(report, "\t"))
		file.close()
	print("live_gameplay_mirror_delivery_probe:verified=%s" % str(ok).to_lower())
	get_tree().quit(0 if ok else 1)
