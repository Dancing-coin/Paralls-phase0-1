extends Node3D

## 外机真实渲染采集；计时只用于测量，所有角色状态来自现有WS。
const WARMUP_US := 10_000_000
const SAMPLE_US := 60_000_000

@onready var adapter: PopulationPresentationAdapter = $PopulationAdapter
@onready var presenter: PopulationPresenter = $PopulationPresenter
@onready var hud: Label = $HUD/Status

var _output_dir := ""
var _frames: FileAccess
var _messages: FileAccess
var _observations: FileAccess
var _stage := "waiting"
var _started_us := 0
var _ready_us := 0
var _sample_start_us := 0
var _warmup_us := 0
var _sample_duration_us := 0
var _previous_frame_us := 0
var _sample_count := 0
var _expected_population := 0
var _expected_actor_refs: Array[String] = []
var _visible_target := 0
var _first_tick := -1
var _last_tick := -1
var _first_actor := ""
var _first_members: Array = []
var _last_wire: Dictionary = {}
var _last_verified_wire: Dictionary = {}
var _last_verified_anchor: Dictionary = {}
var _bytes_by_kind: Dictionary = {}
var _rotation_complete := false
var _reconnect_complete := false
var _gap_seen := false
var _recovery_seen := false
var _reconnect_epoch := 0
var _finished := false


func _ready() -> void:
	_output_dir = OS.get_environment("PARALLS_POPULATION_EVIDENCE_DIR")
	_expected_population = int(OS.get_environment("PARALLS_POPULATION_EXPECTED_COUNT"))
	_visible_target = mini(160, _expected_population)
	if _output_dir.is_empty() or _expected_population not in [100, 1000, 10000]:
		_fail("probe_configuration_missing")
		return
	var roster_path := OS.get_environment("PARALLS_POPULATION_ROSTER_PATH")
	var roster: Variant = JSON.parse_string(FileAccess.get_file_as_string(roster_path)) if not roster_path.is_empty() else null
	if typeof(roster) != TYPE_DICTIONARY or typeof(roster.get("actor_ids")) != TYPE_ARRAY:
		_fail("expected_roster_missing")
		return
	for actor: Variant in roster["actor_ids"]:
		_expected_actor_refs.append("character:" + str(actor))
	_expected_actor_refs.sort()
	if _expected_actor_refs.size() != _expected_population:
		_fail("expected_roster_count_mismatch")
		return
	DirAccess.make_dir_recursive_absolute(_output_dir)
	_frames = FileAccess.open(_output_dir.path_join("frame-times.csv"), FileAccess.WRITE)
	_messages = FileAccess.open(_output_dir.path_join("messages.jsonl"), FileAccess.WRITE)
	_observations = FileAccess.open(_output_dir.path_join("observations.jsonl"), FileAccess.WRITE)
	if _frames == null or _messages == null or _observations == null:
		_fail("evidence_files_unavailable")
		return
	_frames.store_line("frame_index,elapsed_us,wall_frame_ms,process_ms,render_cpu_ms,render_gpu_ms,near,far,invisible,active_marker_count,confirmed_tick")
	_started_us = Time.get_ticks_usec()
	DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	RenderingServer.viewport_set_measure_render_time(get_viewport().get_viewport_rid(), true)
	if DisplayServer.get_name() == "headless" or RenderingServer.get_current_rendering_method() != "forward_plus" or DisplayServer.window_get_size() != Vector2i(1280, 720) or DisplayServer.window_get_vsync_mode() != DisplayServer.VSYNC_DISABLED:
		_fail("render_environment_mismatch")
		return
	adapter.population_applied.connect(_on_population_applied)
	adapter.subscription_failed.connect(func(_actor: String, reason: String): _fail(reason))
	var backend := get_node("/root/BackendBridge")
	backend.gameplay_mirror_packet_observed.connect(_on_packet)
	var bus := get_node("/root/LocalPresentationBus")
	bus.backend_disconnected.connect(_on_disconnected)
	bus.websocket_session_bound_received.connect(_on_bound)
	if not adapter.bridge.has_pending_enrollment():
		_fail("trusted_enrollment_missing")
		return
	_write_stage("connecting")
	if backend.connect_to_backend(OS.get_environment("PARALLS_BACKEND_WS_URL")) != OK:
		_fail("backend_connect_failed")


