extends Node3D

const LIGHTING_TUNER := preload("res://scripts/visual/ThroneRoomLightingTuner.gd")
const THRONE_HALL_WALK_PREVIEW := preload("res://scenes/phase0/ThroneHallWalkPreview.tscn")
const FLOOR_CHECKPOINTS := [
	{"name": "entry_carpet", "position": Vector3(0.0, 0.5, 16.0)},
	{"name": "center_carpet", "position": Vector3(0.0, 0.5, 4.0)},
	{"name": "object_carpet", "position": Vector3(3.8, 0.5, -4.6)},
	{"name": "left_aisle_tile", "position": Vector3(-7.0, 0.5, 6.0)},
	{"name": "right_aisle_tile", "position": Vector3(7.0, 0.5, 6.0)},
	{"name": "throne_approach", "position": Vector3(0.0, 0.5, -12.0)},
]
const FLOOR_GRID_X := [-9.0, -6.0, -3.0, 0.0, 3.0, 6.0, 9.0]
const FLOOR_GRID_Z := [16.0, 12.0, 8.0, 4.0, 0.0, -4.0, -8.0, -12.0]

@export var backend_url := "ws://127.0.0.1:8000/ws"
@export var autotest_enabled := false
@export var focus_autotest_enabled := false
@export var autotest_dialogue_delay := 0.25
@export var autotest_interact_delay := 0.6
@export var autotest_capture_delay := 0.8
@export var autotest_final_position := Vector3(0.0, 0.5, 20.0)
@export var autotest_interact_position := Vector3(0.0, 0.5, 0.6)
@export var focus_autotest_settle_delay := 0.45
@export var focus_autotest_vantage_offset := Vector3(1.2, 0.5, 2.7)
@export var focus_max_distance := 28.0
@export var focus_forward_threshold := 0.2
@export var near_object_visual_fact_distance := 18.0
@export var near_object_visual_fact_cooldown_ms := 650
@export var near_actor_spatial_access_distance := 18.0
@export var near_actor_spatial_access_cooldown_ms := 650
@export var privacy_private_distance := 4.0
@export var privacy_local_distance := 10.0

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
@onready var character_visual_fact_emitter: Node = $VisualFactEmitter/CharacterVisualFactEmitter
@onready var spatial_access_fact_emitter: Node = $VisualFactEmitter/SpatialAccessFactEmitter
@onready var tactile_fact_emitter: Node = $VisualFactEmitter/TactileFactEmitter
@onready var thermal_fact_emitter: Node = $VisualFactEmitter/ThermalFactEmitter
@onready var olfactory_fact_emitter: Node = $VisualFactEmitter/OlfactoryFactEmitter

var current_focus_target: Node3D
var last_reported_move_position := Vector3.INF
var pending_focus_sync := false
var last_debug_message := ""
var focus_override_active := false
var focus_response_seen := false
var backend_health_request: HTTPRequest
var last_near_object_visual_fact_target := ""
var last_near_object_visual_fact_ts := 0
var last_spatial_access_actor_target := ""
var last_spatial_access_actor_ts := 0
var current_privacy_band := "public"
var spatial_zone_emitted := false

func _ready() -> void:
	var bus := _get_bus()
	if bus:
		bus.backend_connected.connect(_on_backend_connected)
		if bus.has_signal("backend_disconnected"):
			bus.backend_disconnected.connect(_on_backend_disconnected)
		bus.backend_ack_received.connect(_on_backend_ack_received)
		if bus.has_signal("world_result_received"):
			bus.world_result_received.connect(_on_world_result_received)
		if bus.has_signal("debug_event_logged"):
			bus.debug_event_logged.connect(_on_debug_event_logged)
	backend_health_request = HTTPRequest.new()
	backend_health_request.name = "BackendHealthRequest"
	add_child(backend_health_request)
	backend_health_request.request_completed.connect(_on_backend_health_request_completed)
	LIGHTING_TUNER.apply_blender_approx(get_node_or_null("ThroneRoomImported"))
	_bootstrap_throne_room_collision()
	_configure_open_field_camera()
	_bus_log("phase0_main_ready")
	autotest_enabled = OS.get_environment("PHASE0_AUTOTEST") == "1"
	focus_autotest_enabled = OS.get_environment("PHASE0_FOCUS_AUTOTEST") == "1"
	call_deferred("_connect_backend")

