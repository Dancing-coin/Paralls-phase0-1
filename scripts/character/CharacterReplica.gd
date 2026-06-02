extends Node3D

enum LocomotionState {
	IDLE,
	WALK,
	ATTEND,
}

enum DriverMode {
	AI,
	PLAYER,
}

@export var actor_id := "char_a"
@export var patrol_enabled := true
@export var patrol_points: Array[Vector3] = [Vector3.ZERO]
@export var move_speed := 0.55
@export var move_accel := 2.8
@export var move_decel := 3.2
@export var hold_duration := 1.1
@export var patrol_wait_duration := 0.45
@export var turn_speed := 4.5
@export var sway_amount := 0.035
@export var sway_speed := 2.4
@export var dialogue_lean_amount := 0.14
@export var attention_recoil_amount := 0.18
@export var posture_recover_speed := 5.0
@export var driver_mode := DriverMode.AI
@export var use_role_asset := false
@export var player_shell_visual_offset := Vector3(0.0, 0.0, 0.0)
@export var reacts_to_player_focus := false

@onready var visual_scene: Node = $VisualRoot/GreyboxBodyRoot/GreyboxHumanoidVisual
@onready var visual_root: Node3D = $VisualRoot
@onready var role_asset_root: Node3D = $VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot
@onready var role_asset_scene: Node = $VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/GodotPlushSkin
@onready var nameplate: Label3D = $Nameplate

var home_position := Vector3.ZERO
var locomotion_state: int = LocomotionState.IDLE
var hold_timer := 0.0
var sway_time := 0.0
var current_look_target := Vector3.ZERO
var has_look_target := false
var patrol_index := 0
var current_velocity := Vector3.ZERO
var posture_offset := Vector3.ZERO
var posture_target := Vector3.ZERO
var external_move_target := Vector3.ZERO
var has_external_move_target := false
var external_look_target := Vector3.ZERO
var has_external_look_target := false
var requested_action := ""
var player_shell_velocity := Vector3.ZERO
var player_shell_grounded := true
var player_shell_active := false
var focus_attention_timer := 0.0
var focus_attention_visual_timer := 0.0
var focus_attention_posture_timer := 0.0
var runtime_focus_target := ""
var runtime_attention_source := ""
var runtime_nearby_actor_refs: Array[String] = []
var runtime_nearby_object_refs: Array[String] = []
var runtime_nearby_environment_refs: Array[String] = []
var runtime_conversation_candidate_refs: Array[String] = []
var runtime_engagement_pressure := ""
var runtime_privacy_risk_hint := ""

func _ready() -> void:
	home_position = global_position
	current_look_target = global_position - global_basis.z
	_apply_asset_mode()
	_normalize_patrol_points()
	_apply_visual_config()
	_update_nameplate()
	var bus := _get_bus()
	if bus:
		bus.dialogue_received.connect(_on_dialogue_received)
		bus.siming_output_received.connect(_on_siming_output_received)
		if bus.has_signal("focus_state_received"):
			bus.focus_state_received.connect(_on_focus_state_received)
		if bus.has_signal("character_runtime_state_delta_received"):
			bus.character_runtime_state_delta_received.connect(_on_character_runtime_state_delta_received)
		if bus.has_signal("character_runtime_state_snapshot_received"):
			bus.character_runtime_state_snapshot_received.connect(_on_character_runtime_state_snapshot_received)

func _process(delta: float) -> void:
	sway_time += delta * sway_speed
	_apply_idle_sway()
	_update_posture(delta)
	_update_hold(delta)
	_update_rotation(delta)
	_update_movement(delta)

func set_driver_mode(next_mode: int) -> void:
	driver_mode = next_mode

func set_move_target(target: Vector3) -> void:
	external_move_target = Vector3(target.x, global_position.y, target.z)
	has_external_move_target = true

func clear_move_target() -> void:
	has_external_move_target = false
	external_move_target = Vector3.ZERO

func set_look_target(target: Vector3) -> void:
	external_look_target = target
	has_external_look_target = true

func clear_look_target() -> void:
	has_external_look_target = false
	external_look_target = Vector3.ZERO

