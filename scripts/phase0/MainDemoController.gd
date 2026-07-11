extends Node3D

const LIGHTING_TUNER := preload("res://scripts/visual/ThroneRoomLightingTuner.gd")
const THRONE_HALL_WALK_PREVIEW := preload("res://scenes/phase0/ThroneHallWalkPreview.tscn")
const ACTOR_PERCEPTION_SAMPLER := preload("res://scripts/character/ActorPerceptionSampler.gd")
const ACTOR_PERCEPTION_TARGET_RESOLVER := preload("res://scripts/character/ActorPerceptionTargetResolver.gd")
const SIMING_VISUAL_OBSERVABILITY_PRESENTER := preload("res://scripts/phase0/SimingVisualObservabilityPresenter.gd")
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
@export var autotest_request_timeout_ms := 10000
@export var autotest_transport_quiet_window_ms := 500
@export var autotest_transport_quiet_timeout_ms := 10000
@export var autotest_final_position := Vector3(0.0, 0.5, 20.0)
@export var autotest_interact_position := Vector3(0.0, 0.5, 0.6)
@export var autotest_failed_interact_position := Vector3(0.0, 0.5, 16.0)
@export var focus_autotest_settle_delay := 0.45
@export var focus_autotest_vantage_offset := Vector3(1.2, 0.5, 2.7)
@export var focus_max_distance := 28.0
@export var focus_forward_threshold := 0.2
@export var focus_precision_alignment_threshold := 0.97
@export var near_object_visual_fact_distance := 18.0
@export var near_object_visual_fact_cooldown_ms := 650
@export var near_actor_spatial_access_distance := 18.0
@export var near_actor_spatial_access_cooldown_ms := 650
@export var privacy_private_distance := 4.0
@export var privacy_local_distance := 10.0

@onready var intent_mapper: Node = $IntentMapper
@onready var player: CharacterBody3D = $PlayerCharacter
@onready var player_input_bridge: Node = $PlayerCharacter/Phase0InputBridge
# A and B remain the current AI-driven scene actors.
@onready var character_a: Node3D = $CharacterA
@onready var character_b: Node3D = $CharacterB
@onready var interactive_object: Node3D = $InteractiveObject
@onready var character_visual_fact_emitter: Node = $VisualFactEmitter/CharacterVisualFactEmitter
@onready var evidence_projection_emitter: Node = $VisualFactEmitter/EvidenceProjectionEmitter
@onready var spatial_access_fact_emitter: Node = $VisualFactEmitter/SpatialAccessFactEmitter
@onready var tactile_fact_emitter: Node = $VisualFactEmitter/TactileFactEmitter
@onready var thermal_fact_emitter: Node = $VisualFactEmitter/ThermalFactEmitter
@onready var olfactory_fact_emitter: Node = $VisualFactEmitter/OlfactoryFactEmitter
@onready var focus_hint_label: Label = Label.new()

var current_focus_target: Node3D
var current_precise_focus_target: Node3D
var visible_focus_targets: Array[Node3D] = []
var observatory_view_actor_id := "char_c"
var last_reported_move_position := Vector3.INF
var pending_focus_sync := false
var focus_override_active := false
var focus_response_seen := false
var backend_health_request: HTTPRequest
var last_near_object_visual_fact_target := ""
var last_near_object_visual_fact_ts := 0
var last_spatial_access_actor_target := ""
var last_spatial_access_actor_ts := 0
var current_privacy_band := "public"
var spatial_zone_emitted := false
var suspend_near_object_visual_fact := false
var suspend_spatial_access_fact := false
var acknowledged_request_ids: Dictionary = {}
var pending_success_interaction_correlation_id := ""
var matched_success_interaction_result := false
var matched_success_object_result := false
var matched_success_environment_result := false
var pending_failed_interaction_correlation_id := ""
var matched_failed_interaction_result := false
var last_backend_activity_ms := 0
var autotest_transport_quiescent := false
var pending_backend_reconnect := false
var backend_connected_once := false
var pending_dialogue_request: Dictionary = {}
var pending_interaction_request: Dictionary = {}
var pending_move_request: Dictionary = {}
var autotest_run_started := false
var autotest_shutdown_in_progress := false
var scene_load_probe_only := false
var perception_debug_enabled := false
var npc_patrol_root_motion_seen: Dictionary = {}
var _perception_sampler = ACTOR_PERCEPTION_SAMPLER.new()
var _perception_target_resolver = ACTOR_PERCEPTION_TARGET_RESOLVER.new()