func _bootstrap_throne_room_collision() -> void:
	if get_node_or_null("ThroneRoomCollisionRoot") != null:
		return
	var imported_root := get_node_or_null("ThroneRoomImported")
	if imported_root == null:
		return
	var mesh_lookup := {}
	_build_imported_mesh_lookup(imported_root, mesh_lookup)
	var preview_scene := THRONE_HALL_WALK_PREVIEW.instantiate()
	if preview_scene == null:
		return
	var collision_root := Node3D.new()
	collision_root.name = "ThroneRoomCollisionRoot"
	add_child(collision_root)

	for source_path in ["PreviewFloor", "WalkStepLower", "WalkStepUpper", "PreviewCollisionRoot"]:
		var source_node := preview_scene.get_node_or_null(source_path)
		if source_node == null:
			continue
		var duplicated := source_node.duplicate()
		if duplicated is Node:
			_ensure_preview_collision_shapes(duplicated as Node, mesh_lookup)
			collision_root.add_child(duplicated)
	preview_scene.queue_free()
	_bus_log("throne_room_collision_bootstrap:static_bodies=%s collision_shapes=%s" % [
		_count_static_bodies(collision_root),
		_count_collision_shapes(collision_root),
	])

func _ensure_preview_collision_shapes(root: Node, mesh_lookup: Dictionary) -> void:
	for child in root.get_children():
		_ensure_preview_collision_shapes(child, mesh_lookup)
	if not (root is StaticBody3D):
		return
	if root.get_child_count() > 0:
		for child in root.get_children():
			if child is CollisionShape3D:
				return
	var lower := String(root.name).to_lower()
	var collision_shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	if String(root.name).begins_with("COL_"):
		var source_name := String(root.name).trim_prefix("COL_")
		var mesh_node: MeshInstance3D = mesh_lookup.get(source_name, null)
		if mesh_node != null and mesh_node.mesh != null:
			var trimesh := mesh_node.mesh.create_trimesh_shape()
			if trimesh != null:
				collision_shape.shape = trimesh
				root.add_child(collision_shape)
				return
			var aabb := mesh_node.mesh.get_aabb()
			var scale_vec := mesh_node.scale
			var size := Vector3(
				max(abs(aabb.size.x * scale_vec.x), 0.1),
				max(abs(aabb.size.y * scale_vec.y), 0.1),
				max(abs(aabb.size.z * scale_vec.z), 0.1)
			)
			box.size = size
			collision_shape.position = aabb.position + aabb.size * 0.5
			collision_shape.shape = box
			root.add_child(collision_shape)
			return
	var size := Vector3(3.0, 0.5, 3.0)
	if lower.contains("carpet"):
		size = Vector3(2.4, 0.35, 2.4)
	elif lower.contains("previewfloor"):
		size = Vector3(220.0, 2.0, 220.0)
	elif lower.contains("walksteplower"):
		size = Vector3(16.0, 1.2, 18.0)
	elif lower.contains("walkstepupper"):
		size = Vector3(14.0, 1.2, 16.0)
	elif lower.contains("floor3m"):
		size = Vector3(3.2, 0.5, 3.2)
	elif lower.contains("floortiles"):
		size = Vector3(2.2, 0.45, 2.2)
	else:
		return
	box.size = size
	collision_shape.shape = box
	root.add_child(collision_shape)

func _build_imported_mesh_lookup(root: Node, mesh_lookup: Dictionary) -> void:
	if root is MeshInstance3D:
		mesh_lookup[root.name] = root
	for child in root.get_children():
		_build_imported_mesh_lookup(child, mesh_lookup)

func _connect_backend() -> void:
	await get_tree().process_frame
	await get_tree().process_frame
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
	_emit_dialogue_request(target_actor_id, content)

func submit_interaction() -> void:
	var target_object_id := _resolve_focused_object_id()
	if target_object_id == "":
		_bus_log("phase0_interact_no_focus_target")
		return
	_emit_interaction_request(target_object_id, "inspect")

