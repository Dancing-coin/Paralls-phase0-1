extends Node3D

@onready var player: CharacterBody3D = $PlayerCharacter
@onready var coordinator: Node = $CombatCoordinator
@onready var camera: Camera3D = $FollowCamera

var camera_yaw := 0.0
var camera_pitch := 0.18
var camera_orbiting := false
var jump_remaining := 0.0
var jump_vertical_speed := 0.0
const CAMERA_DISTANCE := 3.15
const JUMP_SPEED := 4.5
const MOUSE_LOOK_SENSITIVITY := 0.006
const MOUSE_PITCH_SENSITIVITY := 0.004


func _ready() -> void:
	# Third-person action-game default: the mouse controls the camera without
	# requiring a held RMB. RMB remains available as a capture/release toggle.
	camera_orbiting = true
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	_build_collision()
	for actor_name in ["PlayerCharacter", "AgentCharacterJK", "AgentCharacterT"]:
		get_node("%s/Nameplate" % actor_name).visible = false
		get_node("%s/PerceptionConeDebug" % actor_name).visible = false
	$CityStreetsEnvironment/EnvironmentNavigation.bake_navigation_mesh(false)
	if OS.get_environment("PARALLS_STREET_PROBE") == "1":
		call_deferred("_probe")
	elif OS.get_environment("PARALLS_STREET_PROBE") == "2":
		call_deferred("_probe_combat")


func _physics_process(delta: float) -> void:
	var move_axis := _read_directional_input()
	var camera_forward := Vector3(-sin(camera_yaw), 0.0, cos(camera_yaw))
	# Godot camera screen-right is the negative X basis for this orbit frame.
	# Using the opposite sign makes left/right arrow movement appear reversed.
	var camera_right := Vector3(-cos(camera_yaw), 0.0, -sin(camera_yaw))
	var world_direction := (camera_right * move_axis.x) + (camera_forward * -move_axis.y)
	if world_direction.length() > 0.01:
		world_direction = world_direction.normalized()
	var wants_run := Input.is_action_pressed("phase0_run")
	var jump_type := "none"
	if Input.is_action_just_pressed("phase0_jump") and player.is_on_floor() and jump_remaining <= 0.0:
		jump_type = "single_leg" if wants_run else "two_foot"
		jump_remaining = 0.5
		jump_vertical_speed = JUMP_SPEED
	if jump_remaining > 0.0:
		jump_remaining = maxf(0.0, jump_remaining - delta)
		jump_vertical_speed -= 9.8 * delta
		player.velocity.y = jump_vertical_speed
		jump_type = "single_leg" if wants_run else "two_foot"
	# Keep the character's front aligned with the camera's horizontal forward
	# direction. WASD moves relative to that facing without desynchronizing
	# the third-person view from the player body.
	var look_target := player.global_position + camera_forward * 2.0
	var control_grounded := player.is_on_floor() and jump_type == "none"
	player.begin_embodied_control_frame(player.global_position, world_direction, look_target, control_grounded, wants_run, "run" if wants_run else "walk", "stand", jump_type)
	# Keep both opponents in an explicit face-off stance toward the player.
	# Their imported assets use the opposite forward axis from the player shell,
	# so the runtime look target is authoritative instead of relying on spawn yaw.
	$AgentCharacterJK.set_look_target(player.global_position + Vector3(0.0, 1.0, 0.0))
	$AgentCharacterT.set_look_target(player.global_position + Vector3(0.0, 1.0, 0.0))
	var orbit_offset := Vector3(sin(camera_yaw) * CAMERA_DISTANCE, 1.95 + camera_pitch * 0.55, -cos(camera_yaw) * CAMERA_DISTANCE)
	var desired_camera := player.global_position + Vector3(0.0, 1.95, -3.15)
	desired_camera = player.global_position + orbit_offset
	camera.global_position = camera.global_position.lerp(desired_camera, 0.22)
	var camera_look_target := player.global_position + Vector3(0.0, 1.28, 3.4)
	camera_look_target = player.global_position + camera_forward * 3.4 + Vector3(0.0, 1.28 + camera_pitch, 0.0)
	# camera.look_at(player.global_position + Vector3(0.0, 1.28, 3.4), Vector3.UP)
	camera.look_at(camera_look_target, Vector3.UP)
	$AgentCharacterJK/TargetRing.visible = coordinator.target_actor_id == "char_a"
	$AgentCharacterT/TargetRing.visible = coordinator.target_actor_id == "char_b"


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_RIGHT:
		camera_orbiting = event.pressed
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED if camera_orbiting else Input.MOUSE_MODE_VISIBLE
		return
	if event is InputEventMouseMotion and camera_orbiting:
		camera_yaw = wrapf(camera_yaw - event.relative.x * MOUSE_LOOK_SENSITIVITY, -PI, PI)
		camera_pitch = clampf(camera_pitch - event.relative.y * MOUSE_PITCH_SENSITIVITY, -0.45, 0.55)
		return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
		coordinator.request_attack("street_bandage", coordinator.target_actor_id, "", {}, "action:melee.unarmed_punch")
		return
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_TAB:
		coordinator.target_actor_id = "char_b" if coordinator.target_actor_id == "char_a" else "char_a"
		coordinator.state_changed.emit()
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_Q:
		coordinator.request_attack("street_bandage", coordinator.target_actor_id, "", {}, "action:melee.sword_slash")