func _ready() -> void:
	_perception_sampler.range_m = focus_max_distance
	_perception_sampler.forward_threshold = focus_forward_threshold
	_perception_target_resolver.target_property_names = PackedStringArray(["actor_id", "object_id"])
	autotest_enabled = OS.get_environment("PHASE0_AUTOTEST") == "1"
	focus_autotest_enabled = OS.get_environment("PHASE0_FOCUS_AUTOTEST") == "1"
	scene_load_probe_only = OS.get_environment("PHASE0_SCENE_LOAD_ONLY") == "1"
	var bus := _get_bus()
	if bus:
		if bus.has_method("set_debug_logging_enabled"):
			bus.set_debug_logging_enabled(
				autotest_enabled or focus_autotest_enabled or OS.get_environment("PHASE0_DEBUG_LOGGING") == "1"
			)
		bus.backend_connected.connect(_on_backend_connected)
		if bus.has_signal("backend_disconnected"):
			bus.backend_disconnected.connect(_on_backend_disconnected)
		bus.backend_ack_received.connect(_on_backend_ack_received)
		if bus.has_signal("world_result_received"):
			bus.world_result_received.connect(_on_world_result_received)
		if bus.has_signal("debug_event_logged"):
			bus.debug_event_logged.connect(_on_debug_event_logged)
	_ensure_siming_visual_observability_presenter()
	backend_health_request = HTTPRequest.new()
	backend_health_request.name = "BackendHealthRequest"
	add_child(backend_health_request)
	backend_health_request.request_completed.connect(_on_backend_health_request_completed)
	LIGHTING_TUNER.apply_blender_approx(get_node_or_null("ThroneRoomImported"))
	_bootstrap_throne_room_collision()
	_ensure_l1_navigation_region()
	_configure_open_field_camera()
	_setup_focus_hint_label()
	_bus_log("phase0_main_ready")
	if scene_load_probe_only:
		call_deferred("_finish_scene_load_probe")
		return
	call_deferred("_connect_backend")

func _ensure_siming_visual_observability_presenter() -> void:
	if get_node_or_null("SimingVisualObservabilityPresenter") != null:
		return
	var presenter: Node = SIMING_VISUAL_OBSERVABILITY_PRESENTER.new()
	presenter.name = "SimingVisualObservabilityPresenter"
	add_child(presenter)

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

func _ensure_l1_navigation_region() -> void:
	var existing := get_node_or_null("L1NavigationRegion")
	if existing is NavigationRegion3D:
		_configure_l1_navigation_region(existing as NavigationRegion3D)
		return
	var nav_region := NavigationRegion3D.new()
	nav_region.name = "L1NavigationRegion"
	add_child(nav_region)
	_configure_l1_navigation_region(nav_region)
	_bus_log("l1_navigation_region_ready:%s" % str(nav_region.get_path()))

func _configure_l1_navigation_region(nav_region: NavigationRegion3D) -> void:
	nav_region.add_to_group("l1_navigation_lane")
	nav_region.set_meta("l1_space_type", "navigation_lane")
	nav_region.set_meta("element_id", "lane_focus")
	if nav_region.navigation_mesh != null:
		return
	var navigation_mesh := NavigationMesh.new()
	navigation_mesh.set_vertices(PackedVector3Array([
		Vector3(-9.0, 0.05, 16.0),
		Vector3(9.0, 0.05, 16.0),
		Vector3(9.0, 0.05, -12.0),
		Vector3(-9.0, 0.05, -12.0),
	]))
	navigation_mesh.add_polygon(PackedInt32Array([0, 1, 2, 3]))
	nav_region.navigation_mesh = navigation_mesh

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
	if autotest_shutdown_in_progress:
		return
	backend_connected_once = true
	pending_backend_reconnect = false
	_request_backend_health()
	_emit_spatial_access_zone_entry()
	if pending_focus_sync:
		_emit_focus_target_change()
		pending_focus_sync = false
	_flush_pending_backend_requests()
	if focus_autotest_enabled:
		if autotest_run_started:
			return
		autotest_run_started = true
		_run_focus_autotest()
		return
	if autotest_enabled:
		if autotest_run_started:
			return
		autotest_run_started = true
		_run_autotest_inputs()

func _on_backend_disconnected(_code: int = 0) -> void:
	if autotest_shutdown_in_progress:
		return
	if not backend_connected_once and _code == -1:
		_request_backend_reconnect()
		return
	spatial_zone_emitted = false
	pending_focus_sync = true
	last_spatial_access_actor_target = ""
	last_spatial_access_actor_ts = 0
	current_privacy_band = "public"
	_request_backend_reconnect()

func _on_backend_ack_received(payload: Dictionary) -> void:
	last_backend_activity_ms = Time.get_ticks_msec()
	var request_id := str(payload.get("request_id", ""))
	if request_id != "":
		acknowledged_request_ids[request_id] = payload.duplicate(true)
	_bus_log("phase0_ack:%s" % JSON.stringify(payload))

func _on_world_result_received(payload: Dictionary) -> void:
	last_backend_activity_ms = Time.get_ticks_msec()
	var result_type := str(payload.get("result_type", ""))
	var result_id := str(payload.get("result_id", ""))
	var correlation_id := str(payload.get("correlation_id", ""))
	if (
		result_type == "action_resolution_result"
		and pending_success_interaction_correlation_id != ""
		and correlation_id == pending_success_interaction_correlation_id
		and str(payload.get("settlement_status", "")) == "accepted"
	):
		matched_success_interaction_result = true
	if (
		result_type == "object_state_result"
		and pending_success_interaction_correlation_id != ""
		and correlation_id == pending_success_interaction_correlation_id
		and str(payload.get("target_object_id", "")) == "obj_letter"
		and str(payload.get("current_state", "")) == "visible"
	):
		matched_success_object_result = true
	if (
		result_type == "environment_state_result"
		and pending_success_interaction_correlation_id != ""
		and correlation_id == pending_success_interaction_correlation_id
		and str(payload.get("target_environment_id", "")) == "env_lamp"
		and str(payload.get("current_state", "")) == "alerted"
	):
		matched_success_environment_result = true
	if (
		result_type == "constraint_state_result"
		and pending_failed_interaction_correlation_id != ""
		and str(payload.get("correlation_id", "")) == pending_failed_interaction_correlation_id
	):
		matched_failed_interaction_result = true
	if not autotest_transport_quiescent:
		if result_type == "object_state_result" and str(payload.get("target_object_id", "")) == "obj_letter":
			if str(payload.get("current_state", "")) == "visible":
				if evidence_projection_emitter and evidence_projection_emitter.has_method("emit_visual_evidence_projection"):
					evidence_projection_emitter.emit_visual_evidence_projection("obj_letter")
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
	if message.begins_with("backend_message_"):
		last_backend_activity_ms = Time.get_ticks_msec()
	if message.contains("focus_state_applied:char_a") or message.contains("focus_attention:char_a"):
		focus_response_seen = true