func perform_action(action_name: String) -> void:
	requested_action = action_name

func apply_player_shell_frame(world_position: Vector3, planar_velocity: Vector3, look_target: Vector3, is_grounded: bool) -> void:
	driver_mode = DriverMode.PLAYER
	player_shell_active = true
	player_shell_velocity = Vector3(planar_velocity.x, 0.0, planar_velocity.z)
	player_shell_grounded = is_grounded
	global_position = Vector3(world_position.x, world_position.y, world_position.z) + player_shell_visual_offset
	set_look_target(look_target)
	_update_player_shell_locomotion()

func clear_player_shell_frame() -> void:
	player_shell_active = false
	driver_mode = DriverMode.AI
	player_shell_velocity = Vector3.ZERO
	player_shell_grounded = true
	current_velocity = Vector3.ZERO
	clear_move_target()
	clear_look_target()
	if locomotion_state == LocomotionState.WALK or locomotion_state == LocomotionState.ATTEND:
		locomotion_state = LocomotionState.IDLE
		if use_role_asset:
			_set_role_asset_state("idle")

func is_player_shell_active() -> bool:
	return player_shell_active

func get_role_anchor_position() -> Vector3:
	return global_position

func apply_dialogue(payload: Dictionary) -> void:
	var voice := get_node_or_null("SpatialVoiceController")
	if voice:
		voice.play_stub_voice(payload)
	_pause_and_face(_resolve_player_position())
	_set_dialogue_pose()
	if use_role_asset:
		_set_role_asset_state("run")
	_bus_log("dialogue_applied:%s" % actor_id)

func apply_attention(payload: Dictionary) -> void:
	var target_position := _resolve_attention_target(payload)
	_pause_and_face(target_position)
	_set_attention_pose()
	if use_role_asset:
		_set_role_asset_state("fall")
	var target_environment_raw: Variant = payload.get("target_environment_id", null)
	if target_environment_raw != null and str(target_environment_raw) != "":
		var target_environment_id := str(target_environment_raw)
		_bus_log("attention_target_environment:%s:%s" % [actor_id, target_environment_id])
	_bus_log("attention_applied:%s" % actor_id)

func _on_dialogue_received(payload: Dictionary) -> void:
	if payload.get("actor_id", "") == actor_id:
		apply_dialogue(payload)

func _on_siming_output_received(payload: Dictionary) -> void:
	if payload.get("target_actor_id", "") == actor_id:
		apply_attention(payload)

func _on_focus_state_received(payload: Dictionary) -> void:
	if not reacts_to_player_focus:
		return
	if str(payload.get("actor_id", "")) != "char_c":
		return
	if str(payload.get("target_actor_id", "")) != actor_id:
		return

	_bus_log("focus_state_applied:%s" % actor_id)
	_focus_on_player_attention()

func _on_character_runtime_state_snapshot_received(payload: Dictionary) -> void:
	if str(payload.get("actor_id", "")) != actor_id:
		return
	_apply_runtime_state_payload(payload)

func _on_character_runtime_state_delta_received(payload: Dictionary) -> void:
	if str(payload.get("actor_id", "")) != actor_id:
		return
	_apply_runtime_state_payload(payload)

func _get_bus() -> Node:
	return get_node_or_null("/root/LocalPresentationBus")

func _bus_log(message: String) -> void:
	var bus := _get_bus()
	if bus and bus.has_method("log_debug"):
		bus.log_debug(message)

func set_focus_highlight(is_focused: bool) -> void:
	var environment_attention := runtime_nearby_environment_refs.size() > 0 and runtime_attention_source == "visual_fact"
	var highlighted := is_focused or focus_attention_visual_timer > 0.0 or runtime_attention_source == "focus_state" or runtime_attention_source == "visual_fact" or environment_attention
	if use_role_asset:
		_set_role_asset_focus(highlighted)
	else:
		if visual_scene and visual_scene.has_method("set_focus_highlight"):
			visual_scene.set_focus_highlight(highlighted)
	_update_nameplate()

