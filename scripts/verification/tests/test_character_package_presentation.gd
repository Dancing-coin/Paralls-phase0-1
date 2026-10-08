extends SceneTree

var failures: Array[String] = []

func _initialize() -> void:
	call_deferred("_run")

func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)

func _run() -> void:
	var scene := load("res://scenes/phase0/StreetCombatActorControlDemo.tscn") as PackedScene
	var instance := scene.instantiate()
	root.add_child(instance)
	await process_frame
	var control: Node = instance.get_node("CharacterControlFoundation")
	_check(control.call("get_actors").size() == 4, "original three actors plus knight are discovered")
	var player: Node = instance.get_node("PlayerCharacter")
	_check(player.get_meta("package_id") == "female_bandage_external", "original player package is preserved")
	_check(player.get("actor_id") == "street_bandage", "original player identity is preserved")
	_check(instance.get_node("AgentCharacterJK").get_meta("package_id") == "female_jk_external", "JK package is preserved")
	_check(instance.get_node("AgentCharacterT").get_meta("package_id") == "female_t_external", "T package is preserved")
	var actor: Node = instance.get_node_or_null("KnightCharacter")
	_check(actor != null, "knight is an additional actor")
	if actor == null:
		instance.queue_free()
		await process_frame
		quit(1)
		return
	_check(actor.get("actor_id") == "crusader_knight", "knight has independent identity")
	var presenter: Node = actor.get("role_asset_scene")
	_check(presenter.get_script().resource_path == "res://scripts/character/CharacterPackagePresentationAdapter.gd", "knight must use generic package presenter")
	if presenter.has_method("get_registration_status"):
		_check(bool(presenter.call("get_registration_status").get("accepted", false)), "package, skeleton and native library register")
		var idle: Dictionary = presenter.call("resolve_motion_realization", "action:locomotion.idle")
		_check(bool(idle.get("accepted", false)), "registered native idle resolves")
		_check(str(idle.get("motion_library_id", "")) == "motionlib:crusader_knight.native@1", "idle resolves knight library")
		_check(str(idle.get("realization_mode", "")) == "package_native", "knight does not use street library")
		var attack: Dictionary = presenter.call("resolve_motion_realization", "action:melee.sword_slash")
		_check(not bool(attack.get("accepted", false)), "withdrawn combat clip cannot become qualified attack")
		for pair: Array in [["idle", "idle_guard"], ["walk", "walk_guard"], ["run", "run_charge"], ["jump", "jump_command"]]:
			presenter.call("set_state", pair[0])
			var played := str(presenter.call("get_current_clip_name"))
			_check(played.ends_with(str(pair[1])), "state plays native clip: " + str(pair[0]) + " got " + played)
		_check(presenter.call("has_qualified_skeleton"), "mapped bones exist in actual imported skeleton")
		_check(actor.get("role_asset_scene") == presenter, "actor selected generic package presenter")
	else:
		_check(false, "presenter exposes registration outcome")
	for step: int in range(3):
		control.call("select_next_actor")
	_check(control.call("get_active_actor") == actor, "fourth actor can be controlled")
	await process_frame
	var coordinator: Node = instance.get_node("CombatCoordinator")
	_check(coordinator.get("player_actor_id") == "crusader_knight", "HUD coordinator follows actual knight identity")
	_check(instance.get_node("StreetCombatHUD/PlayerCard/PlayerName").get("text").begins_with("KNIGHT"), "HUD displays knight instead of original player")
	_check(instance.get_node("StreetCombatHUD/PlayerCard/HealthValue").get("text") == "--", "preview HUD shows no invented knight HP")
	_check(not coordinator.get("actor_hp").has("crusader_knight"), "local knight is not given backend combat state")
	instance.call("_request_attack", "action:melee.sword_slash")
	_check(coordinator.get("pending_attempts").is_empty(), "preview knight submits no combat attempt")
	control.call("select_next_actor")
	_check(control.call("get_active_actor") == player, "four actor switching returns to original player")
	instance.queue_free()
	await process_frame
	print("character_package_presentation failures=", failures)
	quit(0 if failures.is_empty() else 1)