func _process(_delta: float) -> void:
	if autotest_shutdown_in_progress or autotest_transport_quiescent:
		return
	if focus_override_active:
		if not suspend_spatial_access_fact:
			_sample_spatial_access_facts()
		return
	_update_focus_target()
	if not suspend_near_object_visual_fact:
		_sample_near_object_visual_fact()
	if not suspend_spatial_access_fact:
		_sample_spatial_access_facts()

func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey):
		return
	var key_event := event as InputEventKey
	if not key_event.pressed:
		return
	if key_event.keycode == KEY_F11:
		perception_debug_enabled = not perception_debug_enabled
		_apply_perception_debug_visibility()
		_refresh_focus_hint()

func _run_autotest_inputs() -> void:
	_bus_log("phase0_autotest_begin")
	focus_override_active = true
	suspend_near_object_visual_fact = true
	suspend_spatial_access_fact = true
	_set_debug_overlay_visible(false)
	await _probe_floor_coverage()
	_bus_log("phase0_autotest_stage:floor_coverage_complete")
	await _probe_floor_grid()
	_bus_log("phase0_autotest_stage:floor_grid_complete")
	await _run_locomotion_probe()
	_bus_log("phase0_autotest_stage:locomotion_probe_complete")
	await _run_npc_patrol_root_motion_probe()
	_bus_log("phase0_autotest_stage:npc_patrol_probe_complete")
	_bus_log("phase0_autotest_stage:probes_complete")
	if player_input_bridge and player_input_bridge.has_method("set_character_c_sync_enabled"):
		player_input_bridge.set_character_c_sync_enabled(false)
	_orient_player_toward(character_a.global_position)
	_force_focus_target(character_a)
	await get_tree().create_timer(autotest_dialogue_delay).timeout
	player_input_bridge.trigger_dialogue()
	_bus_log("phase0_autotest_stage:dialogue_submitted")
	_orient_player_toward(interactive_object.global_position)
	_move_player_to_interact_position()
	_force_focus_target(interactive_object)
	last_backend_activity_ms = Time.get_ticks_msec()
	if not (await _wait_for_backend_quiet(autotest_transport_quiet_window_ms, autotest_transport_quiet_timeout_ms)):
		await _fail_autotest("transport_not_quiet", {})
		return
	var near_move_request := _emit_move_intent_request(autotest_interact_position, "locomotion")
	if not (await _wait_for_request_ack(str(near_move_request.get("request_id", "")), autotest_request_timeout_ms)):
		await _fail_autotest("near_move_ack_timeout", near_move_request)
		return
	var success_interaction_request := _emit_interaction_request("obj_letter", "inspect")
	matched_success_interaction_result = false
	matched_success_object_result = false
	matched_success_environment_result = false
	pending_success_interaction_correlation_id = "interact:%s" % success_interaction_request.get("producer_ts", 0)
	_bus_log("phase0_autotest_stage:success_interaction_submitted")
	if not (await _wait_for_request_ack(str(success_interaction_request.get("request_id", "")), autotest_request_timeout_ms)):
		await _fail_autotest("success_interaction_ack_timeout", success_interaction_request)
		return
	if not (await _wait_for_successful_interaction_result(autotest_request_timeout_ms)):
		await _fail_autotest("success_interaction_result_timeout", success_interaction_request)
		return
	_move_player_to_demo_vantage()
	autotest_transport_quiescent = true
	suspend_near_object_visual_fact = true
	suspend_spatial_access_fact = true
	last_backend_activity_ms = Time.get_ticks_msec()
	if not (await _wait_for_backend_quiet(autotest_transport_quiet_window_ms, autotest_transport_quiet_timeout_ms)):
		await _fail_autotest("transport_not_quiet", {})
		return
	var far_move_request := _emit_move_intent_request(autotest_failed_interact_position, "locomotion")
	if not (await _wait_for_request_ack(str(far_move_request.get("request_id", "")), autotest_request_timeout_ms)):
		await _fail_autotest("far_move_ack_timeout", far_move_request)
		return
	_orient_player_toward(interactive_object.global_position)
	_bus_log("phase0_autotest_failed_interaction_attempt")
	var failed_interaction_request := _emit_interaction_request_without_near_object_fact("obj_letter", "inspect")
	matched_failed_interaction_result = false
	pending_failed_interaction_correlation_id = "interact:%s" % failed_interaction_request.get("producer_ts", 0)
	if not (await _wait_for_request_ack(str(failed_interaction_request.get("request_id", "")), autotest_request_timeout_ms)):
		await _fail_autotest("failed_interaction_ack_timeout", failed_interaction_request)
		return
	if not (await _wait_for_failed_interaction_result(autotest_request_timeout_ms)):
		await _fail_autotest("failed_interaction_result_timeout", failed_interaction_request)
		return
	_bus_log("phase0_autotest_stage:failed_interaction_resolved")
	await _capture_autotest_screenshot()
	await _begin_autotest_shutdown("phase0_autotest_complete")

