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
