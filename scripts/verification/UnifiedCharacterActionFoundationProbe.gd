class_name UnifiedCharacterActionFoundationProbe
extends Node

const REPORT_PATH := ".harness/verification/unified-character-action-foundation-runtime.json"
const BACKEND_URL := "ws://127.0.0.1:8000/ws"

var _results: Array[Dictionary] = []
var _authority_results: Array[Dictionary] = []
var _acks: Array[Dictionary] = []
var _backend_url := ""

func _ready() -> void:
	_backend_url = OS.get_environment("PARALLS_BACKEND_WS_URL").strip_edges()
	if _backend_url.is_empty():
		_backend_url = BACKEND_URL
	call_deferred("_run_probe")

func _run_probe() -> void:
	var bus := get_node_or_null("/root/LocalPresentationBus")
	var bridge := get_node_or_null("/root/BackendBridge")
	if bus == null or bridge == null or not bus.has_signal("unified_character_action_foundation_result_received"):
		_fail("missing_backend_bridge_or_signal")
		return
	bus.unified_character_action_foundation_result_received.connect(_on_result)
	bus.backend_ack_received.connect(_on_ack)
	var connect_err: int = bridge.connect_to_backend(_backend_url)
	if connect_err != OK:
		_fail("connect_failed:%s" % connect_err)
		return
	var deadline := Time.get_ticks_msec() + 8000
	while Time.get_ticks_msec() < deadline and not bridge.is_backend_open():
		await get_tree().process_frame
	if not bridge.is_backend_open():
		_fail("connect_timeout")
		return

	var jk := get_node_or_null("../FemaleJKExternal") as CharacterBody3D
	var t := get_node_or_null("../FemaleTExternal") as CharacterBody3D
	if jk == null or t == null:
		_fail("missing_actors")
		return
	var before := {"foundation_jk": jk.global_position, "foundation_t": t.global_position}
	await _drive_actor(jk, "foundation_jk")
	await _drive_actor(t, "foundation_t")
	var after := {"foundation_jk": jk.global_position, "foundation_t": t.global_position}
	var package_ids := [str(jk.get_meta("package_id", "")), str(t.get_meta("package_id", ""))]

	var agent_intent := await _send_attempt(_attempt("agent:walk", "foundation_jk", "locomotion:walk", "agent_inf", "esm"))
	var melee := _attempt("player:melee", "foundation_jk", "melee:slash", "player", "esm")
	var melee_result := await _send_attempt(melee)
	var duplicate_result := await _send_attempt(melee)
	var stale_attempt := _attempt("stale:melee", "foundation_jk", "melee:slash", "player", "esm")
	stale_attempt["expected_revisions"] = {"actor:character:foundation_jk": 0}
	var stale_result := await _send_attempt(stale_attempt)
	var hitscan := _attempt("player:hitscan", "foundation_t", "hitscan:fire", "player", "gameplay")
	hitscan["weapon_ref"] = "weapon:semantic_rifle"
	var hitscan_result := await _send_attempt(hitscan)
	var invalid := await _send_raw({"package_ids": package_ids, "attempt": {"attempt_id": "invalid:client-truth", "actor_ref": "character:foundation_t", "action_instance_id": "invalid:1", "semantic_action_id": "hitscan:fire", "contact_marker_id": "marker:contact", "physics_tick": 1, "authority_route": "gameplay", "idempotency_key": "invalid:1", "command_version": "v1", "causation_id": "cause:invalid", "correlation_id": "corr:invalid", "source": "player", "privacy_scope": "public", "damage": 99}})

	var screenshot_path := _capture_screenshot()
	var report := {
		"status": "godot-runtime-unified-character-action-foundation-verified",
		"backend_connected": bridge.is_backend_open(), "backend_url": _backend_url,
		"package_reports": package_ids, "actor_count": 2,
		"shared_motor_owner": jk.get_node_or_null("CharacterMotor") != null and t.get_node_or_null("CharacterMotor") != null,
		"actor_motion_paths": {"foundation_jk": [before["foundation_jk"], after["foundation_jk"]], "foundation_t": [before["foundation_t"], after["foundation_t"]]},
		"agent_inf_intent_seen": _outcome(agent_intent) == "committed", "melee_attempt_seen": not melee_result.is_empty(),
		"melee_authority_committed": _outcome(melee_result) == "committed", "hitscan_authority_seen": _outcome(hitscan_result) == "committed",
		"duplicate_replayed": _transaction(duplicate_result) == _transaction(melee_result), "stale_rejected": _outcome(stale_result) == "rejected",
		"rejection_recovered": _outcome(invalid) == "rejected" or invalid.get("accepted") == false or str(invalid.get("error_code", "")).begins_with("invalid_action_attempt"),
		"attempts": [agent_intent, melee_result, duplicate_result, stale_result, hitscan_result, invalid], "authority_results": _authority_results,
		"mode": "B", "body_stream_seen": false, "runtime_capture_paths": [screenshot_path] if not screenshot_path.is_empty() else [],
	}
	var ok := bool(report["backend_connected"]) and bool(report["shared_motor_owner"]) and bool(report["agent_inf_intent_seen"]) and bool(report["melee_authority_committed"]) and bool(report["hitscan_authority_seen"]) and bool(report["duplicate_replayed"]) and bool(report["stale_rejected"]) and bool(report["rejection_recovered"])
	report["status"] = "godot-runtime-unified-character-action-foundation-verified" if ok else "godot-runtime-unified-character-action-foundation-failed"
	_write_report(report)
	for key in ["backend_connected", "melee_authority_committed", "hitscan_authority_seen", "duplicate_replayed", "stale_rejected"]:
		print("unified_character_action_foundation_probe:%s=%s" % [key, str(report[key]).to_lower()])
	print("unified_character_action_foundation_probe:package_ids=%s" % JSON.stringify(package_ids))
	print("unified_character_action_foundation_probe:verified=%s" % str(ok).to_lower())
	get_tree().quit(0 if ok else 1)

