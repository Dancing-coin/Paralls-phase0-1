extends Node3D

@export var backend_url := "ws://127.0.0.1:8000/ws"
@export var autotest_enabled := false
@export var focus_autotest_enabled := false
@export var autotest_dialogue_delay := 0.25
@export var autotest_interact_delay := 0.6
@export var autotest_capture_delay := 0.8
@export var autotest_final_position := Vector3(0.0, 0.5, 20.0)
@export var focus_autotest_settle_delay := 0.45
@export var focus_autotest_vantage_offset := Vector3(1.2, 0.5, 2.7)
@export var focus_max_distance := 28.0
@export var focus_forward_threshold := 0.2
@export var near_object_visual_fact_distance := 18.0
@export var near_object_visual_fact_cooldown_ms := 650

@onready var intent_mapper: Node = $IntentMapper
@onready var player: CharacterBody3D = $Player
@onready var player_input_bridge: Node = $Player/Phase0InputBridge
# A and B remain the current AI-driven scene actors.
@onready var character_a: Node3D = $CharacterA
@onready var character_b: Node3D = $CharacterB
# CharacterC is the first player-driven in-world role shell.
# The playable Player node remains the locomotion/camera shell for Phase 0.x.
@onready var character_c: Node3D = $CharacterC
@onready var interactive_object: Node3D = $InteractiveObject

var current_focus_target: Node3D
var last_reported_move_position := Vector3.INF
var pending_focus_sync := false
var last_debug_message := ""
var focus_override_active := false
var focus_response_seen := false
var backend_health_request: HTTPRequest
var last_near_object_visual_fact_target := ""
var last_near_object_visual_fact_ts := 0

func _ready() -> void:
	var bus := _get_bus()
	if bus:
		bus.backend_connected.connect(_on_backend_connected)
		bus.backend_ack_received.connect(_on_backend_ack_received)
		if bus.has_signal("debug_event_logged"):
			bus.debug_event_logged.connect(_on_debug_event_logged)
	backend_health_request = HTTPRequest.new()
	backend_health_request.name = "BackendHealthRequest"
	add_child(backend_health_request)
	backend_health_request.request_completed.connect(_on_backend_health_request_completed)
	_configure_open_field_camera()
	_bus_log("phase0_main_ready")
	autotest_enabled = OS.get_environment("PHASE0_AUTOTEST") == "1"
	focus_autotest_enabled = OS.get_environment("PHASE0_FOCUS_AUTOTEST") == "1"
	call_deferred("_connect_backend")

func _connect_backend() -> void:
	var bridge := _get_bridge()
	if bridge == null:
		_bus_log("phase0_backend_bridge_missing")
		return
	var err: int = bridge.connect_to_backend(backend_url)
	_bus_log("phase0_backend_connect_err:%s" % err)

func submit_dialogue(content: String = "phase0 manual test") -> void:
	var target_actor_id := _resolve_focused_actor_id()
	if target_actor_id == "":
		_bus_log("phase0_dialogue_no_focus_target")
		return
	var bridge := _get_bridge()
	if bridge:
		_bus_log("phase0_dialogue_target:%s" % target_actor_id)
		bridge.send_envelope(intent_mapper.emit_dialogue_submit(target_actor_id, content))

func submit_interaction() -> void:
	var target_object_id := _resolve_focused_object_id()
	if target_object_id == "":
		_bus_log("phase0_interact_no_focus_target")
		return
	var bridge := _get_bridge()
	if bridge:
		_bus_log("phase0_interact_target:%s" % target_object_id)
		_emit_near_object_visual_fact(target_object_id)
		bridge.send_envelope(intent_mapper.emit_interact_intent(target_object_id, "inspect"))

func _on_backend_connected(_payload: String) -> void:
	_request_backend_health()
	if pending_focus_sync:
		_emit_focus_target_change()
		pending_focus_sync = false
	if focus_autotest_enabled:
		_run_focus_autotest()
		return
	if autotest_enabled:
		_run_autotest_inputs()

func _on_backend_ack_received(payload: Dictionary) -> void:
	_bus_log("phase0_ack:%s" % JSON.stringify(payload))

func _on_debug_event_logged(message: String) -> void:
	last_debug_message = message
	if message.contains("focus_state_applied:char_a") or message.contains("focus_attention:char_a"):
		focus_response_seen = true

func _process(_delta: float) -> void:
	if focus_override_active:
		return
	_update_focus_target()
	_sample_near_object_visual_fact()