func _on_backend_connected(_payload: String) -> void:
	_request_backend_health()
	_emit_spatial_access_zone_entry()
	if pending_focus_sync:
		_emit_focus_target_change()
		pending_focus_sync = false
	if focus_autotest_enabled:
		_run_focus_autotest()
		return
	if autotest_enabled:
		_run_autotest_inputs()

func _on_backend_disconnected(_code: int = 0) -> void:
	spatial_zone_emitted = false
	pending_focus_sync = true
	last_spatial_access_actor_target = ""
	last_spatial_access_actor_ts = 0
	current_privacy_band = "public"

func _on_backend_ack_received(payload: Dictionary) -> void:
	_bus_log("phase0_ack:%s" % JSON.stringify(payload))

func _on_world_result_received(payload: Dictionary) -> void:
	var result_type := str(payload.get("result_type", ""))
	var result_id := str(payload.get("result_id", ""))
	if result_type == "object_state_result" and str(payload.get("target_object_id", "")) == "obj_letter":
		if str(payload.get("current_state", "")) == "visible":
			if tactile_fact_emitter and tactile_fact_emitter.has_method("emit_contact_fact"):
				tactile_fact_emitter.emit_contact_fact("", "obj_letter", "light")
	elif result_type == "environment_state_result" and str(payload.get("target_environment_id", "")) == "env_lamp":
		if str(payload.get("current_state", "")) == "alerted":
			if thermal_fact_emitter and thermal_fact_emitter.has_method("emit_thermal_proximity_fact"):
				thermal_fact_emitter.emit_thermal_proximity_fact("env_lamp", "warm")
			if olfactory_fact_emitter and olfactory_fact_emitter.has_method("emit_odor_state_fact"):
				olfactory_fact_emitter.emit_odor_state_fact("env_lamp", "noticeable")
	if result_id != "":
		_bus_log("phase0_world_result_seen:%s:%s" % [result_type, result_id])

func _on_debug_event_logged(message: String) -> void:
	last_debug_message = message
	if message.contains("focus_state_applied:char_a") or message.contains("focus_attention:char_a"):
		focus_response_seen = true

func _process(_delta: float) -> void:
	if focus_override_active:
		_sample_spatial_access_facts()
		return
	_update_focus_target()
	_sample_near_object_visual_fact()
	_sample_spatial_access_facts()

func _run_autotest_inputs() -> void:
	_bus_log("phase0_autotest_begin")
	focus_override_active = true
	_set_debug_overlay_visible(false)
	await _probe_floor_coverage()
	await _probe_floor_grid()
	await _run_locomotion_probe()
	if player_input_bridge and player_input_bridge.has_method("set_character_c_sync_enabled"):
		player_input_bridge.set_character_c_sync_enabled(false)
	_orient_player_toward(character_a.global_position)
	_force_focus_target(character_a)
	await get_tree().create_timer(autotest_dialogue_delay).timeout
	player_input_bridge.trigger_dialogue()
	_orient_player_toward(interactive_object.global_position)
	_force_focus_target(interactive_object)
	_move_player_to_interact_position()
	_emit_move_intent_request(autotest_interact_position, "locomotion")
	await get_tree().create_timer(autotest_interact_delay).timeout
	player_input_bridge.trigger_interaction()
	_move_player_to_demo_vantage()
	_emit_move_intent_request(autotest_final_position, "locomotion")
	await get_tree().create_timer(autotest_interact_delay).timeout
	_orient_player_toward(interactive_object.global_position)
	_force_focus_target(interactive_object)
	_bus_log("phase0_autotest_failed_interaction_attempt")
	player_input_bridge.trigger_interaction()
	await get_tree().create_timer(autotest_capture_delay).timeout
	_capture_autotest_screenshot()
	focus_override_active = false
	if player_input_bridge and player_input_bridge.has_method("set_character_c_sync_enabled"):
		player_input_bridge.set_character_c_sync_enabled(true)
	get_tree().quit()

func _probe_floor_coverage() -> void:
	for checkpoint in FLOOR_CHECKPOINTS:
		var probe := _sample_floor_point(checkpoint["position"])
		_bus_log(
			"floor_probe:%s grounded=%s y=%.3f normal_y=%.3f" % [
				checkpoint["name"],
				str(probe["grounded"]),
				probe["y"],
				probe["normal_y"],
			]
		)