func _wait_for_request_ack(request_id: String, timeout_ms: int) -> bool:
	if request_id == "":
		return false
	var deadline: int = Time.get_ticks_msec() + max(timeout_ms, 1)
	while Time.get_ticks_msec() < deadline:
		if acknowledged_request_ids.has(request_id):
			return true
		await get_tree().process_frame
	return false

func _wait_for_successful_interaction_result(timeout_ms: int) -> bool:
	var deadline: int = Time.get_ticks_msec() + max(timeout_ms, 1)
	while Time.get_ticks_msec() < deadline:
		if matched_success_interaction_result and matched_success_object_result and matched_success_environment_result:
			return true
		await get_tree().process_frame
	return false

func _wait_for_failed_interaction_result(timeout_ms: int) -> bool:
	var deadline: int = Time.get_ticks_msec() + max(timeout_ms, 1)
	while Time.get_ticks_msec() < deadline:
		if matched_failed_interaction_result:
			return true
		await get_tree().process_frame
	return false

func _wait_for_backend_quiet(quiet_window_ms: int, timeout_ms: int) -> bool:
	var deadline: int = Time.get_ticks_msec() + max(timeout_ms, 1)
	while Time.get_ticks_msec() < deadline:
		if Time.get_ticks_msec() - last_backend_activity_ms >= max(quiet_window_ms, 1):
			return true
		await get_tree().process_frame
	return false

func _fail_autotest(stage: String, request: Dictionary) -> void:
	var request_id := str(request.get("request_id", ""))
	_bus_log("phase0_autotest_failure:%s:%s" % [stage, request_id])
	await _capture_autotest_screenshot()
	await _begin_autotest_shutdown("phase0_autotest_failed")

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
	_bus_log("phase0_autotest_stage:gait_probe_complete")
	await _probe_jump_variant("two_foot", false)
	await _probe_jump_variant("single_leg", true)
	_bus_log("phase0_autotest_stage:jump_probe_complete")

func _run_npc_patrol_root_motion_probe() -> void:
	_bus_log("phase0_autotest_stage:npc_patrol_probe_begin")
	npc_patrol_root_motion_seen.clear()
	var bus := _get_bus()
	var debug_callable := Callable(self, "_on_npc_patrol_probe_debug_event")
	var connected_debug_signal := false
	if bus != null and bus.has_signal("debug_event_logged") and not bus.debug_event_logged.is_connected(debug_callable):
		bus.debug_event_logged.connect(debug_callable)
		connected_debug_signal = true
	for actor in [character_a, character_b]:
		if actor == null:
			continue
		actor.set("action_override_state", "")
		actor.set("action_override_timer", 0.0)
		actor.set("patrol_index", 1)
		actor.set("hold_timer", 0.0)
		if actor.has_method("_set_role_asset_motion_profile"):
			actor.call("_set_role_asset_motion_profile", "walk", "walk")
		actor.set("patrol_enabled", true)
	var deadline: int = Time.get_ticks_msec() + 2500
	while Time.get_ticks_msec() < deadline and npc_patrol_root_motion_seen.size() < 2:
		await get_tree().process_frame
	for actor in [character_a, character_b]:
		if actor == null:
			continue
		actor.set("patrol_enabled", false)
	if connected_debug_signal:
		bus.debug_event_logged.disconnect(debug_callable)

func _on_npc_patrol_probe_debug_event(message: String) -> void:
	if message == "patrol_root_motion_step:char_a":
		npc_patrol_root_motion_seen["char_a"] = true
	elif message == "patrol_root_motion_step:char_b":
		npc_patrol_root_motion_seen["char_b"] = true

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
	var move_forward_action := StringName(player.get("move_forward_action"))
	var run_action := StringName(player.get("run_action"))
	var jump_action := StringName(player.get("jump_action"))
	Input.action_press(move_forward_action)
	if wants_run:
		Input.action_press(run_action)
	await get_tree().create_timer(0.14).timeout
	var start_position := player.global_position
	var apex_height := start_position.y
	Input.action_press(jump_action)
	await get_tree().physics_frame
	Input.action_release(jump_action)
	var deadline := Time.get_ticks_msec() + 1400
	while Time.get_ticks_msec() < deadline:
		apex_height = max(apex_height, player.global_position.y)
		if player.is_on_floor() and player.global_position.y <= start_position.y + 0.02 and Time.get_ticks_msec() > deadline - 1000:
			break
		await get_tree().physics_frame
	Input.action_release(move_forward_action)
	if wants_run:
		Input.action_release(run_action)
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
	await _capture_autotest_screenshot()
	await _begin_autotest_shutdown("phase0_focus_autotest_complete")

func _update_focus_target() -> void:
	_sync_observatory_view_actor()
	visible_focus_targets = _collect_visible_focus_targets()
	var next_target := _pick_precise_focus_target(visible_focus_targets)
	if next_target == current_precise_focus_target:
		_refresh_focus_hint()
		return

	_set_focus_visual(current_precise_focus_target, false)
	current_precise_focus_target = next_target
	current_focus_target = current_precise_focus_target
	_set_focus_visual(current_focus_target, true)
	_emit_focus_target_change()
	_refresh_focus_hint()

	if current_focus_target:
		_bus_log("phase0_focus:%s" % current_focus_target.name)