func _process(_delta: float) -> void:
	if _finished or _started_us == 0:
		return
	var now := Time.get_ticks_usec()
	if now - _started_us > 240_000_000:
		_fail("probe_timeout")
		return
	var counts := presenter.counts()
	if adapter._consumers.size() > 160 or int(counts["active_marker_count"]) > 160:
		_fail("presentation_capacity_exceeded")
		return
	if adapter.bridge.connection_gap_count > 0:
		_gap_seen = true
	if _gap_seen and _all_bases_ready():
		_recovery_seen = true
	hud.text = "人口 %d  ·  近景 %d / 远景 %d / 不可见 %d\n已确认 tick %d  ·  %s\n蓝色：闲暇   紫色：休息   金色：工作" % [_expected_population, counts["near"], counts["far"], counts["invisible"], presenter.latest_confirmed_tick, _stage]
	if _stage == "connecting" and _members_ready():
		_ready_us = now
		_first_tick = presenter.latest_confirmed_tick
		_first_members = adapter._consumers.keys()
		_first_actor = str(_first_members[0])
		_write_stage("warmup")
		_capture("before.png")
	elif _stage == "warmup" and now - _ready_us >= WARMUP_US:
		_sample_start_us = now
		_warmup_us = now - _ready_us
		_previous_frame_us = now
		_write_stage("sampling")
	elif _stage == "sampling":
		var rid := get_viewport().get_viewport_rid()
		_sample_count += 1
		_frames.store_line("%d,%d,%.6f,%.6f,%.6f,%.6f,%d,%d,%d,%d,%d" % [
			_sample_count, now - _sample_start_us, (now - _previous_frame_us) / 1000.0,
			Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0,
			RenderingServer.viewport_get_measured_render_time_cpu(rid), RenderingServer.viewport_get_measured_render_time_gpu(rid),
			counts["near"], counts["far"], counts["invisible"], counts["active_marker_count"], presenter.latest_confirmed_tick])
		_previous_frame_us = now
		if now - _sample_start_us >= SAMPLE_US:
			_frames.flush()
			_sample_duration_us = now - _sample_start_us
			_write_stage("capturing_after")
			if not await _capture("after.png"):
				return
			_write_stage("awaiting_lod_boundary")
	elif _stage == "awaiting_lod_boundary":
		var boundary := _read_boundary("authority-before.json")
		if not boundary.is_empty() and _members_at_tick(int(boundary["authority"]["confirmed_tick"])):
			_record_lod("before")
			_write_stage("rotating")
			if _expected_population == 100:
				$Camera.position.x = 15.0
				$Camera.look_at(Vector3.ZERO)
			if adapter.set_interest_window(32) != OK:
				_fail("interest_rotation_failed")
	elif _stage == "rotating" and _members_ready() and not presenter._lod_dirty and presenter._camera_position.is_equal_approx($Camera.global_position):
		var next_members: Array = adapter._consumers.keys()
		if _expected_population > 100 and next_members.has(_first_members[0]):
			_fail("invisible_member_rotation_failed")
			return
		_record_lod("after")
		_write_stage("lod_rotated")
	elif _stage == "lod_rotated":
		var boundary := _read_boundary("authority-after.json")
		if boundary.is_empty() or not bool(boundary.get("resumed_same_driver", false)):
			return
		_rotation_complete = true
		_reconnect_epoch = adapter.bridge._connection_epoch
		_write_stage("disconnecting")
		get_node("/root/BackendBridge").close_backend_connection()
	elif _stage == "disconnected":
		_try_reconnect()
	elif _stage == "reconnecting" and _members_ready():
		_reconnect_complete = adapter.bridge._connection_epoch > _reconnect_epoch
		_finish_capture()


func _members_ready() -> bool:
	var counts := presenter.counts()
	return adapter.allowed_actor_refs.size() == _expected_population and adapter._pending.is_empty() and adapter._operations.is_empty() and _all_bases_ready() and int(counts["near"]) == 32 and int(counts["far"]) == _visible_target - 32 and int(counts["invisible"]) == _expected_population - _visible_target