func _probe_floor_grid() -> void:
	var hole_anomalies: Array[String] = []
	var blocked_anomalies: Array[String] = []
	var total := 0
	for z in FLOOR_GRID_Z:
		for x in FLOOR_GRID_X:
			total += 1
			var probe := _sample_floor_point(Vector3(x, 0.5, z))
			var grounded := bool(probe["grounded"])
			var y := float(probe["y"])
			var normal_y := float(probe["normal_y"])
			if not grounded or y < -0.05:
				hole_anomalies.append("(x=%.1f,z=%.1f,grounded=%s,y=%.3f,ny=%.3f)" % [x, z, str(grounded), y, normal_y])
			elif y > 0.35 or normal_y < 0.65:
				blocked_anomalies.append("(x=%.1f,z=%.1f,grounded=%s,y=%.3f,ny=%.3f)" % [x, z, str(grounded), y, normal_y])
	if hole_anomalies.is_empty() and blocked_anomalies.is_empty():
		_bus_log("floor_grid_probe:points=%s holes=0 blocked=0" % total)
	else:
		_bus_log("floor_grid_probe:points=%s holes=%s blocked=%s" % [total, hole_anomalies.size(), blocked_anomalies.size()])
		for anomaly in hole_anomalies:
			_bus_log("floor_grid_hole:%s" % anomaly)
		for anomaly in blocked_anomalies:
			_bus_log("floor_grid_blocked:%s" % anomaly)

func _sample_floor_point(position: Vector3) -> Dictionary:
	var from := Vector3(position.x, 3.0, position.z)
	var to := Vector3(position.x, -4.0, position.z)
	var query := PhysicsRayQueryParameters3D.create(from, to)
	query.collision_mask = 0xFFFFFFFF
	query.exclude = [player]
	var result := get_world_3d().direct_space_state.intersect_ray(query)
	if result.is_empty():
		return {"grounded": false, "y": position.y, "normal_y": 0.0}
	var hit_position: Vector3 = result.get("position", position)
	var hit_normal: Vector3 = result.get("normal", Vector3.UP)
	return {
		"grounded": true,
		"y": hit_position.y,
		"normal_y": hit_normal.y,
	}

func _run_locomotion_probe() -> void:
	if player_input_bridge == null or not player_input_bridge.has_method("set_forced_player_motion"):
		return
	await _probe_gait_segment("amble", false, false, 0.35)
	await _probe_gait_segment("walk", false, false, 0.35)
	await _probe_gait_segment("brisk_walk", false, false, 0.35)
	await _probe_gait_segment("run", true, false, 0.35)
	await _probe_gait_segment("crouch_walk", false, true, 0.35)
	await _probe_jump_variant("two_foot", false)
	await _probe_jump_variant("single_leg", true)

func _probe_gait_segment(gait_name: String, wants_run: bool, crouch_enabled: bool, duration: float) -> void:
	if player_input_bridge.has_method("set_crouch_enabled"):
		player_input_bridge.set_crouch_enabled(crouch_enabled)
	if player_input_bridge.has_method("set_gait_mode_by_name") and gait_name != "run" and gait_name != "crouch_walk":
		player_input_bridge.set_gait_mode_by_name(gait_name)
	player_input_bridge.set_forced_player_motion(Vector3(0.0, 0.0, -1.0), wants_run)
	await get_tree().create_timer(0.18).timeout
	var start_position := player.global_position
	await get_tree().create_timer(duration).timeout
	var end_position := player.global_position
	player_input_bridge.clear_forced_player_motion()
	var distance := start_position.distance_to(end_position)
	var delta_vector := end_position - start_position
	var facing_dot := _get_character_visual_forward().dot(Vector3(0.0, 0.0, -1.0))
	_bus_log(
		"locomotion_probe:gait=%s crouch=%s run=%s distance=%.3f dx=%.3f dz=%.3f facing_dot=%.3f" % [
			gait_name,
			str(crouch_enabled),
			str(wants_run),
			distance,
			delta_vector.x,
			delta_vector.z,
			facing_dot,
		]
	)
	await get_tree().create_timer(0.08).timeout
	if crouch_enabled and player_input_bridge.has_method("set_crouch_enabled"):
		player_input_bridge.set_crouch_enabled(false)
		await get_tree().create_timer(0.08).timeout