func _drive_actor(actor: CharacterBody3D, actor_ref: String) -> void:
	var motor := actor.get_node_or_null("CharacterMotor")
	if motor == null:
		return
	for _frame in range(12):
		motor.apply_intent_frame(actor, {"actor_id": actor_ref, "controller_source": "probe", "control_mode": "program_controlled", "move_local": Vector2(0, -1), "gait": "walk", "desired_facing_yaw": 0.0}, 1.0 / 60.0)
		await get_tree().process_frame

func _attempt(key: String, actor: String, action: String, source: String, route: String) -> Dictionary:
	var physics_tick := Time.get_ticks_msec()
	return {
		"attempt_id": "attempt:%s" % key,
		"actor_ref": "character:%s" % actor,
		"action_instance_id": "action:%s" % key,
		"semantic_action_id": action,
		"target_refs": ["object:foundation_target"],
		"contact_marker_id": "marker:contact",
		"physics_tick": physics_tick,
		"connection_epoch": 1,
		"client_sequence": _next_sequence(),
		"physics_evidence_refs": ["contact:probe"],
		"physics_evidence_digest": "sha256:" + "0".repeat(64),
		"action_descriptor_digest": "sha256:" + "1".repeat(64),
		"authority_route": route,
		"expected_revisions": {},
		"idempotency_key": "idempotency:%s" % key,
		"command_version": "v1",
		"causation_id": "cause:%s" % key,
		"correlation_id": "corr:%s" % key,
		"source": source,
		"privacy_scope": "public",
	}

var _attempt_sequence := 0

func _next_sequence() -> int:
	_attempt_sequence += 1
	return _attempt_sequence

func _send_attempt(attempt: Dictionary) -> Dictionary:
	return await _send_raw({"package_ids": ["female_jk_external", "female_t_external"], "attempt": attempt})

func _send_raw(payload: Dictionary) -> Dictionary:
	_results.clear()
	_acks.clear()
	var bridge := get_node_or_null("/root/BackendBridge")
	if bridge == null or bridge.send_envelope({"message_type": "unified_character_action_foundation_probe", "payload": payload}) != OK:
		return {"outcome": "rejected", "error_code": "send_failed"}
	var deadline := Time.get_ticks_msec() + 5000
	while Time.get_ticks_msec() < deadline and _results.is_empty() and _acks.is_empty():
		await get_tree().process_frame
	return _results[0] if not _results.is_empty() else (_acks[0] if not _acks.is_empty() else {"outcome": "unknown", "error_code": "timeout"})

func _on_result(payload: Dictionary) -> void:
	_results.append(payload)
	_authority_results.append(payload)

func _on_ack(payload: Dictionary) -> void:
	_acks.append(payload)

func _outcome(payload: Dictionary) -> String:
	var result: Variant = payload.get("authority_result", payload) if payload is Dictionary else {}
	return str(result.get("outcome", "")) if result is Dictionary else ""

func _transaction(payload: Dictionary) -> String:
	var result: Variant = payload.get("authority_result", payload) if payload is Dictionary else {}
	return str(result.get("transaction_id", "")) if result is Dictionary else ""

func _write_report(report: Dictionary) -> void:
	var path := ProjectSettings.globalize_path("res://" + REPORT_PATH)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(report, "\t"))
		file.close()

func _capture_screenshot() -> String:
	var path := ProjectSettings.globalize_path("res://.harness/verification/unified-character-action-foundation-runtime.png")
	var viewport_texture := get_viewport().get_texture()
	if viewport_texture != null:
		var image := viewport_texture.get_image()
		if image != null:
			if image.save_png(path) == OK:
				return path
	return ""

func _fail(code: String) -> void:
	_write_report({"status": "godot-runtime-unified-character-action-foundation-failed", "error_code": code, "mode": "B", "body_stream_seen": false})
	print("unified_character_action_foundation_probe:verified=false:%s" % code)
	get_tree().quit(1)
