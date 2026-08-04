extends Node

const MIRROR_BRIDGE := preload("res://scripts/interaction/GameplayMirrorBridge.gd")
const MIRROR_CONSUMER := preload("res://scripts/interaction/GameplayRuntimeStateMirrorConsumer.gd")
const VERIFICATION_ROOT := "res:/" + "/.harness/verification/"

var _mirror_bridge: GameplayMirrorBridge
var _consumer: GameplayRuntimeStateMirrorConsumer
var _scenario_id := ""
var _expected_initial_state := ""
var _expected_final_state := ""
var _actor_ref := ""
var _group_id := ""
var _initial_facade_revision := ""
var _initial_snapshot_seen := false
var _finished := false


func _ready() -> void:
	_scenario_id = OS.get_environment("PARALLS_ADVENTURE_BASIC_MIRROR_SCENARIO")
	_expected_initial_state = OS.get_environment("PARALLS_ADVENTURE_BASIC_MIRROR_INITIAL_STATE")
	_expected_final_state = OS.get_environment("PARALLS_ADVENTURE_BASIC_MIRROR_FINAL_STATE")
	_group_id = "adventure.basic.%s" % _scenario_id
	if _scenario_id.is_empty() or _expected_initial_state.is_empty() or _expected_final_state.is_empty():
		_finish(false, "scenario_expectation_missing")
		return
	var bus := get_node_or_null("/root/LocalPresentationBus")
	if bus == null:
		_finish(false, "presentation_bus_missing")
		return
	bus.backend_connected.connect(_on_backend_connected)
	bus.websocket_session_bound_received.connect(_on_session_bound)
	bus.backend_ack_received.connect(_on_backend_ack)
	bus.gameplay_runtime_state_projection_received.connect(_on_projection)
	bus.gameplay_mirror_delivery_received.connect(_on_delivery)
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
		_finish(false, "adventure_basic_live_delivery_timeout")


func _on_backend_connected(_url: String) -> void:
	if _mirror_bridge.bind_session() != OK:
		_finish(false, "bind_send_failed")


func _on_session_bound(payload: Dictionary) -> void:
	var scope: Variant = payload.get("allowed_actor_refs", [])
	if typeof(scope) != TYPE_ARRAY or (scope as Array).size() != 1:
		_finish(false, "authorized_scope_invalid")
		return
	_actor_ref = str((scope as Array)[0])
	if _actor_ref != "character:char_player":
		_finish(false, "authorized_actor_invalid")
		return
	_mirror_bridge.register_consumer(_actor_ref, _consumer)
	call_deferred("_subscribe_bound_actor")


func _subscribe_bound_actor() -> void:
	if _mirror_bridge.request_subscription(_actor_ref) != OK:
		_finish(false, "subscribe_send_failed")


func _on_backend_ack(payload: Dictionary) -> void:
	if str(payload.get("source_type", "")) == "gameplay_mirror_subscribe" and not bool(payload.get("accepted", false)):
		_finish(false, "subscribe_denied:%s" % str(payload.get("error_code", "unknown")))


func _on_projection(payload: Dictionary) -> void:
	if _initial_snapshot_seen or str(payload.get("actor_ref", "")) != _actor_ref:
		return
	call_deferred("_observe_initial_projection")


func _observe_initial_projection() -> void:
	if _finished or _initial_snapshot_seen:
		return
	var presentation_state := _presentation_state()
	if presentation_state != _expected_initial_state:
		_finish(false, "initial_presentation_state_invalid:%s" % presentation_state)
		return
	_initial_snapshot_seen = true
	_initial_facade_revision = _consumer.facade_revision
	_write_ready()


func _on_delivery(payload: Dictionary) -> void:
	if str(payload.get("actor_ref", "")) != _actor_ref or not _initial_snapshot_seen:
		return
	await get_tree().process_frame
	if _finished:
		return
	var presentation_state := _presentation_state()
	if _consumer.resync_required or _consumer.rejected_projection_count > 0:
		_finish(false, "delivery_stream_invalid")
		return
	if presentation_state != _expected_final_state:
		return
	var accepted := _consumer.accepted_projection_count >= 2 \
		and _consumer.connection_epoch >= 1 \
		and _consumer.last_delivery_sequence >= 1 \
		and presentation_state == _expected_final_state \
		and _consumer.facade_revision != _initial_facade_revision
	_finish(accepted, "committed_delivery_observed" if accepted else "final_delivery_invariant_invalid")


func _presentation_state() -> String:
	var group: Variant = _consumer.visible_groups.get(_group_id, {})
	if typeof(group) != TYPE_DICTIONARY:
		return ""
	var payload: Variant = (group as Dictionary).get("payload", {})
	if typeof(payload) != TYPE_DICTIONARY:
		return ""
	return str((payload as Dictionary).get("presentation_state", ""))


func _write_ready() -> void:
	var path := ProjectSettings.globalize_path(VERIFICATION_ROOT + "live-adventure-basic-mirror-ready.json")
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify({
			"status": "ready",
			"scenario_id": _scenario_id,
			"actor_ref": _actor_ref,
			"group_id": _group_id,
			"presentation_state": _presentation_state(),
			"facade_revision": _consumer.facade_revision,
		}))
		file.close()


func _finish(ok: bool, reason: String) -> void:
	if _finished:
		return
	_finished = true
	var report := {
		"status": "live_adventure_basic_mirror_verified" if ok else "live_adventure_basic_mirror_failed",
		"reason": reason,
		"scenario_id": _scenario_id,
		"actor_ref": _actor_ref,
		"group_id": _group_id,
		"initial_snapshot_seen": _initial_snapshot_seen,
		"expected_initial_state": _expected_initial_state,
		"expected_final_state": _expected_final_state,
		"presentation_state": _presentation_state(),
		"initial_facade_revision": _initial_facade_revision,
		"facade_revision": _consumer.facade_revision,
		"connection_epoch": _consumer.connection_epoch,
		"last_delivery_sequence": _consumer.last_delivery_sequence,
		"accepted_projection_count": _consumer.accepted_projection_count,
		"rejected_projection_count": _consumer.rejected_projection_count,
		"resync_required": _consumer.resync_required,
	}
	var path := ProjectSettings.globalize_path(VERIFICATION_ROOT + "live-adventure-basic-mirror-runtime.json")
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(report, "\t"))
		file.close()
	print("live_adventure_basic_mirror_delivery_probe:verified=%s" % str(ok).to_lower())
	get_tree().quit(0 if ok else 1)