func _probe_jump_variant(jump_type: String, wants_run: bool) -> void:
	if player_input_bridge == null:
		return
	if player_input_bridge.has_method("set_crouch_enabled"):
		player_input_bridge.set_crouch_enabled(false)
	if player_input_bridge.has_method("set_gait_mode_by_name"):
		player_input_bridge.set_gait_mode_by_name("walk")
	Input.action_press(player.move_forward_action)
	if wants_run:
		Input.action_press(player.run_action)
	await get_tree().create_timer(0.14).timeout
	var start_position := player.global_position
	var apex_height := start_position.y
	Input.action_press(player.jump_action)
	await get_tree().physics_frame
	Input.action_release(player.jump_action)
	var deadline := Time.get_ticks_msec() + 1400
	while Time.get_ticks_msec() < deadline:
		apex_height = max(apex_height, player.global_position.y)
		if player.is_on_floor() and player.global_position.y <= start_position.y + 0.02 and Time.get_ticks_msec() > deadline - 1000:
			break
		await get_tree().physics_frame
	Input.action_release(player.move_forward_action)
	if wants_run:
		Input.action_release(player.run_action)
	var end_position := player.global_position
	var horizontal_distance := Vector2(end_position.x - start_position.x, end_position.z - start_position.z).length()
	_bus_log(
		"jump_probe:type=%s run=%s apex=%.3f distance=%.3f" % [
			jump_type,
			str(wants_run),
			apex_height - start_position.y,
			horizontal_distance,
		]
	)
	await get_tree().create_timer(0.12).timeout

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

func _move_player_to_interact_position() -> void:
	player.global_position = autotest_interact_position
	_orient_player_toward(interactive_object.global_position)

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

func _emit_dialogue_request(target_actor_id: String, content: String) -> void:
	var bridge := _get_bridge()
	if bridge == null or intent_mapper == null:
		return
	if not intent_mapper.has_method("emit_dialogue_submit"):
		return
	_bus_log("phase0_dialogue_target:%s" % target_actor_id)
	bridge.send_envelope(intent_mapper.emit_dialogue_submit(target_actor_id, content))

func _emit_interaction_request(target_object_id: String, interaction_type: String) -> void:
	var bridge := _get_bridge()
	if bridge == null or intent_mapper == null:
		return
	if not intent_mapper.has_method("emit_interact_intent"):
		return
	_bus_log("phase0_interact_target:%s" % target_object_id)
	_emit_near_object_visual_fact(target_object_id)
	bridge.send_envelope(intent_mapper.emit_interact_intent(target_object_id, interaction_type))

func _emit_move_intent_request(target_point: Vector3, move_mode: String) -> void:
	var bridge := _get_bridge()
	if bridge == null or intent_mapper == null:
		return
	if not intent_mapper.has_method("emit_move_intent"):
		return
	_bus_log(
		"phase0_move_target:%s:[%.3f,%.3f,%.3f]" % [
			move_mode,
			target_point.x,
			target_point.y,
			target_point.z,
		]
	)
	bridge.send_envelope(intent_mapper.emit_move_intent(move_mode, target_point))

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
	_emit_move_intent_request(control_position, "locomotion")

func _emit_spatial_access_zone_entry() -> void:
	if spatial_zone_emitted:
		return
	if spatial_access_fact_emitter == null:
		return
	if not spatial_access_fact_emitter.has_method("emit_actor_entered_zone"):
		return
	var bridge := _get_bridge()
	if bridge == null or (bridge.has_method("is_backend_open") and not bridge.is_backend_open()):
		return
	var emitted: bool = spatial_access_fact_emitter.emit_actor_entered_zone("zone_focus")
	if not emitted:
		return
	spatial_zone_emitted = true

func _sample_spatial_access_facts() -> void:
	var bridge := _get_bridge()
	if bridge == null or (bridge.has_method("is_backend_open") and not bridge.is_backend_open()):
		return
	_emit_spatial_access_zone_entry()
	_sample_actor_approach_fact()
	_sample_privacy_boundary_fact()

