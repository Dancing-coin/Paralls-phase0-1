extends Node

const MIRROR_BRIDGE := preload("res://scripts/interaction/GameplayMirrorBridge.gd")

var _mirror_bridge: GameplayMirrorBridge
var _finished := false


func _ready() -> void:
	var bus := get_node_or_null("/root/LocalPresentationBus")
	if bus == null:
		_finish(false, {})
		return
	bus.backend_connected.connect(_on_backend_connected)
	bus.websocket_session_bound_received.connect(_on_session_bound)
	_mirror_bridge = MIRROR_BRIDGE.new()
	add_child(_mirror_bridge)
	if _mirror_bridge.load_session_enrollment_from_environment() != OK:
		_finish(false, {})
		return
	var backend := get_node_or_null("/root/BackendBridge")
	if backend == null:
		_finish(false, {})
		return
	if backend.connect_to_backend(OS.get_environment("PARALLS_BACKEND_WS_URL")) != OK:
		_finish(false, {})
		return
	await get_tree().create_timer(10.0).timeout
	if not _finished:
		_finish(false, {})


func _on_backend_connected(_url: String) -> void:
	if _mirror_bridge.bind_session() != OK:
		_finish(false, {})


func _on_session_bound(payload: Dictionary) -> void:
	if str(payload.get("session_ref", "")).is_empty():
		_finish(false, {})
		return
	var scope: Array = payload.get("allowed_actor_refs", [])
	_finish(not scope.is_empty(), {"allowed_actor_refs": scope})


func _finish(ok: bool, details: Dictionary) -> void:
	if _finished:
		return
	_finished = true
	var report := {
		"status": "trusted-local-gameplay-mirror-live-bind-verified" if ok else "trusted-local-gameplay-mirror-live-bind-failed",
		"scope_granted": details.get("allowed_actor_refs", []),
	}
	var path := ProjectSettings.globalize_path("res://.harness/verification/trusted-local-gameplay-mirror-launch-runtime.json")
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(report, "\t"))
		file.close()
	print("trusted_local_gameplay_mirror_launch_probe:verified=%s" % str(ok).to_lower())
	get_tree().quit(0 if ok else 1)