func _apply_idle_sway() -> void:
	if visual_root:
		var offset_y := sin(sway_time) * sway_amount
		visual_root.position = Vector3(posture_offset.x, offset_y + posture_offset.y, posture_offset.z)

func _update_posture(delta: float) -> void:
	posture_offset = posture_offset.lerp(posture_target, clamp(posture_recover_speed * delta, 0.0, 1.0))
	if focus_attention_visual_timer > 0.0:
		focus_attention_visual_timer = max(focus_attention_visual_timer - delta, 0.0)
		set_focus_highlight(false)
	if focus_attention_posture_timer > 0.0:
		focus_attention_posture_timer = max(focus_attention_posture_timer - delta, 0.0)

	if hold_timer <= 0.0 and focus_attention_posture_timer <= 0.0 and posture_target.length() > 0.001:
		posture_target = Vector3.ZERO

func _update_hold(delta: float) -> void:
	if hold_timer > 0.0:
		hold_timer = max(hold_timer - delta, 0.0)
		locomotion_state = LocomotionState.ATTEND
	elif locomotion_state == LocomotionState.ATTEND:
		if focus_attention_timer > 0.0:
			focus_attention_timer = max(focus_attention_timer - delta, 0.0)
		else:
			locomotion_state = LocomotionState.IDLE
			if use_role_asset:
				_set_role_asset_state("idle")

func _update_movement(delta: float) -> void:
	if driver_mode == DriverMode.PLAYER and player_shell_active:
		current_velocity = player_shell_velocity
		return

	if hold_timer > 0.0:
		current_velocity = current_velocity.move_toward(Vector3.ZERO, move_decel * delta)
		return

	if has_external_move_target:
		_move_toward_target(external_move_target, delta, true)
		return

	if not patrol_enabled or patrol_points.size() <= 1:
		current_velocity = current_velocity.move_toward(Vector3.ZERO, move_decel * delta)
		return

	var target: Vector3 = home_position + patrol_points[patrol_index]
	_move_toward_patrol_target(target, delta)

func _move_toward_patrol_target(target: Vector3, delta: float) -> void:
	var to_target: Vector3 = target - global_position
	to_target.y = 0.0
	if to_target.length() < 0.05:
		patrol_index = (patrol_index + 1) % patrol_points.size()
		locomotion_state = LocomotionState.IDLE
		hold_timer = max(hold_timer, patrol_wait_duration)
		current_velocity = current_velocity.move_toward(Vector3.ZERO, move_decel * delta)
		return

	_move_toward_target(target, delta, false)

func _move_toward_target(target: Vector3, delta: float, clear_on_arrival: bool) -> void:
	var to_target: Vector3 = target - global_position
	to_target.y = 0.0
	if to_target.length() < 0.05:
		if clear_on_arrival:
			clear_move_target()
		locomotion_state = LocomotionState.IDLE
		current_velocity = current_velocity.move_toward(Vector3.ZERO, move_decel * delta)
		if use_role_asset:
			_set_role_asset_state("idle")
		return

	var move_direction: Vector3 = to_target.normalized()
	current_velocity = current_velocity.move_toward(move_direction * move_speed, move_accel * delta)
	var step: Vector3 = current_velocity * delta
	if step.length() > to_target.length():
		step = move_direction * to_target.length()

	global_position += step
	current_look_target = global_position + move_direction
	has_look_target = true
	locomotion_state = LocomotionState.WALK
	posture_target = Vector3.ZERO
	if use_role_asset:
		_set_role_asset_state("walk")

func _update_player_shell_locomotion() -> void:
	var planar_speed := player_shell_velocity.length()
	if planar_speed > 0.08:
		locomotion_state = LocomotionState.WALK
		posture_target = Vector3.ZERO
		if use_role_asset:
			_set_role_asset_state("walk")
	elif not player_shell_grounded:
		locomotion_state = LocomotionState.ATTEND
		if use_role_asset:
			_set_role_asset_state("run")
	else:
		locomotion_state = LocomotionState.IDLE
		if use_role_asset:
			_set_role_asset_state("idle")