func _read_directional_input() -> Vector2:
	# Locomotion is mapped exclusively through the WASD phase0 actions.
	# Keeping the action names also lets deterministic probes inject movement.
	return Input.get_vector("phase0_move_left", "phase0_move_right", "phase0_move_forward", "phase0_move_backward")


func _probe_combat() -> void:
	var deadline := Time.get_ticks_msec() + 8000
	while Time.get_ticks_msec() < deadline and not coordinator.connected:
		await get_tree().process_frame
	if not coordinator.connected:
		print("street_combat_probe:backend_connected=false")
		get_tree().quit(1)
		return
	print("street_combat_probe:backend_connected=true")
	var skeletons := 0
	for actor_name in ["PlayerCharacter", "AgentCharacterJK", "AgentCharacterT"]:
		var actor := get_node(actor_name)
		var skin := actor.get_node("VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/StreetCharacterSkin")
		if skin.has_qualified_skeleton():
			skeletons += 1
	print("street_combat_probe:skeletons=%s" % skeletons)
	var environment: Node3D = $CityStreetsEnvironment/EnvironmentVisual
	var collision: Node3D = $CityStreetsEnvironment/EnvironmentCollision
	var navigation: NavigationRegion3D = $CityStreetsEnvironment/EnvironmentNavigation
	var environment_ok := not environment.find_children("*", "MeshInstance3D", true, false).is_empty()
	var collision_ok := not collision.find_children("*", "CollisionShape3D", true, false).is_empty()
	var navigation_ok := navigation.navigation_mesh != null and navigation.navigation_mesh.get_polygon_count() > 0
	print("street_combat_probe:environment=%s:collision=%s:navigation=%s" % [str(environment_ok).to_lower(), str(collision_ok).to_lower(), str(navigation_ok).to_lower()])
	print("street_combat_probe:hud_observed=%s" % str(is_instance_valid($StreetCombatHUD) and $StreetCombatHUD.visible).to_lower())
	Input.action_press("phase0_move_forward")
	# Move into the staged combat pocket while still proving player locomotion.
	# The probe must preserve line-of-sight evidence for the first authority attempt.
	for _frame in range(50):
		await get_tree().physics_frame
	Input.action_release("phase0_move_forward")
	print("street_combat_probe:player_position=%s:jk_position=%s:t_position=%s" % [player.global_position, $AgentCharacterJK.global_position, $AgentCharacterT.global_position])
	# Let the live pose stream publish the final post-movement positions before
	# submitting the first authority attempt. This exercises the real transport
	# ordering instead of relying on a local position shortcut.
	for _frame in range(12):
		await get_tree().physics_frame
	var player_attempt: String = await coordinator.request_attack("street_bandage", "char_a", "probe-player-hit")
	if player_attempt.is_empty():
		print("street_combat_probe:player_hit=false:send_failed")
		get_tree().quit(1)
		return
	deadline = Time.get_ticks_msec() + 5000
	while Time.get_ticks_msec() < deadline and not coordinator.results_by_attempt.has(player_attempt):
		await get_tree().process_frame
	var player_result: Dictionary = coordinator.results_by_attempt.get(player_attempt, {})
	print("street_combat_probe:player_result=%s:hp=%s" % [JSON.stringify(player_result), coordinator.actor_hp["char_a"]])
	var player_ok: bool = str(player_result.get("outcome", "")) == "committed" and int(coordinator.actor_hp["char_a"]) == 80
	print("street_combat_probe:player_hit=%s" % str(player_ok).to_lower())
	var playback_ok := await _probe_imported_action_catalog()
	print("street_combat_probe:imported_attack_playback=%s" % str(playback_ok).to_lower())
	var agent_ok := false
	var agent_attempt: String = await coordinator.request_attack("char_a", "street_bandage", "probe-agent-hit")
	if not agent_attempt.is_empty():
		deadline = Time.get_ticks_msec() + 5000
		while Time.get_ticks_msec() < deadline and not coordinator.results_by_attempt.has(agent_attempt):
			await get_tree().process_frame
		var agent_result: Dictionary = coordinator.results_by_attempt.get(agent_attempt, {})
		print("street_combat_probe:agent_result=%s:hp=%s" % [JSON.stringify(agent_result), coordinator.actor_hp["street_bandage"]])
		agent_ok = str(agent_result.get("outcome", "")) == "committed" and int(coordinator.actor_hp["street_bandage"]) == 80
	print("street_combat_probe:agent_hit=%s" % str(agent_ok).to_lower())
	var duplicate_sent: bool = await coordinator.replay_attempt(player_attempt)
	await get_tree().create_timer(0.4).timeout
	var duplicate_replayed: bool = duplicate_sent and coordinator.duplicate_attempts.has(player_attempt) and int(coordinator.actor_hp["char_a"]) == 80
	print("street_combat_probe:duplicate_replayed=%s" % str(duplicate_replayed).to_lower())
	var stale_attempt: String = await coordinator.request_attack("street_bandage", "char_a", "probe-stale", {"actor:character:street_bandage": 0})
	var stale_result: Dictionary = await _wait_for_result(stale_attempt)
	var stale_rejected: bool = str(stale_result.get("outcome", "")) == "rejected" and str(stale_result.get("failed_code", "")) == "revision_conflict" and int(coordinator.actor_hp["char_a"]) == 80
	print("street_combat_probe:stale_rejected=%s" % str(stale_rejected).to_lower())
	var recovery_attempt: String = await coordinator.request_attack("street_bandage", "char_a", "probe-recovery")
	var recovery_result: Dictionary = await _wait_for_result(recovery_attempt)
	var recovery_committed: bool = str(recovery_result.get("outcome", "")) == "committed" and int(coordinator.actor_hp["char_a"]) == 60
	print("street_combat_probe:recovery_committed=%s" % str(recovery_committed).to_lower())
	var duplicate_stale_recovery := duplicate_replayed and stale_rejected and recovery_committed
	print("street_combat_probe:duplicate_stale_recovery=%s" % str(duplicate_stale_recovery).to_lower())
	var sword_attempt: String = await coordinator.request_attack("street_bandage", "char_a", "probe-sword-slash", {}, "action:melee.sword_slash")
	var sword_result: Dictionary = await _wait_for_result(sword_attempt)
	var sword_projection: Dictionary = sword_result.get("committed_projection", {})
	var sword_ok := str(sword_result.get("outcome", "")) == "committed" and str(sword_projection.get("semantic_action_id", "")) == "action:melee.sword_slash"
	print("street_combat_probe:sword_slash_authority=%s" % str(sword_ok).to_lower())
	await get_tree().process_frame
	var hud_ok: bool = $StreetCombatHUD.get_node("SkillBar/SkillNames").text == "拳击       剑击       奔跑       锁定" and $StreetCombatHUD.get_node("StaminaBar/StaminaValue").text == "%s/100" % coordinator.actor_stamina["street_bandage"]
	print("street_combat_probe:hud_actions_and_stamina=%s" % str(hud_ok).to_lower())
	get_tree().quit(0 if player_ok and agent_ok and duplicate_stale_recovery and playback_ok and sword_ok and hud_ok else 1)


