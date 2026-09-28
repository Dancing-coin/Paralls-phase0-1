extends SceneTree

var _failed := false

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var scene: Node = load("res://scenes/phase0/StreetCombatDemo.tscn").instantiate()
	root.add_child(scene)
	await process_frame
	await physics_frame
	await physics_frame
	for _frame in range(75):
		await physics_frame
	var actors := [scene.get_node("PlayerCharacter"), scene.get_node("AgentCharacterJK"), scene.get_node("AgentCharacterT")]
	scene.set_physics_process(false)
	for actor in actors:
		(actor as Node).set_physics_process(false)
	var skeletons := 0
	var controller_bound := 0
	var active_animation_trees := 0
	var playback_bindings := 0
	var valid_animation_player_bindings := 0
	var state_machine_catalogs := 0
	var six_clip_catalogs := 0
	var extra_actions_blocked := 0
	var reference_idle_count := 0
	var reference_run_speed := false
	var root_track_qualified := false
	for actor_index: int in range(actors.size()):
		var actor: Node = actors[actor_index]
		var skin := actor.get_node("VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/StreetCharacterSkin")
		if skin.has_qualified_skeleton():
			skeletons += 1
		if skin.get_node_or_null("RoleAnimationController") != null and skin.get_node_or_null("RootMotionSampler") != null:
			controller_bound += 1
		if skin.has_method("is_animation_tree_active") and skin.is_animation_tree_active():
			active_animation_trees += 1
		if skin.has_method("get_animation_tree_path") and not skin.get_animation_tree_path().is_empty():
			playback_bindings += 1
		if skin.has_method("has_valid_animation_player_binding") and skin.has_valid_animation_player_binding():
			valid_animation_player_bindings += 1
		var controller := skin.get_node_or_null("RoleAnimationController")
		if controller != null and controller.has_method("get_available_states"):
			var states: PackedStringArray = controller.get_available_states()
			if states.size() == 6 and ["idle", "walk", "run", "jump", "boxing", "sword_attack"].all(func(state_name: String) -> bool: return states.has(state_name)):
				state_machine_catalogs += 1
		if skin.get_source_animation_clips().size() == 6:
			six_clip_catalogs += 1
		if not skin.play_source_state("left_turn"):
			extra_actions_blocked += 1
		if actor_index > 0 and skin.get_playback_state() == "idle":
			reference_idle_count += 1
		if actor_index == 0:
			reference_run_speed = actor.run_speed_for_actor() > actor.move_speed
		print("character_replica_actor:%s:animation_tree_active=%s:playback=%s:states=%s" % [actor.name, str(skin.is_animation_tree_active()).to_lower(), skin.get_playback_state(), JSON.stringify(Array(controller.get_available_states()) if controller != null and controller.has_method("get_available_states") else [])])
		if actor_index == 1:
			root_track_qualified = skin.has_root_motion_track("walking")
		await _skin_probe(skin)
	scene.set_physics_process(true)
	for actor in actors:
		(actor as Node).set_physics_process(true)
	Input.action_press("phase0_move_forward")
	Input.action_press("phase0_run")
	for _frame in range(40):
		await physics_frame
	var player := actors[0] as CharacterBody3D
	var player_skin := player.get_node("VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/StreetCharacterSkin")
	var player_run_playback: bool = str(player_skin.get_playback_state()) == "run"
	var player_run_motion: bool = Vector2(player.velocity.x, player.velocity.z).length() > 4.0
	Input.action_release("phase0_move_forward")
	Input.action_release("phase0_run")
	var mover := actors[1] as CharacterBody3D
	var before := mover.global_position
	mover.set_driver_mode(0)
	mover.set_move_target(before + Vector3(0.0, 0.0, -0.8))
	for _i in range(30):
		await physics_frame
	var moved := mover.global_position.distance_to(before) > 0.01
	var walls: int = scene.find_children("*", "StaticBody3D", true, false).size()
	var structure_passed: bool = skeletons == 3 and controller_bound == 3 and active_animation_trees == 3 and playback_bindings == 3 and valid_animation_player_bindings == 3 and state_machine_catalogs == 3 and six_clip_catalogs == 3 and extra_actions_blocked == 3 and reference_idle_count == 2 and reference_run_speed and player_run_playback and player_run_motion and root_track_qualified and moved
	var result := {"skeletons": skeletons, "controller_bound": controller_bound, "active_animation_trees": active_animation_trees, "playback_bindings": playback_bindings, "valid_animation_player_bindings": valid_animation_player_bindings, "state_machine_catalogs": state_machine_catalogs, "six_clip_catalogs": six_clip_catalogs, "extra_actions_blocked": extra_actions_blocked, "reference_idle_count": reference_idle_count, "reference_run_speed": reference_run_speed, "player_run_playback": player_run_playback, "player_run_motion": player_run_motion, "root_track_qualified": root_track_qualified, "moved": moved, "static_body_count": walls, "motor_move_and_slide_owner": 1, "action_state_checks_passed": not _failed, "passed": structure_passed and not _failed}
	print("character_replica_convergence_probe:" + JSON.stringify(result))
	_failed = not bool(result["passed"])
	quit(1 if _failed else 0)

