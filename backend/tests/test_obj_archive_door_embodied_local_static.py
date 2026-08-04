from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_door_host_uses_the_existing_motor_owner_and_reviewed_atom_contract() -> None:
    host = _read("scripts/interaction/ArchiveDoorEmbodiedActionHost.gd")
    scene = _read("scenes/phase0/CharacterBase.tscn")
    main_demo = _read("scenes/phase0/MainDemo.tscn")
    replica = _read("scripts/character/CharacterReplica.gd")

    assert "class_name ArchiveDoorEmbodiedActionHost" in host
    assert "Phase0PlayerBridge" in host
    assert "set_forced_player_motion" in host
    assert "set_forced_player_motion(offset.normalized(), true)" in host
    assert "clear_forced_player_motion" in host
    assert "DefaultSceneActionAtomCatalog" in host
    assert "CharacterEmbodimentAssetRegistry" in host
    assert "start_move" in host
    assert "turn_to_target" in host
    assert "raise_hand" in host
    assert "tap_contact" in host
    assert "recover_balance" in host
    assert "embodied_action_request_received" in host
    assert "embodied_phase_event_emitted" in host
    assert "embodied_local_outcome_emitted" in host
    assert "measure_right_hand_to_anchor" in host
    assert "move_and_slide(" not in host
    assert "global_position =" not in host
    assert 'path="res://scripts/interaction/ArchiveDoorEmbodiedActionHost.gd"' in scene
    assert '[node name="ArchiveDoorEmbodiedActionHost" type="Node" parent="."]' in scene
    assert 'door_bridge_path := NodePath("../../DefaultSceneArchiveDoorAffordanceBridge")' in host
    assert '[node name="DefaultSceneArchiveDoorAffordanceBridge" type="Node" parent="."' in main_demo
    assert "func play_reviewed_action_atom" in replica
    assert "func measure_right_hand_to_anchor" in replica


def test_door_host_refreshes_forced_facing_from_the_live_contact_geometry() -> None:
    host = _read("scripts/interaction/ArchiveDoorEmbodiedActionHost.gd")
    align_body = host.split("func _process_align() -> void:", maxsplit=1)[1].split(
        "func _process_contact() -> void:", maxsplit=1
    )[0]

    refresh = "player_bridge.set_forced_facing_yaw(desired_yaw)"
    assert refresh in align_body
    assert align_body.index(refresh) < align_body.index("if absf(wrapf(player.rotation.y - desired_yaw")


def test_reach_ik_configures_the_discovered_chain_before_entering_the_skeleton_tree() -> None:
    role_skin = _read("scripts/character/KnightRoleSkin.gd")
    combat_modifier = _read("scripts/character/KnightCombatModifier.gd")
    ik_body = role_skin.split("func _configure_skeleton_ik_reach(", maxsplit=1)[1].split(
        "func _bone_world_position", maxsplit=1
    )[0]

    root_config = 'right_hand_reach_ik.set("root_bone", skeleton.get_bone_name(right_upper_arm_bone))'
    tip_config = 'right_hand_reach_ik.set("tip_bone", skeleton.get_bone_name(right_hand_bone))'
    add_to_skeleton = "skeleton.add_child(right_hand_reach_ik)"
    assert 'NodePath("../ArchiveDoorReachTarget")' in ik_body
    assert ik_body.index(root_config) < ik_body.index(add_to_skeleton)
    assert ik_body.index(tip_config) < ik_body.index(add_to_skeleton)
    assert '"hand_world_position"' in role_skin
    assert '"anchor_world_position"' in role_skin
    assert 'skeleton.call("force_update_all_bone_transforms")' in role_skin
    assert "func begin_right_hand_modifier_reach(" in role_skin
    assert "_set_combat_modifier_right_arm_solver_active(true)" in role_skin
    assert "_set_combat_modifier_right_arm_solver_active(false)" in role_skin
    assert "func set_external_right_arm_solver_active(enabled: bool) -> void:" in combat_modifier
    assert "external_right_arm_solver_active" in combat_modifier


def test_host_ticks_contact_on_the_character_motor_physics_clock() -> None:
    host = _read("scripts/interaction/ArchiveDoorEmbodiedActionHost.gd")
    align_body = host.split("func _process_align() -> void:", maxsplit=1)[1].split(
        "func _process_contact() -> void:", maxsplit=1
    )[0]

    assert "func _physics_process(_delta: float) -> void:" in host
    assert 'elif _stage == "contact":' in host
    assert "_process_contact()" in host
    assert '_stage = "contact"' in align_body
    assert "const IK_SOLVER_SETTLE_PHYSICS_TICKS" in host
    assert "_ik_solver_settle_ticks" in host


