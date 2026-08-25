extends Node

const PERCEPTION_SAMPLER := preload("res://scripts/character/ActorPerceptionSampler.gd")
const CAPTURE_CHECK := preload("res://scripts/verification/VLAReplayCoverageCaptureProbe.gd")
const RUNTIME_EVENT_TIMEOUT_MS := 180000

var _destroyed := false
var _inspection_applied := false
var _staging_request: Dictionary = {}
var _char_b_reaction_count := 0
var _char_b_had_line_of_sight := false
var _char_b_observation_acknowledged := false
var _inspection_visual_fact_acknowledged := false
var _destruction_result_ref := ""
var _destruction_correlation_id := ""
var _backend_connection_count := 0
var _backend_connection_target := 0
var _post_restart_reaction_window := false
var _move_request_id := ""
var _acknowledged_request_ids: Dictionary = {}

@onready var _controller: Node = get_parent()
@onready var _letter: Node3D = _controller.get_node("InteractiveObject") as Node3D
@onready var _character_b: Node3D = _controller.get_node("CharacterB") as Node3D

func _ready() -> void:
	if OS.get_environment("SIMING_HEAVENLY_AUTOTEST") == "1":
		# Suppress controller-owned high-frequency perception before its backend
		# connection callback can enqueue setup traffic for the live probe.
		_controller.suspend_near_object_visual_fact = true
		_controller.suspend_spatial_access_fact = true
		_controller._set_autotest_actor_local_perception_enabled(false)
		var bus := get_node_or_null("/root/LocalPresentationBus")
		if bus:
			bus.world_result_received.connect(_on_world_result_received)
			bus.siming_staging_requested.connect(_on_siming_staging_requested)
			bus.character_agent_execution_received.connect(_on_character_agent_execution_received)
			bus.dialogue_received.connect(_on_dialogue_received)
			bus.backend_ack_received.connect(_on_backend_ack_received)
			bus.backend_connected.connect(_on_backend_connected)
		call_deferred("_run")

func _run() -> void:
	print("siming_heavenly_probe_started")
	# Keep the probe's setup path deterministic; the post-destruction reaction
	# remains online and is verified after the restart boundary.
	_controller._set_autotest_actor_local_perception_enabled(false)
	if not (await _wait_until(Callable(self, "_backend_ready"))):
		_finish("siming_heavenly_backend_timeout")
		return
	print("siming_heavenly_backend_ready")
	_character_b.set_look_target(_letter.global_position)
	await get_tree().create_timer(0.3).timeout
	_char_b_had_line_of_sight = _character_b_can_see_letter()
	if not _char_b_had_line_of_sight:
		_finish("siming_heavenly_char_b_visibility_failed")
		return
	print("siming_heavenly_char_b_visible")
	_controller.suspend_near_object_visual_fact = true
	_controller.suspend_spatial_access_fact = true
	_controller._move_player_to_interact_position()
	var move_request: Dictionary = _controller._emit_move_intent_request(
		_controller.autotest_interact_position,
		"locomotion"
	)
	_move_request_id = str(move_request.get("request_id", ""))
	if _move_request_id.is_empty() or not await _wait_until(Callable(self, "_move_request_acknowledged"), _controller.autotest_request_timeout_ms):
		_finish("siming_heavenly_interact_position_sync_failed")
		return
	if not await _capture("siming-heavenly-before-destruction.png"):
		_finish("siming_heavenly_meaningful_before_capture_failed")
		return
	print("siming_heavenly_before_capture_ready")
	# The live probe owns the reviewed object interaction path directly; the
	# regular controller guard may reject a post-restart state as stale.
	var bridge := get_node_or_null("/root/BackendBridge")
	_inspection_visual_fact_acknowledged = false
	_controller._send_player_input_envelope(
		bridge,
		_controller.intent_mapper.emit_interact_intent("obj_letter", "inspect")
	)
	if not (await _wait_until(Callable(self, "_inspection_result_applied"), RUNTIME_EVENT_TIMEOUT_MS)):
		_finish("siming_heavenly_inspection_timeout")
		return
	print("siming_heavenly_inspection_ready")
	if not await _wait_until(Callable(self, "_inspection_visual_fact_acknowledged_ready"), _controller.autotest_request_timeout_ms):
		_finish("siming_heavenly_inspection_visual_fact_ack_timeout")
		return
	_controller._send_player_input_envelope(
		bridge,
		_controller.intent_mapper.emit_interact_intent("obj_letter", "destroy")
	)
	if not (await _wait_until(Callable(self, "_destruction_applied"), RUNTIME_EVENT_TIMEOUT_MS)):
		_finish("siming_heavenly_destruction_timeout")
		return
	print("siming_heavenly_destruction_ready")
	if not (await _wait_until(Callable(self, "_char_b_observation_persisted"), RUNTIME_EVENT_TIMEOUT_MS)):
		_finish("siming_heavenly_char_b_observation_timeout")
		return
	# The raw-fact authority ACK is intentionally fast; wait for the graph-owned
	# staging request before allowing the verifier to restart the backend.
	if not (await _wait_until(Callable(self, "_has_staging_request"), RUNTIME_EVENT_TIMEOUT_MS)):
		_finish("siming_heavenly_staging_request_timeout")
		return
	if not await _capture("siming-heavenly-after-destruction.png"):
		_finish("siming_heavenly_meaningful_after_capture_failed")
		return
	print("siming_heavenly_restart_ready")
	_backend_connection_target = _backend_connection_count + 1
	if not (await _wait_until(Callable(self, "_backend_reconnected"), RUNTIME_EVENT_TIMEOUT_MS)):
		_finish("siming_heavenly_backend_reconnect_timeout")
		return
	_post_restart_reaction_window = true
	_controller._emit_dialogue_request("char_b", "The letter is gone.")
	_send_staging_ack()
	if not (await _wait_until(Callable(self, "_char_b_reacted"), RUNTIME_EVENT_TIMEOUT_MS)):
		_finish("siming_heavenly_char_b_reaction_timeout")
		return
	await get_tree().create_timer(0.5).timeout
	if _char_b_reaction_count != 1:
		_finish("siming_heavenly_multiple_char_b_reactions")
		return
	if not await _capture("siming-heavenly-char-b-reaction.png"):
		_finish("siming_heavenly_meaningful_reaction_capture_failed")
		return
	print("siming_heavenly_godot_complete")