func _skin_probe(skin: Node) -> void:
	var initial_state: String = str(skin.get_playback_state())
	print("character_replica_skin_probe:initial=%s:clip=%s" % [initial_state, skin.get_current_clip_name()])
	if skin.has_method("restore_reviewed_action_playback"):
		skin.restore_reviewed_action_playback()
	if skin.has_method("play_locomotion_state"):
		skin.play_locomotion_state("idle")
	await _wait_until_state(skin, "idle", 0.5)
	if skin.has_method("play_locomotion_state"):
		skin.play_locomotion_state("walk")
	else:
		skin.set_state("walk")
	await _wait_until_state(skin, "walk", 0.5)
	print("character_replica_skin_probe:walk_state=%s:clip=%s" % [skin.get_playback_state(), skin.get_current_clip_name()])
	if not str(skin.get_current_clip_name()).to_lower().ends_with("walking") and not str(skin.get_current_clip_name()).to_lower().ends_with("walk"):
		_failed = true
	if skin.get_playback_state() != "walk":
		_failed = true
	if skin.has_method("play_locomotion_state"):
		skin.play_locomotion_state("run")
	await _wait_until_state(skin, "run", 0.5)
	print("character_replica_skin_probe:run_state=%s:clip=%s" % [skin.get_playback_state(), skin.get_current_clip_name()])
	if skin.get_playback_state() != "run":
		_failed = true
	if skin.has_method("play_locomotion_state"):
		skin.play_locomotion_state("jump")
	await _wait_until_state(skin, "jump", 0.5)
	print("character_replica_skin_probe:jump_state=%s:clip=%s" % [skin.get_playback_state(), skin.get_current_clip_name()])
	if skin.get_playback_state() != "jump":
		_failed = true
	var action: Dictionary = skin.play_reviewed_action_atom("boxing", "boxing", "active")
	if not bool(action.get("accepted", false)):
		_failed = true
	await _wait_until_state(skin, "boxing", 0.5)
	print("character_replica_skin_probe:boxing_state=%s:clip=%s" % [skin.get_playback_state(), skin.get_current_clip_name()])
	if not str(skin.get_current_clip_name()).to_lower().ends_with("boxing"):
		_failed = true
	if skin.get_playback_state() != "boxing":
		_failed = true
	await _wait_until_not_state(skin, "boxing", 2.5)
	print("character_replica_skin_probe:boxing_recovered_state=%s:clip=%s" % [skin.get_playback_state(), skin.get_current_clip_name()])
	if not skin.has_method("consume_root_motion_delta"):
		_failed = true
	var sword_action: Dictionary = skin.play_reviewed_action_atom("sword_attack", "sword attack", "active")
	print("character_replica_skin_probe:sword_accepted=%s:clip=%s" % [str(sword_action.get("accepted", false)).to_lower(), skin.get_current_clip_name()])
	if not bool(sword_action.get("accepted", false)):
		_failed = true
	await _wait_until_state(skin, "sword_attack", 0.5)
	print("character_replica_skin_probe:sword_state=%s:clip=%s" % [skin.get_playback_state(), skin.get_current_clip_name()])
	if skin.get_playback_state() != "sword_attack":
		_failed = true
	await _wait_until_not_state(skin, "sword_attack", 2.5)
	print("character_replica_skin_probe:sword_recovered_state=%s:clip=%s" % [skin.get_playback_state(), skin.get_current_clip_name()])
	if skin.get_playback_state() == "sword_attack":
		_failed = true


func _wait_until_not_state(skin: Node, state_name: String, timeout_seconds: float) -> void:
	var deadline := Time.get_ticks_msec() + int(timeout_seconds * 1000.0)
	while Time.get_ticks_msec() < deadline and str(skin.get_playback_state()) == state_name:
		await process_frame


func _wait_until_state(skin: Node, state_name: String, timeout_seconds: float) -> void:
	var deadline := Time.get_ticks_msec() + int(timeout_seconds * 1000.0)
	while Time.get_ticks_msec() < deadline and str(skin.get_playback_state()) != state_name:
		await process_frame