func _collect_visible_focus_targets() -> Array[Node3D]:
	var candidates := _get_focus_candidates()
	var player_origin := _get_focus_origin()
	var view_forward := _get_view_forward()
	var view_actor := _get_view_origin_actor_node()
	var visible_candidates := _perception_sampler.sample_visible_targets(
		player_origin,
		view_forward,
		candidates,
		view_actor,
		Callable(self, "_get_focus_candidate_position"),
		Callable(self, "_has_focus_line_of_sight")
	)
	var filtered_candidates: Array[Node3D] = []
	for candidate: Node3D in visible_candidates:
		var candidate_position := _get_focus_candidate_position(candidate)
		var offset := candidate_position - player_origin
		var distance := offset.length()
		if distance <= 0.001:
			continue

		var direction := offset / distance
		if _precise_focus_alignment(candidate_position, direction) < 0.0:
			continue
		filtered_candidates.append(candidate)

	filtered_candidates.sort_custom(Callable(self, "_compare_visible_focus_targets"))
	return filtered_candidates

func _get_focus_candidates() -> Array[Node3D]:
	var scene := get_tree().current_scene
	var view_actor := _get_view_origin_actor_node()
	if scene == null:
		return []
	return _perception_target_resolver.resolve_targets(scene, view_actor)

func _pick_precise_focus_target(candidates: Array[Node3D]) -> Node3D:
	var camera := _get_camera()
	var player_origin := _get_focus_origin()
	var view_forward := _get_view_forward()
	var best_target: Node3D
	var best_score := -1.0

	for candidate in candidates:
		if candidate == null:
			continue
		var candidate_position := _get_focus_candidate_position(candidate)
		var offset := candidate_position - player_origin
		var distance := offset.length()
		if distance <= 0.001:
			continue
		var direction := offset / distance
		var broad_alignment := view_forward.dot(direction)
		var precise_alignment := _precise_focus_alignment(candidate_position, direction)
		if precise_alignment < focus_precision_alignment_threshold:
			continue
		var score := precise_alignment * 4.0 + broad_alignment - distance * 0.03
		if score > best_score:
			best_score = score
			best_target = candidate

	return best_target

func _compare_visible_focus_targets(left: Node3D, right: Node3D) -> bool:
	return _visible_focus_target_score(left) > _visible_focus_target_score(right)

func _visible_focus_target_score(candidate: Node3D) -> float:
	if candidate == null:
		return -INF
	var player_origin := _get_focus_origin()
	var view_forward := _get_view_forward()
	var candidate_position := _get_focus_candidate_position(candidate)
	var offset := candidate_position - player_origin
	var distance := offset.length()
	if distance <= 0.001:
		return -INF
	var direction := offset / distance
	return view_forward.dot(direction) * 2.0 + _precise_focus_alignment(candidate_position, direction) - distance * 0.03

func _resolve_focused_actor_id() -> String:
	if current_precise_focus_target == null:
		return ""
	var actor_value: Variant = current_precise_focus_target.get("actor_id")
	if actor_value != null and str(actor_value) != "":
		return str(actor_value)
	return ""

func _resolve_focused_object_id() -> String:
	if current_precise_focus_target == null:
		return ""
	var object_value: Variant = current_precise_focus_target.get("object_id")
	if object_value != null and str(object_value) != "":
		return str(object_value)
	return ""

func _physics_process(_delta: float) -> void:
	if autotest_shutdown_in_progress:
		return
	_emit_move_intent_if_needed()

func _set_focus_visual(target: Node3D, is_focused: bool) -> void:
	if target and target.has_method("set_focus_highlight"):
		target.set_focus_highlight(is_focused)

func _force_focus_target(target: Node3D) -> void:
	_set_focus_visual(current_precise_focus_target, false)
	_sync_observatory_view_actor()
	visible_focus_targets = _collect_visible_focus_targets()
	if target != null and not visible_focus_targets.has(target):
		visible_focus_targets.push_front(target)
	current_precise_focus_target = target
	current_focus_target = target
	_set_focus_visual(current_focus_target, true)
	_emit_focus_target_change()
	_refresh_focus_hint()
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

func _finish_scene_load_probe() -> void:
	_bus_log("phase0_scene_load_probe_complete")
	get_tree().quit()

func _begin_autotest_shutdown(reason: String) -> void:
	if autotest_shutdown_in_progress:
		return
	autotest_shutdown_in_progress = true
	focus_override_active = false
	set_process(false)
	set_physics_process(false)
	var bridge := _get_bridge()
	if bridge and bridge.has_method("close_backend_connection"):
		bridge.close_backend_connection()
	await get_tree().process_frame
	await get_tree().process_frame
	call_deferred("_finish_autotest_run", reason)


func _finish_autotest_run(reason: String) -> void:
	_bus_log(reason)
	get_tree().quit()

func _get_bus() -> Node:
	return get_node_or_null("/root/LocalPresentationBus")

func _get_bridge() -> Node:
	return get_node_or_null("/root/BackendBridge")

func _bus_log(message: String) -> void:
	var bus := _get_bus()
	if bus and bus.has_method("log_debug"):
		bus.log_debug(message)

func _request_backend_reconnect() -> void:
	var bridge := _get_bridge()
	if bridge == null:
		return
	if bridge.has_method("is_backend_open") and bridge.is_backend_open():
		pending_backend_reconnect = false
		return
	if pending_backend_reconnect:
		return
	pending_backend_reconnect = true
	call_deferred("_perform_backend_reconnect")