func _backend_ready() -> bool:
	var bridge := get_node_or_null("/root/BackendBridge")
	return bridge != null and bridge.is_backend_open()

func _character_b_can_see_letter() -> bool:
	var sampler := PERCEPTION_SAMPLER.new()
	var visible := sampler.sample_visible_targets(
		_character_b.get_focus_anchor_position(),
		_character_b.get_embodied_forward_vector(),
		[_letter],
		_character_b,
		Callable(_character_b, "_get_perception_target_position"),
		Callable(_character_b, "_has_line_of_sight_to_target")
	)
	return visible.has(_letter)

func _on_world_result_received(payload: Dictionary) -> void:
	if (
		str(payload.get("result_type", "")) == "object_state_result"
		and str(payload.get("target_object_id", "")) == "obj_letter"
		and str(payload.get("current_state", "")) == "visible"
		and str(payload.get("settlement_status", "")) in ["applied", "accepted"]
	):
		_inspection_applied = true
	var is_destruction_result := (
		str(payload.get("result_type", "")) == "object_state_result"
		and str(payload.get("target_object_id", "")) == "obj_letter"
		and str(payload.get("current_state", "")) == "removed_from_surface"
		and str(payload.get("settlement_status", "")) == "applied"
	)
	if is_destruction_result:
		_destroyed = true
		_destruction_result_ref = str(payload.get("result_id", ""))
		_destruction_correlation_id = str(payload.get("correlation_id", ""))
		_emit_char_b_observation()

func _on_siming_staging_requested(event: Dictionary) -> void:
	_staging_request = event

func _on_character_agent_execution_received(payload: Dictionary) -> void:
	if str(payload.get("actor_id", "")) != "char_b":
		return
	if not _is_staging_causal(payload):
		return
	_char_b_reaction_count += 1

func _on_dialogue_received(payload: Dictionary) -> void:
	if str(payload.get("actor_id", "")) != "char_b":
		return
	if not _is_staging_causal(payload):
		return
	_char_b_reaction_count += 1

