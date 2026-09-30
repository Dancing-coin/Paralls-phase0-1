from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_phase0_player_locomotion_probe_releases_transient_actor_hold_before_measuring():
    source = (ROOT / "scripts" / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    probe = source.split("func _run_locomotion_probe()", 1)[1].split("func _run_npc_patrol_root_motion_probe()", 1)[0]
    assert 'player_actor.set("hold_timer", 0.0)' in probe
    assert 'player_actor.set("action_override_timer", 0.0)' in probe


def test_forced_focus_target_survives_normal_focus_resampling_until_probe_releases_it():
    source = (ROOT / "scripts" / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    force_focus = source.split("func _force_focus_target", 1)[1].split("func _orient_player_toward", 1)[0]
    assert "focus_override_active = true" in force_focus


def test_actor_owned_player_pose_feedback_cannot_replace_locomotion_intent():
    source = (ROOT / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(encoding="utf-8")
    after_move = source.split("func after_player_shell_move", 1)[1].split("func _sync_character_c_from_player", 1)[0]
    assert "if player_root_motion_enabled:\n\t\treturn" in after_move


def test_player_shell_publishes_motor_post_collision_motion_instead_of_status_metadata():
    source = (ROOT / "scripts" / "player" / "PlayerShell.gd").read_text(encoding="utf-8")
    physics_process = source.split("func _physics_process", 1)[1].split("func set_jump_variant_profile", 1)[0]
    assert 'actor.get_node_or_null("CharacterMotor")' in physics_process
    assert "_publish_motion_state(motor.get_last_motion_state())" in physics_process
    assert "_publish_motion_state(actor.get_locomotion_status())" not in physics_process