func _sample_actor_approach_fact() -> void:
	if spatial_access_fact_emitter == null:
		return
	if not spatial_access_fact_emitter.has_method("emit_actor_approached_actor"):
		return
	if not spatial_access_fact_emitter.has_method("emit_actor_left_actor_range"):
		return
	var target_actor_id := _resolve_focused_actor_id()
	if target_actor_id == "":
		if last_spatial_access_actor_target != "":
			spatial_access_fact_emitter.emit_actor_left_actor_range("zone_focus")
		last_spatial_access_actor_target = ""
		return
	var target_node := _find_node_by_property("actor_id", target_actor_id)
	if target_node == null:
		if last_spatial_access_actor_target != "":
			spatial_access_fact_emitter.emit_actor_left_actor_range("zone_focus")
		last_spatial_access_actor_target = ""
		return
	var distance := _get_focus_origin().distance_to(target_node.global_position)
	if distance > near_actor_spatial_access_distance:
		if last_spatial_access_actor_target != "":
			spatial_access_fact_emitter.emit_actor_left_actor_range("zone_focus")
		last_spatial_access_actor_target = ""
		return
	var now_ms := Time.get_ticks_msec()
	if target_actor_id == last_spatial_access_actor_target and now_ms - last_spatial_access_actor_ts < near_actor_spatial_access_cooldown_ms:
		return
	var emitted: bool = spatial_access_fact_emitter.emit_actor_approached_actor(target_actor_id, distance)
	if not emitted:
		return
	last_spatial_access_actor_target = target_actor_id
	last_spatial_access_actor_ts = now_ms

func _sample_privacy_boundary_fact() -> void:
	if spatial_access_fact_emitter == null:
		return
	if not spatial_access_fact_emitter.has_method("emit_privacy_boundary_changed"):
		return
	var next_band := _resolve_privacy_band()
	if next_band == current_privacy_band:
		return
	var emitted: bool = spatial_access_fact_emitter.emit_privacy_boundary_changed(current_privacy_band, next_band, "zone_focus")
	if not emitted:
		return
	current_privacy_band = next_band

func _resolve_privacy_band() -> String:
	var target_actor_id := _resolve_focused_actor_id()
	if target_actor_id == "":
		return "public"
	var target_node := _find_node_by_property("actor_id", target_actor_id)
	if target_node == null:
		return "public"
	var distance := _get_focus_origin().distance_to(target_node.global_position)
	if distance <= privacy_private_distance:
		return "private"
	if distance <= privacy_local_distance:
		return "local"
	return "public"

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
	if backend_health_request.get_http_client_status() != HTTPClient.STATUS_DISCONNECTED:
		backend_health_request.cancel_request()
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
	if character_visual_fact_emitter == null:
		return
	if not character_visual_fact_emitter.has_method("emit_fixed_gaze_on_target"):
		return
	character_visual_fact_emitter.emit_fixed_gaze_on_target(target_actor_id, target_object_id)

func _emit_near_object_visual_fact(target_object_id: String) -> void:
	if character_visual_fact_emitter == null:
		return
	if not character_visual_fact_emitter.has_method("emit_actor_near_object"):
		return
	var target_node := _find_node_by_property("object_id", target_object_id)
	if target_node == null:
		return
	var now_ms := Time.get_ticks_msec()
	if target_object_id == last_near_object_visual_fact_target and now_ms - last_near_object_visual_fact_ts < near_object_visual_fact_cooldown_ms:
		return
	var emitted: bool = character_visual_fact_emitter.emit_actor_near_object(target_object_id)
	if not emitted:
		return
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

func _count_static_bodies(node: Node) -> int:
	var total := 0
	if node is StaticBody3D:
		total += 1
	for child in node.get_children():
		total += _count_static_bodies(child)
	return total

func _count_collision_shapes(node: Node) -> int:
	var total := 0
	if node is CollisionShape3D:
		total += 1
	for child in node.get_children():
		total += _count_collision_shapes(child)
	return total

func _get_character_visual_forward() -> Vector3:
	if character_c and character_c.has_method("get_visual_forward"):
		var forward: Variant = character_c.get_visual_forward()
		if forward is Vector3 and (forward as Vector3).length() > 0.001:
			return (forward as Vector3).normalized()
	return Vector3(0.0, 0.0, -1.0)