def test_host_tries_the_existing_modifier_reach_only_after_a_measured_ik_miss() -> None:
    host = _read("scripts/interaction/ArchiveDoorEmbodiedActionHost.gd")
    replica = _read("scripts/character/CharacterReplica.gd")
    contact_body = host.split("func _process_contact() -> void:", maxsplit=1)[1].split(
        "func _advance_phase", maxsplit=1
    )[0]

    assert "func begin_right_hand_modifier_reach(" in replica
    assert "_fallback_reach_requested" in host
    assert 'replica.call("begin_right_hand_modifier_reach", contact.global_position, CONTACT_TOLERANCE_M)' in contact_body
    assert contact_body.index("_fallback_reach_requested") < contact_body.index("ik_alignment_tolerance_exceeded")


def test_contact_ik_settle_is_bounded_by_monotonic_time_as_well_as_physics_ticks() -> None:
    host = _read("scripts/interaction/ArchiveDoorEmbodiedActionHost.gd")
    align_body = host.split("func _process_align() -> void:", maxsplit=1)[1].split(
        "func _process_contact", maxsplit=1
    )[0]
    contact_body = host.split("func _process_contact() -> void:", maxsplit=1)[1].split(
        "func _advance_phase", maxsplit=1
    )[0]

    assert "const CONTACT_SETTLE_TIMEOUT_MS" in host
    assert "var _contact_started_at_ms := 0" in host
    assert "_contact_started_at_ms = Time.get_ticks_msec()" in align_body
    assert "Time.get_ticks_msec() - _contact_started_at_ms < CONTACT_SETTLE_TIMEOUT_MS" in contact_body


def test_custom_reach_modifier_is_a_local_last_resort_after_the_existing_modifier_miss() -> None:
    role_skin = _read("scripts/character/KnightRoleSkin.gd")
    scene = _read("scenes/phase0/KnightRoleSkin.tscn")
    host = _read("scripts/interaction/ArchiveDoorEmbodiedActionHost.gd")
    modifier = _read("scripts/character/ArchiveDoorReachModifier.gd")
    contact_body = host.split("func _process_contact() -> void:", maxsplit=1)[1].split(
        "func _advance_phase", maxsplit=1
    )[0]

    assert "extends SkeletonModifier3D" in modifier
    assert "func configure_bones(bones: Dictionary) -> void:" in modifier
    assert "func begin_reach(anchor_world_position: Vector3) -> bool:" in modifier
    assert "func clear_reach() -> void:" in modifier
    assert 'path="res://scripts/character/ArchiveDoorReachModifier.gd"' in scene
    assert '[node name="ArchiveDoorReachModifier" type="SkeletonModifier3D" parent="KnightScene/KnightArmature/Skeleton3D"]' in scene
    assert "func begin_archive_door_reach_modifier(" in role_skin
    assert "_custom_reach_requested" in host
    assert 'replica.call("begin_archive_door_reach_modifier", contact.global_position, CONTACT_TOLERANCE_M)' in contact_body
    assert "global_position =" not in modifier
    assert "move_and_slide(" not in modifier


def test_door_host_exposes_read_only_runtime_diagnostics_for_live_evidence() -> None:
    host = _read("scripts/interaction/ArchiveDoorEmbodiedActionHost.gd")
    probe = _read("scripts/verification/ObjArchiveDoorPhysicalEmbodimentProbe.gd")

    assert "func runtime_status() -> Dictionary:" in host
    assert '"last_transition"' in host
    assert '"last_contact_measurement"' in host
    assert '"contact_process_count"' in host
    assert "host.call(\"runtime_status\")" in probe


def test_motor_consumes_the_existing_desired_facing_field_without_a_second_owner() -> None:
    shell = _read("scripts/player/PlayerShell.gd")
    bridge = _read("scripts/player/Phase0PlayerBridge.gd")
    motor = _read("scripts/character/CharacterMotor.gd")

    assert "forced_desired_facing_yaw" in shell
    assert "set_forced_facing_yaw" in bridge
    assert "clear_forced_facing_yaw" in bridge
    assert "get_desired_facing_yaw" in motor
    assert "rotate_toward" in motor
    assert shell.count("move_and_slide(") == 0
    assert bridge.count("move_and_slide(") == 0