func _wait_for_result(attempt_id: String) -> Dictionary:
	if attempt_id.is_empty():
		return {}
	var deadline := Time.get_ticks_msec() + 5000
	while Time.get_ticks_msec() < deadline and not coordinator.results_by_attempt.has(attempt_id):
		await get_tree().process_frame
	return coordinator.results_by_attempt.get(attempt_id, {})


func _probe_imported_attack_playback() -> bool:
	var actor := player
	var skin := actor.get_node("VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/StreetCharacterSkin")
	var settle_deadline := Time.get_ticks_msec() + 2500
	while Time.get_ticks_msec() < settle_deadline and skin.get_current_clip_name().to_lower().ends_with("boxing"):
		await get_tree().process_frame
	var before: String = skin.get_current_clip_name()
	var registry := CharacterEmbodimentAssetRegistry.new()
	var presentation := RolePresentationAdapter.new(registry, skin)
	var playback: Dictionary = presentation.apply_input({"package_id": str(actor.get_meta("package_id", "")), "semantic_action_id": "action:melee.unarmed_punch", "claims": []})
	await get_tree().create_timer(0.12).timeout
	var during: String = skin.get_current_clip_name()
	await get_tree().create_timer(0.55).timeout
	var near_contact: String = skin.get_current_clip_name()
	var after_deadline := Time.get_ticks_msec() + 2500
	while Time.get_ticks_msec() < after_deadline and skin.get_current_clip_name().to_lower().ends_with("boxing"):
		await get_tree().process_frame
	var after: String = skin.get_current_clip_name()
	print("street_combat_probe:attack_clips=%s,%s,%s,%s" % [before, during, near_contact, after])
	return bool(playback.get("accepted", false)) and before.to_lower().ends_with("idle") and during.to_lower().ends_with("boxing") and near_contact.to_lower().ends_with("boxing") and after.to_lower().ends_with("idle")