func _read_boundary(name: String) -> Dictionary:
	var path := _output_dir.path_join(name)
	if not FileAccess.file_exists(path):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed if parsed is Dictionary else {}


func _members_at_tick(tick: int) -> bool:
	if not _members_ready():
		return false
	for marker: MeshInstance3D in presenter._markers.values():
		var public: Dictionary = marker.get_meta("public_view", {})
		if int(public.get("confirmed_tick", -1)) != tick:
			return false
	return true


func _record_lod(name: String) -> void:
	var members: Array = presenter._markers.keys()
	var near_members: Array = presenter._near_labels.keys()
	members.sort()
	near_members.sort()
	_write_json("lod-" + name + ".json", {"members": members, "near_members": near_members,
		"counts": presenter.counts(), "confirmed_tick": presenter.latest_confirmed_tick,
		"elapsed_us": Time.get_ticks_usec() - _started_us,
		"camera_position": [$Camera.position.x, $Camera.position.y, $Camera.position.z]})


func _all_bases_ready() -> bool:
	if adapter._consumers.size() != _visible_target or presenter._markers.size() != _visible_target:
		return false
	for consumer: GameplayRuntimeStateMirrorConsumer in adapter._consumers.values():
		if consumer.resync_required or consumer.facade_revision.is_empty():
			return false
	return true


func _on_packet(raw_text: String, packet_bytes: int) -> void:
	if _messages == null or _finished:
		return
	var message: Dictionary = JSON.parse_string(raw_text)
	var payload: Dictionary = message.get("payload", {})
	var kind: String = str(payload.get("delivery_kind", message.get("message_type", "unknown")))
	_bytes_by_kind[kind] = int(_bytes_by_kind.get(kind, 0)) + packet_bytes
	_last_wire = {"connection_epoch": payload.get("connection_epoch"), "delivery_sequence": payload.get("delivery_sequence"), "actor_ref": payload.get("actor_ref")}
	_messages.store_line(JSON.stringify({"elapsed_us": Time.get_ticks_usec() - _started_us, "packet_bytes": packet_bytes, "raw_text": raw_text}))


func _on_population_applied(actor_ref: String, snapshot: Dictionary) -> void:
	if _observations == null or _finished:
		return
	# 原包只作为候选；只有 production adapter 真正应用后的对应 wire 才能成为截图来源。
	if str(_last_wire.get("actor_ref", "")) != actor_ref or int(_last_wire.get("connection_epoch", 0)) != adapter.bridge._connection_epoch or int(_last_wire.get("delivery_sequence", 0)) != adapter.bridge._last_delivery_sequence:
		_fail("verified_wire_anchor_mismatch")
		return
	_last_verified_wire = _last_wire.duplicate(true)
	_last_verified_anchor = {"wire": _last_verified_wire.duplicate(true), "actor_ref": actor_ref,
		"facade_revision": snapshot["facade_revision"],
		"confirmed_tick": snapshot["groups"]["population_public"]["payload"]["confirmed_tick"],
		"marker_update": presenter.applied_count}
	var observation: Dictionary = _last_verified_anchor.duplicate(true)
	observation["elapsed_us"] = Time.get_ticks_usec() - _started_us
	observation["stage"] = _stage
	_observations.store_line(JSON.stringify(observation))


func _on_bound(payload: Dictionary) -> void:
	var actual: Array = payload.get("allowed_actor_refs", []).duplicate()
	actual.sort()
	if actual != _expected_actor_refs:
		_fail("authorized_roster_mismatch")


func _on_disconnected(_code: int) -> void:
	if _stage != "disconnecting":
		_fail("unexpected_disconnect")
		return
	if not presenter._markers.is_empty() or not adapter._consumers.is_empty():
		_fail("disconnect_did_not_clear_presentation")
		return
	_write_stage("disconnected")


func _try_reconnect() -> void:
	var path := OS.get_environment("PARALLS_POPULATION_RECONNECT_ENROLLMENT_PATH")
	if path.is_empty() or not FileAccess.file_exists(path):
		return
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY:
		return
	adapter.bridge.set_session_enrollment(parsed)
	_write_stage("reconnecting")
	if get_node("/root/BackendBridge").connect_to_backend(OS.get_environment("PARALLS_BACKEND_WS_URL")) != OK:
		_fail("reconnect_failed")