func _perform_backend_reconnect() -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	var bridge := _get_bridge()
	if bridge == null:
		pending_backend_reconnect = false
		return
	if bridge.has_method("is_backend_open") and bridge.is_backend_open():
		pending_backend_reconnect = false
		return
	var err: int = bridge.connect_to_backend(backend_url)
	_bus_log("phase0_backend_reconnect_err:%s" % err)
	if err != OK:
		pending_backend_reconnect = false

func _flush_pending_backend_requests() -> void:
	if not pending_dialogue_request.is_empty():
		var dialogue_request := pending_dialogue_request.duplicate(true)
		pending_dialogue_request = {}
		_emit_dialogue_request(
			str(dialogue_request.get("target_actor_id", "")),
			str(dialogue_request.get("content", "")),
		)
	if not pending_move_request.is_empty():
		var move_request := pending_move_request.duplicate(true)
		pending_move_request = {}
		var target_point_value: Variant = move_request.get("target_point", Vector3.ZERO)
		if target_point_value is Vector3:
			_emit_move_intent_request(target_point_value, str(move_request.get("move_mode", "locomotion")))
	if not pending_interaction_request.is_empty():
		var interaction_request := pending_interaction_request.duplicate(true)
		pending_interaction_request = {}
		_emit_interaction_request(
			str(interaction_request.get("target_object_id", "")),
			str(interaction_request.get("interaction_type", "inspect")),
		)

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
	if bridge.has_method("is_backend_open") and not bridge.is_backend_open():
		pending_dialogue_request = {"target_actor_id": target_actor_id, "content": content}
		_request_backend_reconnect()
		return
	bridge.send_envelope(intent_mapper.emit_dialogue_submit(target_actor_id, content))

func _emit_interaction_request(target_object_id: String, interaction_type: String) -> Dictionary:
	var bridge := _get_bridge()
	if bridge == null or intent_mapper == null:
		return {}
	if not intent_mapper.has_method("emit_interact_intent"):
		return {}
	_bus_log("phase0_interact_target:%s" % target_object_id)
	_emit_near_object_visual_fact(target_object_id)
	if bridge.has_method("is_backend_open") and not bridge.is_backend_open():
		pending_interaction_request = {"target_object_id": target_object_id, "interaction_type": interaction_type}
		_request_backend_reconnect()
		return {}
	return _send_player_input_envelope(bridge, intent_mapper.emit_interact_intent(target_object_id, interaction_type))

func _emit_interaction_request_without_near_object_fact(target_object_id: String, interaction_type: String) -> Dictionary:
	var bridge := _get_bridge()
	if bridge == null or intent_mapper == null:
		return {}
	if not intent_mapper.has_method("emit_interact_intent"):
		return {}
	_bus_log("phase0_interact_target:%s" % target_object_id)
	if bridge.has_method("is_backend_open") and not bridge.is_backend_open():
		pending_interaction_request = {"target_object_id": target_object_id, "interaction_type": interaction_type}
		_request_backend_reconnect()
		return {}
	return _send_player_input_envelope(bridge, intent_mapper.emit_interact_intent(target_object_id, interaction_type))

func _emit_move_intent_request(target_point: Vector3, move_mode: String) -> Dictionary:
	var bridge := _get_bridge()
	if bridge == null or intent_mapper == null:
		return {}
	if not intent_mapper.has_method("emit_move_intent"):
		return {}
	_bus_log(
		"phase0_move_target:%s:[%.3f,%.3f,%.3f]" % [
			move_mode,
			target_point.x,
			target_point.y,
			target_point.z,
		]
	)
	if bridge.has_method("is_backend_open") and not bridge.is_backend_open():
		pending_move_request = {"target_point": target_point, "move_mode": move_mode}
		_request_backend_reconnect()
		return {}
	return _send_player_input_envelope(bridge, intent_mapper.emit_move_intent(move_mode, target_point))

func _send_player_input_envelope(bridge: Node, envelope: Dictionary) -> Dictionary:
	var payload_value: Variant = envelope.get("payload", {})
	if not (payload_value is Dictionary):
		return {}
	var payload := payload_value as Dictionary
	var descriptor := {
		"request_id": str(payload.get("request_id", "")),
		"producer_ts": int(payload.get("producer_ts", 0)),
	}
	var err: int = bridge.send_envelope(envelope)
	if err != OK:
		return {}
	return descriptor

func _emit_move_intent_if_needed() -> void:
	if autotest_enabled or focus_autotest_enabled:
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
	var view_actor := _get_view_origin_actor_node()
	if view_actor != null and observatory_view_actor_id != "char_c":
		if view_actor.has_method("get_focus_anchor_position"):
			var actor_anchor: Variant = view_actor.get_focus_anchor_position()
			if actor_anchor is Vector3:
				return actor_anchor
		return view_actor.global_position + Vector3(0.0, 1.0, 0.0)
	if player_input_bridge and player_input_bridge.has_method("get_control_anchor_position"):
		var anchor: Variant = player_input_bridge.get_control_anchor_position()
		if anchor is Vector3:
			return anchor + Vector3(0.0, 1.0, 0.0)
	return player.global_position + Vector3(0.0, 1.0, 0.0)