func _probe_imported_action_catalog() -> bool:
	var registry := CharacterEmbodimentAssetRegistry.new()
	var action_ids := ["action:melee.unarmed_punch", "action:melee.sword_slash"]
	var all_accepted := true
	for actor_name in ["PlayerCharacter", "AgentCharacterJK", "AgentCharacterT"]:
		var actor := get_node(actor_name)
		var skin := actor.get_node("VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/StreetCharacterSkin")
		for action_id in action_ids:
			var adapter := RolePresentationAdapter.new(registry, skin)
			var playback: Dictionary = adapter.apply_input({"package_id": str(actor.get_meta("package_id", "")), "semantic_action_id": action_id, "claims": []})
			var clip := str(playback.get("selected_profile", {}).get("clip_ref", ""))
			var current := str(skin.get_current_clip_name()).to_lower()
			var accepted := bool(playback.get("accepted", false)) and not clip.is_empty() and current.ends_with(clip.to_lower())
			print("street_combat_probe:action=%s:%s:%s" % [actor_name, action_id, str(accepted).to_lower()])
			all_accepted = all_accepted and accepted
		for clip in ["idle", "walking", "running", "jump", "boxing"]:
			var clip_ok: bool = bool(skin.has_clip(clip))
			print("street_combat_probe:clip=%s:%s:%s" % [actor_name, clip, str(clip_ok).to_lower()])
			all_accepted = all_accepted and clip_ok
		var sword_clip_ok: bool = bool(skin.has_clip("sword attack") or skin.has_clip("SWORD ATTACK"))
		print("street_combat_probe:clip=%s:sword attack:%s" % [actor_name, str(sword_clip_ok).to_lower()])
		all_accepted = all_accepted and sword_clip_ok
	return all_accepted