def test_controller_exposes_nonblocking_attempt_lifecycle_while_preserving_probe_wrapper() -> None:
    controller = _read("scripts/interaction/EmbodiedActionController.gd")

    assert "func start_realtime_attempt(" in controller
    assert "func advance_realtime_attempt(" in controller
    assert "func finish_realtime_attempt(" in controller
    assert "func run_attempt(" in controller
    assert "local_ownership_restored" in controller


def test_door_contact_outcome_reports_measured_contact_without_a_world_state_claim() -> None:
    host = _read("scripts/interaction/ArchiveDoorEmbodiedActionHost.gd")

    assert '"observation_rule_ref": "observation_rule:archive_door_contact:v1"' in host
    assert '_finish_attempt("contact_observed", "", true' in host
    assert '"hand_alignment_error_m": hand_alignment_error_m' in host
    assert '"observed_state": "open"' not in host
    assert "object_observation" not in host


def test_backend_bridge_bootstraps_embodied_controller_enrollment_and_binds_once_per_enrollment() -> None:
    bridge = _read("scripts/autoload/BackendBridge.gd")

    assert "var _embodied_controller_enrollment: Dictionary = {}" in bridge
    assert "var _embodied_controller_bind_sent := false" in bridge
    assert "func load_embodied_controller_enrollment_from_environment() -> int:" in bridge
    assert 'OS.get_environment("PARALLS_EMBODIED_CONTROLLER_ENROLLMENT_JSON")' in bridge
    assert 'if str(enrollment.get("credential_kind", "")) != "trusted_local_launch":' in bridge
    assert "func _emit_pending_embodied_controller_bind() -> void:" in bridge
    assert '"message_type": "embodied_controller_bind"' in bridge
    assert "_embodied_controller_bind_sent = true" in bridge
    assert "_emit_pending_embodied_controller_bind()" in bridge
    assert "_embodied_controller_enrollment.clear()" in bridge


def test_main_demo_registers_archive_door_requests_for_preflight_recovery() -> None:
    controller = _read("scripts/phase0/MainDemoController.gd")
    bus = _read("scripts/autoload/LocalPresentationBus.gd")

    assert "signal archive_door_request_registered(payload)" in bus
    assert "func _register_archive_door_request(" in controller
    assert '"target_object_id": target_object_id' in controller
    assert '"interaction_type": interaction_type' in controller
    assert '"correlation_id": "interact:%s" % descriptor.get("producer_ts", 0)' in controller
    assert 'bus.emit_signal("archive_door_request_registered", payload)' in controller


def test_door_host_recovers_on_preflight_constraint_settlement_cancel_and_resync() -> None:
    host = _read("scripts/interaction/ArchiveDoorEmbodiedActionHost.gd")
    replica = _read("scripts/character/CharacterReplica.gd")

    assert "func recover_without_grant(" in host
    assert "_on_embodied_settlement_result_received" in host
    assert "_on_embodied_cancel_directive_received" in host
    assert "_on_embodied_resync_projection_received" in host
    assert "_on_world_result_received" in host
    assert "recover_balance" in host
    assert "release_stance_lease" in host
    assert "clear_right_hand_reach" in host
    assert "func clear_right_hand_reach() -> void:" in replica


def test_door_host_enforces_local_stance_and_approach_obstacle_guards_without_a_second_motor_owner() -> None:
    host = _read("scripts/interaction/ArchiveDoorEmbodiedActionHost.gd")
    bridge = _read("scripts/interaction/ArchiveDoorEmbodiedAffordanceBridge.gd")

    assert "stance_occupied" in host
    assert "approach_obstructed" in host
    assert "func reserve_stance_lease(" in bridge
    assert "func release_stance_lease(" in bridge
    assert "func is_approach_obstructed(" in bridge
    assert "move_and_slide(" not in host
    assert "global_transform =" not in host


def test_character_reach_path_prefers_skeleton_ik_and_falls_back_closed_when_unavailable() -> None:
    replica = _read("scripts/character/CharacterReplica.gd")
    role_skin = _read("scripts/character/KnightRoleSkin.gd")

    assert "func begin_right_hand_reach(" in replica
    assert "func clear_right_hand_reach() -> void:" in replica
    assert 'ClassDB.class_exists("SkeletonIK3D")' in role_skin
    assert "SkeletonIK3D" in role_skin
    assert "skeleton_modifier_fallback" in role_skin
    assert "ik_chain_unavailable" in role_skin