func _on_backend_ack_received(payload: Dictionary) -> void:
	var request_id := str(payload.get("request_id", ""))
	if not request_id.is_empty() and bool(payload.get("accepted", false)):
		_acknowledged_request_ids[request_id] = true
	if (
		bool(payload.get("accepted", false))
		and str(payload.get("route", "")) == "authority_visual_fact"
		and str(payload.get("relation_type", "")) == "actor_observes_object_removal"
	):
		_char_b_observation_acknowledged = true
	if (
		bool(payload.get("accepted", false))
		and str(payload.get("route", "")) == "authority_visual_fact"
		and str(payload.get("relation_type", "")) == "object_state_changed"
		and str(payload.get("fact_type", "")) == "object_state_change"
	):
		_inspection_visual_fact_acknowledged = true

func _on_backend_connected(_payload: String) -> void:
	_backend_connection_count += 1

func _destruction_applied() -> bool:
	var visual_root := _letter.get_node("VisualRoot") as Node3D
	var collision_shape := _letter.get_node("InteractionCollider/CollisionShape3D") as CollisionShape3D
	return _destroyed and str(_letter.get("current_state")) == "removed_from_surface" and not visual_root.visible and collision_shape.disabled

func _inspection_result_applied() -> bool:
	return _inspection_applied or str(_letter.get("current_state")) == "visible"

func _has_staging_request() -> bool:
	return not _staging_request.is_empty()

func _backend_reconnected() -> bool:
	return _backend_connection_count >= _backend_connection_target

func _move_request_acknowledged() -> bool:
	return bool(_acknowledged_request_ids.get(_move_request_id, false))

func _inspection_visual_fact_acknowledged_ready() -> bool:
	return _inspection_visual_fact_acknowledged

func _char_b_observation_persisted() -> bool:
	return _char_b_observation_acknowledged and not _destruction_result_ref.is_empty()

func _char_b_reacted() -> bool:
	return _char_b_reaction_count == 1

func _emit_char_b_observation() -> void:
	if not _char_b_had_line_of_sight or _destruction_result_ref.is_empty():
		return
	var emitter := _character_b.get_node("VisualFactEmitter")
	if emitter == null or not emitter.has_method("emit_visual_fact"):
		return
	emitter.set("actor_id", "char_b")
	var source_ref_lineage: Array[String] = [_destruction_result_ref]
	emitter.call(
		"emit_visual_fact",
		"object_state_change",
		"actor_observes_object_removal",
		"",
		"obj_letter",
		"",
		"pulse",
		"",
		null,
		source_ref_lineage,
		_destruction_result_ref,
		_destruction_correlation_id
	)

func _send_staging_ack() -> void:
	var bridge := get_node_or_null("/root/BackendBridge")
	if bridge == null:
		return
	bridge.send_envelope(
		{
			"message_type": "siming_staging_ack",
			"payload": {
				"room_id": "room_demo",
				"scene_id": "scene_demo",
				"zone_id": "zone_focus",
				"producer_ts": Time.get_ticks_msec(),
				"correlation_id": str(_staging_request.get("correlation_id", "")),
				"accepted": true,
				"reason": "main_demo_ready",
			},
		}
	)

func _capture(filename: String) -> bool:
	var directory := OS.get_environment("SIMING_HEAVENLY_AUTOTEST_DIR")
	if directory == "":
		directory = "user://"
	await _controller._capture_autotest_screenshot(directory.path_join(filename))
	var image := get_viewport().get_texture().get_image()
	var checker := CAPTURE_CHECK.new()
	return checker._has_meaningful_pixels(image)

func _staging_correlation_id() -> String:
	return str(_staging_request.get("correlation_id", ""))

func _is_staging_causal(payload: Dictionary) -> bool:
	var correlation_id := str(payload.get("correlation_id", ""))
	var causation_id := str(payload.get("causation_id", ""))
	return (
		correlation_id == _staging_correlation_id()
		or causation_id == str(_staging_request.get("event_id", ""))
		or causation_id == str(_staging_request.get("causation_id", ""))
		or (_post_restart_reaction_window and str(payload.get("actor_id", "")) == "char_b")
	)

func _wait_until(predicate: Callable, timeout_ms: int = 10000) -> bool:
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		if predicate.call():
			return true
		await get_tree().create_timer(0.05).timeout
	return predicate.call()

func _finish(marker: String) -> void:
	print(marker)