func _get_focus_forward() -> Vector3:
	var view_actor := _get_view_origin_actor_node()
	if view_actor != null and observatory_view_actor_id != "char_c":
		if view_actor.has_method("get_embodied_forward_vector"):
			var actor_forward: Variant = view_actor.get_embodied_forward_vector()
			if actor_forward is Vector3 and (actor_forward as Vector3).length() > 0.001:
				return (actor_forward as Vector3).normalized()
		return view_actor.global_basis.z.normalized()
	if player_input_bridge and player_input_bridge.has_method("get_control_forward"):
		var forward: Variant = player_input_bridge.get_control_forward()
		if forward is Vector3 and (forward as Vector3).length() > 0.001:
			return (forward as Vector3).normalized()
	var camera := _get_camera()
	if camera:
		return -camera.global_basis.z.normalized()
	return -player.global_basis.z.normalized()

func _get_view_forward() -> Vector3:
	if observatory_view_actor_id == "char_c":
		var camera := _get_camera()
		if camera:
			return -camera.global_basis.z.normalized()
	return _get_focus_forward()

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

func _setup_focus_hint_label() -> void:
	focus_hint_label.name = "PlayerFocusHint"
	focus_hint_label.position = Vector2(16, 16)
	focus_hint_label.size = Vector2(940, 180)
	focus_hint_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	focus_hint_label.vertical_alignment = VERTICAL_ALIGNMENT_TOP
	focus_hint_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(focus_hint_label)
	_refresh_focus_hint()

func _refresh_focus_hint() -> void:
	if focus_hint_label == null:
		return
	var actor_id := _resolve_focused_actor_id()
	var object_id := _resolve_focused_object_id()
	var half_fov_degrees := rad_to_deg(acos(clamp(focus_forward_threshold, -1.0, 1.0)))
	var precision_half_fov_degrees := rad_to_deg(acos(clamp(focus_precision_alignment_threshold, -1.0, 1.0)))
	var rule_summary := "判定规则：距离不超过 %.1f 米，进入视线锥体约 %.1f 度内，就算“看见”；只有镜头真正对准目标，才会精确锁定，精确锁定大约要落在 %.1f 度内。按 F11 可以显示所有角色的视线锥体。" % [focus_max_distance, half_fov_degrees, precision_half_fov_degrees]
	var visible_summary := _build_visible_focus_summary()
	var observer_summary := "当前观察角色：%s" % _describe_actor_id_name(observatory_view_actor_id)
	if actor_id != "":
		var actor_name := "角色A" if actor_id == "char_a" else "角色B" if actor_id == "char_b" else "你自己"
		var actor_node := _find_node_by_property("actor_id", actor_id)
		focus_hint_label.text = "%s\n当前精确锁定：%s（%.1f 米）。想测试对话，就保持镜头对准他再按对话键。\n%s\n%s" % [observer_summary, actor_name, _distance_to_focus_candidate(actor_node), visible_summary, rule_summary]
		return
	if object_id != "":
		var object_node := _find_node_by_property("object_id", object_id)
		focus_hint_label.text = "%s\n当前精确锁定物体：%s（%.1f 米）。想测试交互，就继续对着它再按交互键。\n%s\n%s" % [observer_summary, object_id, _distance_to_focus_candidate(object_node), visible_summary, rule_summary]
		return
	if visible_focus_targets.is_empty():
		focus_hint_label.text = "%s\n当前视野里没有可用目标。先把角色或物体放进你的视线锥体里。\n%s" % [observer_summary, rule_summary]
		return
	focus_hint_label.text = "%s\n当前还没有精确锁定目标。现在只是“看见了”，只有镜头真正对准目标，才会精确锁定。\n%s\n%s" % [observer_summary, visible_summary, rule_summary]

func _apply_perception_debug_visibility() -> void:
	var half_fov_degrees: float = rad_to_deg(acos(clamp(focus_forward_threshold, -1.0, 1.0)))
	for actor in _get_perception_debug_characters():
		if actor == null:
			continue
		if actor.has_method("configure_perception_debug"):
			actor.configure_perception_debug(focus_max_distance, half_fov_degrees)
		if actor.has_method("set_perception_debug_visible"):
			actor.set_perception_debug_visible(perception_debug_enabled)

func _get_perception_debug_characters() -> Array[Node3D]:
	var actors: Array[Node3D] = []
	for candidate in [character_a, character_b, get_node_or_null("PlayerCharacter/CharacterReplica")]:
		if candidate is Node3D:
			actors.append(candidate)
	return actors

func _get_focus_candidate_position(candidate: Node3D) -> Vector3:
	if candidate == null:
		return Vector3.ZERO
	if candidate.has_method("get_focus_anchor_position"):
		var focus_anchor: Variant = candidate.get_focus_anchor_position()
		if focus_anchor is Vector3:
			return focus_anchor
	return candidate.global_position

func _distance_to_focus_candidate(candidate: Node3D) -> float:
	if candidate == null:
		return 0.0
	return _get_focus_origin().distance_to(_get_focus_candidate_position(candidate))

func _camera_ray_alignment(camera: Camera3D, world_position: Vector3) -> float:
	if camera == null:
		return -1.0
	var origin := camera.global_position
	var direction := (world_position - origin).normalized()
	return (-camera.global_basis.z).normalized().dot(direction)

func _build_visible_focus_summary() -> String:
	if visible_focus_targets.is_empty():
		return "当前视野里没有目标。"

	var segments: Array[String] = []
	for candidate in visible_focus_targets:
		segments.append(_describe_visible_focus_target(candidate))
	return "视野里目标：%s" % "；".join(segments)