func _update_rotation(delta: float) -> void:
	if has_external_look_target:
		current_look_target = external_look_target
		has_look_target = true

	if not has_look_target:
		return

	var look_target: Vector3 = Vector3(current_look_target.x, global_position.y, current_look_target.z)
	if look_target.is_equal_approx(global_position):
		return

	var desired_basis: Basis = Basis.looking_at((look_target - global_position).normalized(), Vector3.UP)
	global_basis = global_basis.slerp(desired_basis, clamp(turn_speed * delta, 0.0, 1.0))

func _pause_and_face(target_position: Vector3) -> void:
	hold_timer = hold_duration
	current_look_target = target_position
	has_look_target = true
	current_velocity = Vector3.ZERO
	locomotion_state = LocomotionState.ATTEND

func _focus_on_player_attention() -> void:
	focus_attention_timer = max(focus_attention_timer, 0.7)
	focus_attention_visual_timer = max(focus_attention_visual_timer, 0.9)
	focus_attention_posture_timer = max(focus_attention_posture_timer, 0.9)
	current_look_target = _resolve_player_position()
	has_look_target = true
	current_velocity = Vector3.ZERO
	locomotion_state = LocomotionState.ATTEND
	posture_target = Vector3(0.0, attention_recoil_amount * 0.22, -dialogue_lean_amount * 0.55)
	set_focus_highlight(true)
	if use_role_asset:
		_set_role_asset_state("walk")
	_bus_log("focus_attention:%s" % actor_id)

func _apply_runtime_state_payload(payload: Dictionary) -> void:
	runtime_focus_target = _read_runtime_string(payload, "current_focus_target", runtime_focus_target)
	runtime_attention_source = _read_runtime_string(payload, "current_attention_source", runtime_attention_source)
	if payload.has("nearby_actor_refs"):
		runtime_nearby_actor_refs = _read_runtime_string_array(payload.get("nearby_actor_refs", []))
	if payload.has("nearby_object_refs"):
		runtime_nearby_object_refs = _read_runtime_string_array(payload.get("nearby_object_refs", []))
	if payload.has("nearby_environment_refs"):
		runtime_nearby_environment_refs = _read_runtime_string_array(payload.get("nearby_environment_refs", []))
	if payload.has("conversation_candidate_refs"):
		runtime_conversation_candidate_refs = _read_runtime_string_array(payload.get("conversation_candidate_refs", []))
	runtime_engagement_pressure = _read_runtime_string(payload, "engagement_pressure", runtime_engagement_pressure)
	runtime_privacy_risk_hint = _read_runtime_string(payload, "privacy_risk_hint", runtime_privacy_risk_hint)
	if actor_id == "char_c":
		_bus_log(
			"runtime_state_applied:%s:%s:%s" % [
				actor_id,
				runtime_focus_target,
				runtime_attention_source,
			]
		)

func _read_runtime_string(payload: Dictionary, key: String, current: String) -> String:
	if not payload.has(key):
		return current
	var value: Variant = payload.get(key)
	if value == null:
		return current
	return str(value)

func _read_runtime_string_array(value: Variant) -> Array[String]:
	var result: Array[String] = []
	if value is Array:
		for entry in value:
			if entry == null:
				continue
			result.append(str(entry))
	return result

func _update_nameplate() -> void:
	if nameplate == null:
		return
	var source_visual_fact := runtime_attention_source == "visual_fact"
	var environment_attention := source_visual_fact and runtime_nearby_environment_refs.size() > 0
	var attention_active := focus_attention_visual_timer > 0.0 or runtime_conversation_candidate_refs.size() > 0 or source_visual_fact
	if not attention_active:
		nameplate.text = actor_id.to_upper()
		nameplate.modulate = Color(1.0, 1.0, 1.0, 1.0)
		return
	if environment_attention and focus_attention_visual_timer <= 0.0:
		nameplate.text = "%s ?" % actor_id.to_upper()
		nameplate.modulate = Color(1.0, 0.62, 0.28, 1.0)
		return
	if source_visual_fact and focus_attention_visual_timer <= 0.0:
		nameplate.text = "%s ~" % actor_id.to_upper()
		nameplate.modulate = Color(0.55, 0.92, 1.0, 1.0)
		return
	nameplate.text = "%s !" % actor_id.to_upper()
	nameplate.modulate = Color(1.0, 0.92, 0.45, 1.0)