func _run_autotest_inputs() -> void:
	_bus_log("phase0_autotest_begin")
	focus_override_active = true
	_set_debug_overlay_visible(false)
	if player_input_bridge and player_input_bridge.has_method("set_character_c_sync_enabled"):
		player_input_bridge.set_character_c_sync_enabled(false)
	_orient_player_toward(character_a.global_position)
	_force_focus_target(character_a)
	await get_tree().create_timer(autotest_dialogue_delay).timeout
	player_input_bridge.trigger_dialogue()
	_orient_player_toward(interactive_object.global_position)
	_force_focus_target(interactive_object)
	await get_tree().create_timer(autotest_interact_delay).timeout
	player_input_bridge.trigger_interaction()
	await get_tree().create_timer(autotest_capture_delay).timeout
	_move_player_to_demo_vantage()
	_capture_autotest_screenshot()
	focus_override_active = false
	if player_input_bridge and player_input_bridge.has_method("set_character_c_sync_enabled"):
		player_input_bridge.set_character_c_sync_enabled(true)
	get_tree().quit()

func _run_focus_autotest() -> void:
	_bus_log("phase0_focus_autotest_begin")
	focus_response_seen = false
	_set_debug_overlay_visible(false)
	_move_player_to_focus_vantage(character_a.global_position)
	focus_override_active = true
	_force_focus_target(character_a)
	await _wait_for_focus_response()
	_capture_autotest_screenshot()
	get_tree().quit()

func _update_focus_target() -> void:
	var next_target := _pick_focus_target()
	if next_target == current_focus_target:
		return

	_set_focus_visual(current_focus_target, false)
	current_focus_target = next_target
	_set_focus_visual(current_focus_target, true)
	_emit_focus_target_change()

	if current_focus_target:
		_bus_log("phase0_focus:%s" % current_focus_target.name)

func _pick_focus_target() -> Node3D:
	# Keep focus/interaction candidates stable for the current Phase 0 loop:
	# A controls the key object, B observes, and the player-driven C shell is present
	# in-world but is not yet a separate focusable NPC target.
	var candidates: Array[Node3D] = [character_a, character_b, interactive_object]
	var player_origin := _get_focus_origin()
	var forward := _get_focus_forward()
	var best_target: Node3D
	var best_score := -1.0

	for candidate in candidates:
		if candidate == null:
			continue

		var offset := candidate.global_position - player_origin
		var distance := offset.length()
		if distance > focus_max_distance or distance <= 0.001:
			continue

		var direction := offset / distance
		var alignment := forward.dot(direction)
		if alignment < focus_forward_threshold:
			continue

		var score := alignment - distance * 0.05
		if score > best_score:
			best_score = score
			best_target = candidate

	return best_target

func _resolve_focused_actor_id() -> String:
	if current_focus_target == null:
		return ""
	var actor_value: Variant = current_focus_target.get("actor_id")
	if actor_value != null and str(actor_value) != "":
		return str(actor_value)
	return ""

func _resolve_focused_object_id() -> String:
	if current_focus_target == null:
		return ""
	var object_value: Variant = current_focus_target.get("object_id")
	if object_value != null and str(object_value) != "":
		return str(object_value)
	return ""

func _physics_process(_delta: float) -> void:
	_emit_move_intent_if_needed()

func _set_focus_visual(target: Node3D, is_focused: bool) -> void:
	if target and target.has_method("set_focus_highlight"):
		target.set_focus_highlight(is_focused)

func _force_focus_target(target: Node3D) -> void:
	_set_focus_visual(current_focus_target, false)
	current_focus_target = target
	_set_focus_visual(current_focus_target, true)
	_emit_focus_target_change()
	if current_focus_target:
		_bus_log("phase0_focus_forced:%s" % current_focus_target.name)

func _orient_player_toward(target_position: Vector3) -> void:
	var camera_holder := _get_camera_holder()
	var look_target := Vector3(target_position.x, player.global_position.y, target_position.z)
	var facing := look_target - player.global_position
	facing.y = 0.0
	if facing.length() > 0.001:
		var yaw := atan2(facing.x, facing.z)
		player.rotation.y = yaw
		if camera_holder:
			camera_holder.rotation.y = yaw
	_update_focus_target()

func _move_player_to_demo_vantage() -> void:
	player.global_position = autotest_final_position
	_orient_player_toward(interactive_object.global_position)
	var camera_holder := _get_camera_holder()
	if camera_holder:
		camera_holder.rotation.x = deg_to_rad(-22.0)
		var spring_arm := camera_holder.find_child("SpringArm3D", true, false)
		if spring_arm is SpringArm3D:
			(spring_arm as SpringArm3D).spring_length = 7.2