func _capture(filename: String) -> bool:
	# 在绘制前锁定本帧已经验证的显示锚点；阶段隔离保证取图完成前不轮换 camera/成员。
	await RenderingServer.frame_pre_draw
	if _finished:
		return false
	var anchor: Dictionary = _last_verified_anchor.duplicate(true)
	var counts: Dictionary = presenter.counts()
	var camera_position: Vector3 = $Camera.position
	if anchor.is_empty() or int(anchor["marker_update"]) != presenter.applied_count or int(anchor["confirmed_tick"]) != presenter.latest_confirmed_tick:
		_fail("screenshot_verified_anchor_missing")
		return false
	await RenderingServer.frame_post_draw
	if _finished:
		return false
	if int(anchor["marker_update"]) != presenter.applied_count or counts != presenter.counts() or camera_position != $Camera.position:
		_fail("screenshot_state_changed_during_draw")
		return false
	if get_viewport().get_texture().get_image().save_png(_output_dir.path_join(filename)) != OK:
		_fail("screenshot_failed")
		return false
	if filename == "before.png":
		_first_tick = int(anchor["confirmed_tick"])
	elif filename == "after.png":
		_last_tick = int(anchor["confirmed_tick"])
	anchor["elapsed_us"] = Time.get_ticks_usec() - _started_us
	anchor["screenshot"] = filename
	anchor["counts"] = counts
	anchor["camera_position"] = [camera_position.x, camera_position.y, camera_position.z]
	_observations.store_line(JSON.stringify(anchor))
	return true


func _write_stage(stage: String) -> void:
	_stage = stage
	_write_json("stage.json", {"stage": stage, "elapsed_us": Time.get_ticks_usec() - _started_us})


func _finish_capture() -> void:
	if _last_tick <= _first_tick or not _rotation_complete or not _reconnect_complete or not _recovery_seen:
		_fail("runtime_evidence_incomplete")
		return
	_finished = true
	_write_json("godot-capture.json", {"status": "captured", "godot_status": "godot_unverified",
		"reason": "等待外部runner核对原始帧、消息、截图与后端同边界证明",
		"population": _expected_population, "sample_count": _sample_count,
		"warmup_us": _warmup_us, "sample_duration_us": _sample_duration_us,
		"ready_elapsed_us": _ready_us - _started_us, "sample_start_elapsed_us": _sample_start_us - _started_us,
		"sample_end_elapsed_us": _sample_start_us + _sample_duration_us - _started_us,
		"capture_end_elapsed_us": Time.get_ticks_usec() - _started_us,
		"first_tick": _first_tick, "last_tick": _last_tick, "observed_actor": _first_actor,
		"gap_seen": _gap_seen, "resync_recovered": _recovery_seen, "rotation_complete": _rotation_complete, "reconnect_complete": _reconnect_complete,
		"application_packet_bytes": _bytes_by_kind, "ws_frame_bytes": null,
		"ws_frame_bytes_reason": "WebSocketPeer只暴露application packet，未测framing或压缩传输字节",
		"scene": scene_file_path, "godot_version": Engine.get_version_info(),
		"renderer": RenderingServer.get_current_rendering_method(), "driver": RenderingServer.get_current_rendering_driver_name(),
		"gpu": RenderingServer.get_video_adapter_name(), "resolution": [DisplayServer.window_get_size().x, DisplayServer.window_get_size().y],
		"vsync": DisplayServer.window_get_vsync_mode(), "counts": presenter.counts()})
	_close_files()
	get_tree().quit(0)


func _fail(reason: String) -> void:
	if _finished:
		return
	_finished = true
	if not _output_dir.is_empty():
		_write_json("godot-capture.json", {"status": "failed", "godot_status": "godot_unverified", "reason": reason})
	_close_files()
	push_error("population_probe:%s" % reason)
	get_tree().quit(1)


func _write_json(name: String, payload: Dictionary) -> void:
	var file := FileAccess.open(_output_dir.path_join(name), FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(payload, "\t"))
		file.close()


func _close_files() -> void:
	for file: FileAccess in [_frames, _messages, _observations]:
		if file != null:
			file.close()