func _resolve_player_position() -> Vector3:
	var scene := get_tree().current_scene
	if scene:
		var character_c := scene.get_node_or_null("CharacterC")
		if character_c and character_c.has_method("is_player_shell_active") and character_c.is_player_shell_active():
			if character_c.has_method("get_role_anchor_position"):
				return character_c.get_role_anchor_position()
			if character_c is Node3D:
				return (character_c as Node3D).global_position
	var player := get_tree().get_root().find_child("Player", true, false)
	if player is Node3D:
		return (player as Node3D).global_position
	return global_position - global_basis.z

func _resolve_attention_target(payload: Dictionary) -> Vector3:
	var environment_raw: Variant = payload.get("target_environment_id", null)
	if environment_raw != null and str(environment_raw) != "":
		var environment_id := str(environment_raw)
		var environment_node := _find_node_by_property("environment_id", environment_id)
		if environment_node:
			return environment_node.global_position

	var object_id := str(payload.get("target_object_id", ""))
	if object_id != "":
		var object_node := _find_node_by_property("object_id", object_id)
		if object_node:
			return object_node.global_position

	var actor_target := str(payload.get("target_actor_id", ""))
	if actor_target != "":
		var actor_node := _find_node_by_property("actor_id", actor_target)
		if actor_node:
			return actor_node.global_position

	return _resolve_player_position()

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
		var result: Node3D = _find_node_by_property_recursive(child, property_name, expected)
		if result:
			return result
	return null

func _normalize_patrol_points() -> void:
	if patrol_points.is_empty():
		patrol_points = [Vector3.ZERO]
		return

	var normalized: Array[Vector3] = []
	for point in patrol_points:
		normalized.append(Vector3(point.x, 0.0, point.z))
	patrol_points = normalized

func _apply_visual_config() -> void:
	if use_role_asset:
		_apply_role_asset_config()
		return
	if visual_scene and visual_scene.has_method("configure_visuals"):
		var accent := Color(0.25, 0.55, 0.95, 1.0)
		if actor_id == "char_a":
			accent = Color(0.95, 0.76, 0.32, 1.0)
		elif actor_id == "char_b":
			accent = Color(0.56, 0.47, 0.86, 1.0)
		visual_scene.configure_visuals(actor_id, Color(0.82, 0.84, 0.92, 1.0), Color(0.95, 0.84, 0.72, 1.0), accent, Color(0.95, 0.85, 0.35, 1.0))

func _set_dialogue_pose() -> void:
	posture_target = Vector3(0.0, 0.0, -dialogue_lean_amount)

func _set_attention_pose() -> void:
	posture_target = Vector3(0.0, attention_recoil_amount * 0.35, attention_recoil_amount)

func _apply_asset_mode() -> void:
	if role_asset_root:
		role_asset_root.visible = use_role_asset
	if role_asset_scene is Node3D:
		(role_asset_scene as Node3D).visible = use_role_asset
	var greybox_root := visual_scene.get_parent() if visual_scene else null
	if greybox_root is Node3D:
		(greybox_root as Node3D).visible = not use_role_asset

func _apply_role_asset_config() -> void:
	_set_role_asset_state("idle")

func _set_role_asset_state(state_name: String) -> void:
	if role_asset_scene and role_asset_scene.has_method("set_state"):
		role_asset_scene.set_state(state_name)

func _set_role_asset_focus(is_focused: bool) -> void:
	var plush_mesh := role_asset_scene.get_node_or_null("GodotPlushModel/Rig/Skeleton3D/GodotPlushMesh") if role_asset_scene else null
	if plush_mesh is MeshInstance3D:
		var mat := StandardMaterial3D.new()
		mat.albedo_color = Color(0.95, 0.85, 0.35, 1.0) if is_focused else Color(1.0, 1.0, 1.0, 1.0)
		(plush_mesh as MeshInstance3D).material_overlay = mat
