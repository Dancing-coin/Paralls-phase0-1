extends SceneTree


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var scene := load("res://scenes/phase0/CharacterReplica.tscn") as PackedScene
	if scene == null:
		_fail("compatibility scene missing")
		return
	var replica: Node = scene.instantiate()
	root.add_child(replica)
	await process_frame
	var emitted := [0]
	replica.compatibility_call.connect(func(_diagnostic: Dictionary) -> void: emitted[0] += 1)
	replica.compatibility_strict_mode = true
	replica.begin_embodied_control_frame(Vector3.ZERO, Vector3(1, 0, 0), Vector3.FORWARD, true, false, "walk", "stand", "none")
	if str(replica.latest_control_intent.get("source_kind", "")) != "compatibility" or not replica.is_embodied_control_active():
		_fail("control intent was not forwarded")
		return
	replica.apply_embodied_pose_sync(Vector3.ZERO, Vector3.ZERO, Vector3.FORWARD, true)
	if str(replica.latest_control_intent.get("source_kind", "")) != "compatibility":
		_fail("pose intent was not forwarded")
		return
	replica.perform_action("sword_swing")
	if replica.runtime_state.get_requested_action() != "sword_swing":
		_fail("action was not realized")
		return
	replica.perform_action("sword_swing")
	if not replica.latest_action_admission.get("frame", {}).get("admitted", []).is_empty():
		_fail("duplicate same-tick action ignored occupancy")
		return
	replica.perform_action("")
	if replica.runtime_state.get_requested_action() != "":
		_fail("empty action did not clear requested state")
		return
	var expected_reviewed: Dictionary = replica.play_compatibility_reviewed_action_atom({"action_tag": "missing", "animation_clip_ref": "missing", "phase": "active"})
	var forwarded_reviewed: Dictionary = replica.play_reviewed_action_atom("missing", "missing", "active")
	if forwarded_reviewed != expected_reviewed:
		_fail("reviewed atom result was not forwarded")
		return
	replica.restore_reviewed_action_playback()
	if replica.apply_presentation_asset_binding({}):
		_fail("asset binding rejection was not forwarded")
		return
	var before_internal: int = replica.compatibility_call_count
	replica._realize_action_request("interact")
	if replica.compatibility_call_count != before_internal:
		_fail("actor internal action was counted as compatibility")
		return
	for sample in [
		"body.global_transform = Transform3D.IDENTITY",
		"position += Vector3.ONE",
		"animation_player.play(\"idle\")",
		"animation_tree[\"parameters/state\"] = \"attack\"",
		"append_authority_event({})",
	]:
		if replica._forbidden_shell_operations(sample).is_empty():
			_fail("strict guard allowed " + sample)
			return
	if replica.compatibility_call_count != emitted[0] or replica.compatibility_call_diagnostics.size() > 128:
		_fail("diagnostic count or history mismatch")
		return
	print("CHARACTER_REPLICA_FORWARDING_PROBE_PASS count=", emitted[0])
	quit()


func _fail(message: String) -> void:
	push_error("CHARACTER_REPLICA_FORWARDING_PROBE_FAIL " + message)
	quit(1)