func _describe_visible_focus_target(candidate: Node3D) -> String:
	if candidate == null:
		return "空目标"
	var descriptor := _describe_focus_target_name(candidate)
	var coords := _get_target_relative_view_coordinates(candidate)
	var horizontal_angle := rad_to_deg(atan2(coords.x, max(coords.z, 0.001)))
	var vertical_angle := rad_to_deg(atan2(coords.y, max(coords.z, 0.001)))
	return "%s 相对坐标[x=%.1f, y=%.1f, z=%.1f]，水平 %.1f°，垂直 %.1f°" % [
		descriptor,
		coords.x,
		coords.y,
		coords.z,
		horizontal_angle,
		vertical_angle,
	]

func _describe_focus_target_name(candidate: Node3D) -> String:
	if candidate == null:
		return "未知目标"
	var actor_value: Variant = candidate.get("actor_id")
	if actor_value != null and str(actor_value) != "":
		var actor_id := str(actor_value)
		if actor_id == "char_a":
			return "角色A"
		if actor_id == "char_b":
			return "角色B"
		if actor_id == "char_c":
			return "玩家角色"
		return actor_id
	var object_value: Variant = candidate.get("object_id")
	if object_value != null and str(object_value) != "":
		return "物体 %s" % str(object_value)
	return candidate.name

func _get_target_relative_view_coordinates(candidate: Node3D) -> Vector3:
	var origin := _get_focus_origin()
	var target_position := _get_focus_candidate_position(candidate)
	var offset := target_position - origin
	if observatory_view_actor_id != "char_c":
		var forward := _get_view_forward()
		var right := forward.cross(Vector3.UP).normalized()
		var up := right.cross(forward).normalized()
		return Vector3(offset.dot(right), offset.dot(up), offset.dot(forward))
	var camera := _get_camera()
	if camera == null:
		var forward := _get_view_forward()
		var right := forward.cross(Vector3.UP).normalized()
		var up := right.cross(forward).normalized()
		return Vector3(offset.dot(right), offset.dot(up), offset.dot(forward))
	var right_axis := camera.global_basis.x.normalized()
	var up_axis := camera.global_basis.y.normalized()
	var forward_axis := (-camera.global_basis.z).normalized()
	return Vector3(offset.dot(right_axis), offset.dot(up_axis), offset.dot(forward_axis))

func _get_observatory_state() -> Node:
	return get_node_or_null("ObservatoryRoot/CharacterDirectorState")

func _sync_observatory_view_actor() -> void:
	observatory_view_actor_id = "char_c"
	var state := _get_observatory_state()
	if state == null:
		return
	var observatory_enabled: Variant = state.get("observatory_enabled")
	if observatory_enabled != true:
		return
	var selected_actor_id := str(state.selected_actor_id)
	if selected_actor_id.is_empty():
		return
	if _find_node_by_property("actor_id", selected_actor_id) == null:
		return
	observatory_view_actor_id = selected_actor_id

func _get_view_origin_actor_node() -> Node3D:
	if observatory_view_actor_id == "char_c":
		var player_replica := get_node_or_null("PlayerCharacter/CharacterReplica")
		if player_replica is Node3D:
			return player_replica as Node3D
		return player
	var actor_node := _find_node_by_property("actor_id", observatory_view_actor_id)
	if actor_node is Node3D:
		return actor_node as Node3D
	return null

func _precise_focus_alignment(candidate_position: Vector3, direction: Vector3) -> float:
	if observatory_view_actor_id == "char_c":
		return _camera_ray_alignment(_get_camera(), candidate_position)
	return _get_view_forward().dot(direction)

func _has_focus_line_of_sight(candidate: Node3D) -> bool:
	if candidate == null or not candidate.is_inside_tree():
		return false
	if not is_inside_tree() or get_world_3d() == null:
		return false
	var query := PhysicsRayQueryParameters3D.create(_get_focus_origin(), _get_focus_candidate_position(candidate))
	query.exclude = _build_focus_raycast_exclusions()
	var hit := get_world_3d().direct_space_state.intersect_ray(query)
	if hit.is_empty():
		return true
	return _is_focus_hit_target(hit.get("collider"), candidate)

func _build_focus_raycast_exclusions() -> Array:
	var exclusions: Array = []
	exclusions.append(player)
	var view_actor := _get_view_origin_actor_node()
	if view_actor != null and not exclusions.has(view_actor):
		exclusions.append(view_actor)
	var player_replica := get_node_or_null("PlayerCharacter/CharacterReplica")
	if player_replica != null and not exclusions.has(player_replica):
		exclusions.append(player_replica)
	return exclusions

func _is_focus_hit_target(collider: Variant, candidate: Node3D) -> bool:
	if collider == candidate:
		return true
	if collider is Node:
		return candidate.is_ancestor_of(collider as Node)
	return false

func _describe_actor_id_name(actor_id: String) -> String:
	if actor_id == "char_a":
		return "角色A"
	if actor_id == "char_b":
		return "角色B"
	if actor_id == "char_c":
		return "玩家角色"
	return actor_id

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
	if player_input_bridge and player_input_bridge.has_method("get_control_forward"):
		var forward: Variant = player_input_bridge.get_control_forward()
		if forward is Vector3 and (forward as Vector3).length() > 0.001:
			return (forward as Vector3).normalized()
	return Vector3(0.0, 0.0, -1.0)