func _move_player_to_focus_vantage(target_position: Vector3) -> void:
	player.global_position = Vector3(target_position.x, 0.5, target_position.z) + focus_autotest_vantage_offset
	_orient_player_toward(target_position + Vector3(0.0, 1.0, 0.0))
	var camera_holder := _get_camera_holder()
	if camera_holder:
		camera_holder.rotation.x = deg_to_rad(-6.0)
		var spring_arm := camera_holder.find_child("SpringArm3D", true, false)
		if spring_arm is SpringArm3D:
			(spring_arm as SpringArm3D).spring_length = 2.6

func _capture_autotest_screenshot() -> void:
	var screenshot_path := OS.get_environment("PHASE0_AUTOTEST_SCREENSHOT")
	if screenshot_path == "":
		_bus_log("phase0_screenshot_skipped")
		return

	await RenderingServer.frame_post_draw
	var image := get_viewport().get_texture().get_image()
	var err := image.save_png(screenshot_path)
	_bus_log("phase0_screenshot_saved:%s:%s" % [screenshot_path, err])

func _get_bus() -> Node:
	return get_node_or_null("/root/LocalPresentationBus")

func _get_bridge() -> Node:
	return get_node_or_null("/root/BackendBridge")

func _bus_log(message: String) -> void:
	var bus := _get_bus()
	if bus and bus.has_method("log_debug"):
		bus.log_debug(message)

func _emit_focus_target_change() -> void:
	var bridge := _get_bridge()
	if bridge == null or intent_mapper == null:
		return
	if not intent_mapper.has_method("emit_focus_target_change"):
		return
	if bridge.has_method("is_backend_open") and not bridge.is_backend_open():
		pending_focus_sync = true
		return

	var target_actor_id := _resolve_focused_actor_id()
	var target_object_id := _resolve_focused_object_id()
	bridge.send_envelope(intent_mapper.emit_focus_target_change(target_actor_id, target_object_id))
	_emit_fixed_gaze_visual_fact(target_actor_id, target_object_id)

func _emit_move_intent_if_needed() -> void:
	if autotest_enabled:
		return
	if intent_mapper == null or not intent_mapper.has_method("emit_move_intent"):
		return
	if player_input_bridge == null or not player_input_bridge.has_method("get_control_anchor_position"):
		return

	var anchor: Variant = player_input_bridge.get_control_anchor_position()
	if not (anchor is Vector3):
		return
	var control_position := anchor as Vector3
	if last_reported_move_position != Vector3.INF and control_position.distance_to(last_reported_move_position) < 0.35:
		return

	last_reported_move_position = control_position
	var bridge := _get_bridge()
	if bridge:
		bridge.send_envelope(intent_mapper.emit_move_intent("locomotion", control_position))

func _get_camera() -> Camera3D:
	if player_input_bridge and player_input_bridge.has_method("get_camera"):
		var bridge_camera: Variant = player_input_bridge.get_camera()
		if bridge_camera is Camera3D:
			return bridge_camera as Camera3D
	var camera := player.find_child("Camera3D", true, false)
	if camera is Camera3D:
		return camera as Camera3D
	return null

func _get_camera_holder() -> Node3D:
	var holder := player.find_child("CameraHolder", true, false)
	if holder is Node3D:
		return holder as Node3D
	return null

func _get_focus_origin() -> Vector3:
	if player_input_bridge and player_input_bridge.has_method("get_control_anchor_position"):
		var anchor: Variant = player_input_bridge.get_control_anchor_position()
		if anchor is Vector3:
			return anchor + Vector3(0.0, 1.0, 0.0)
	return player.global_position + Vector3(0.0, 1.0, 0.0)

func _get_focus_forward() -> Vector3:
	if player_input_bridge and player_input_bridge.has_method("get_control_forward"):
		var forward: Variant = player_input_bridge.get_control_forward()
		if forward is Vector3 and (forward as Vector3).length() > 0.001:
			return (forward as Vector3).normalized()
	var camera := _get_camera()
	if camera:
		return -camera.global_basis.z.normalized()
	return -player.global_basis.z.normalized()

func _configure_open_field_camera() -> void:
	var camera_holder := _get_camera_holder()
	if camera_holder == null:
		return

	camera_holder.rotation.x = deg_to_rad(-20.0)
	var spring_arm := camera_holder.find_child("SpringArm3D", true, false)
	if spring_arm is SpringArm3D:
		(spring_arm as SpringArm3D).spring_length = 6.6