func _build_collision() -> void:
	var source := $CityStreetsEnvironment/EnvironmentCollision as Node3D
	for mesh in source.find_children("*", "MeshInstance3D", true, false):
		(mesh as MeshInstance3D).create_trimesh_collision()


func _probe() -> void:
	var skeletons := 0
	var animated := 0
	for actor_name in ["PlayerCharacter", "AgentCharacterJK", "AgentCharacterT"]:
		var actor := get_node(actor_name)
		var skin := actor.get_node("VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/StreetCharacterSkin")
		if skin.has_qualified_skeleton():
			skeletons += 1
		var manifest_path := "res://assets/active/%s/manifest.json" % skin.package_id
		var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(manifest_path))
		var attack_clip := str(manifest.get("actions", [])[0].get("clip_ref", ""))
		if skin.has_clip(str(manifest.get("clip_aliases", {}).get("idle", ""))) and skin.has_clip(str(manifest.get("clip_aliases", {}).get("walk_forward", ""))) and skin.has_clip(attack_clip):
			animated += 1
		print("street_combat_probe:actor=%s:skeleton=%s:animations=%s:current=%s" % [actor_name, skin.has_qualified_skeleton(), skin.has_clip(attack_clip), skin.get_current_clip_name()])
	print("street_combat_probe:skeletons=%s" % skeletons)
	print("street_combat_probe:idle_walk_attack=%s" % animated)
	var environment: Node3D = $CityStreetsEnvironment/EnvironmentVisual
	var collision: Node3D = $CityStreetsEnvironment/EnvironmentCollision
	var navigation: NavigationRegion3D = $CityStreetsEnvironment/EnvironmentNavigation
	var visual_ok := not environment.find_children("*", "MeshInstance3D", true, false).is_empty()
	var collision_ok := not collision.find_children("*", "CollisionShape3D", true, false).is_empty()
	var navigation_ok := navigation.navigation_mesh != null and navigation.navigation_mesh.get_polygon_count() > 0
	print("street_combat_probe:nav_source_meshes=%s:source_mode=%s:root_mode=%s:parsed_type=%s:mesh_type=%s:polygons=%s" % [$CityStreetsEnvironment/EnvironmentNavigation/NavigationSource.find_children("*", "MeshInstance3D", true, false).size(), navigation.navigation_mesh.geometry_source_geometry_mode, NavigationMesh.SOURCE_GEOMETRY_ROOT_NODE_CHILDREN, navigation.navigation_mesh.geometry_parsed_geometry_type, NavigationMesh.PARSED_GEOMETRY_MESH_INSTANCES, navigation.navigation_mesh.get_polygon_count()])
	print("street_combat_probe:environment=%s:collision=%s:navigation=%s" % [str(visual_ok).to_lower(), str(collision_ok).to_lower(), str(navigation_ok).to_lower()])
	for _frame in range(45):
		await get_tree().physics_frame
	camera_yaw = 0.9
	for _frame in range(24):
		await get_tree().physics_frame
	var camera_forward := Vector3(-sin(camera_yaw), 0.0, cos(camera_yaw))
	var body_faces_camera := (-player.global_basis.z).dot(camera_forward) > 0.98
	var player_clip := str(player.role_asset_scene.get_current_clip_name()).to_lower()
	var turn_clip_inactive := not player_clip.ends_with("left turn") and not player_clip.ends_with("right turn")
	print("street_combat_probe:camera_body_facing=%s:turn_clip_inactive=%s" % [str(body_faces_camera).to_lower(), str(turn_clip_inactive).to_lower()])
	get_tree().quit(0 if skeletons == 3 and animated == 3 and visual_ok and collision_ok and navigation_ok and body_faces_camera and turn_clip_inactive else 1)