func _set_debug_overlay_visible(is_visible: bool) -> void:
	var overlay := get_node_or_null("DebugOverlay")
	if overlay is CanvasLayer:
		(overlay as CanvasLayer).visible = is_visible

func _wait_for_focus_response() -> void:
	var deadline := Time.get_ticks_msec() + int(focus_autotest_settle_delay * 1000.0)
	while Time.get_ticks_msec() < deadline:
		if focus_response_seen:
			return
		await get_tree().process_frame
	await get_tree().create_timer(0.1).timeout

func _request_backend_health() -> void:
	if backend_health_request == null:
		return
	var health_url := _build_health_url()
	if health_url == "":
		return
	var err := backend_health_request.request(health_url)
	if err != OK and err != ERR_BUSY:
		_bus_log("phase0_backend_health_request_failed:%s" % err)

func _build_health_url() -> String:
	var health_url := backend_url
	if health_url.begins_with("ws://"):
		health_url = "http://" + health_url.substr(5)
	elif health_url.begins_with("wss://"):
		health_url = "https://" + health_url.substr(6)
	if health_url.ends_with("/ws"):
		health_url = health_url.trim_suffix("/ws")
	if health_url.ends_with("/"):
		health_url = health_url.trim_suffix("/")
	return "%s/health" % health_url

func _on_backend_health_request_completed(_result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if response_code != 200:
		_bus_log("phase0_backend_health_status:%s" % response_code)
		return
	var parsed: Variant = JSON.parse_string(body.get_string_from_utf8())
	if typeof(parsed) != TYPE_DICTIONARY:
		_bus_log("phase0_backend_health_parse_failed")
		return
	var payload: Dictionary = parsed
	_bus_log(
		"phase0_backend_identity:%s:%s" % [
			str(payload.get("build", "")),
			str(payload.get("worktree_root", "")),
		]
	)

func _emit_fixed_gaze_visual_fact(target_actor_id: String, target_object_id: String) -> void:
	var bridge := _get_bridge()
	if bridge == null or intent_mapper == null:
		return
	if not intent_mapper.has_method("emit_visual_fact_event"):
		return
	if target_actor_id == "" and target_object_id == "":
		return

	var relation_type := "actor_looks_at_actor" if target_actor_id != "" else "actor_looks_at_object"
	_bus_log("phase0_visual_fact:%s:%s" % [relation_type, target_actor_id if target_actor_id != "" else target_object_id])
	bridge.send_envelope(intent_mapper.emit_visual_fact_event("fixed_gaze_on_target", relation_type, target_actor_id, target_object_id))

func _emit_near_object_visual_fact(target_object_id: String) -> void:
	var bridge := _get_bridge()
	if bridge == null or intent_mapper == null:
		return
	if not intent_mapper.has_method("emit_visual_fact_event"):
		return
	var target_node := _find_node_by_property("object_id", target_object_id)
	if target_node == null:
		return
	var now_ms := Time.get_ticks_msec()
	if target_object_id == last_near_object_visual_fact_target and now_ms - last_near_object_visual_fact_ts < near_object_visual_fact_cooldown_ms:
		return
	_bus_log("phase0_visual_fact:actor_near_object:%s" % target_object_id)
	bridge.send_envelope(intent_mapper.emit_visual_fact_event("spatial_relation", "actor_near_object", "", target_object_id))
	last_near_object_visual_fact_target = target_object_id
	last_near_object_visual_fact_ts = now_ms

func _sample_near_object_visual_fact() -> void:
	if current_focus_target == null:
		return
	var target_object_id := _resolve_focused_object_id()
	if target_object_id == "":
		return
	var bridge := _get_bridge()
	if bridge == null or (bridge.has_method("is_backend_open") and not bridge.is_backend_open()):
		return
	var target_node := _find_node_by_property("object_id", target_object_id)
	if target_node == null:
		return
	var focus_origin := _get_focus_origin()
	if focus_origin.distance_to(target_node.global_position) > near_object_visual_fact_distance:
		return
	_emit_near_object_visual_fact(target_object_id)

func _find_node_by_property(property_name: String, expected: String) -> Node3D:
	var scene := get_tree().current_scene
	if scene == null:
		return null
	return _find_node_by_property_recursive(scene, property_name, expected)

func _find_node_by_property_recursive(node: Node, property_name: String, expected: String) -> Node3D:
	if node is Node3D:
		var value: Variant = node.get(property_name)
		if value != null and str(value) == expected:
			return node as Node3D
	for child in node.get_children():
		var result := _find_node_by_property_recursive(child, property_name, expected)
		if result:
			return result
	return null
