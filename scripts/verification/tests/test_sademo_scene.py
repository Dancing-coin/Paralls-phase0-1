from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCENE = ROOT / "scenes" / "phase0" / "sademo.tscn"
SCRIPT = ROOT / "scripts" / "street_combat" / "sademo.gd"
ACTOR_SCRIPT = ROOT / "scripts" / "character" / "CharacterActor.gd"


def test_sademo_is_a_single_character_actor_female_t_scene() -> None:
    assert SCENE.exists()
    assert SCRIPT.exists()
    scene = SCENE.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'name="sademo"' in scene
    assert 'res://scenes/phase0/CharacterActor.tscn' in scene
    assert 'res://assets/active/female_t_external/female_t_external.glb' in scene
    assert 'package_id = "female_t_external"' in scene
    assert 'actor_id = "char_c"' in scene
    assert 'driver_mode = 1' in scene
    assert 'AgentCharacterJK' not in scene
    assert 'AgentCharacterT' not in scene
    assert 'CombatCoordinator' not in scene
    assert scene.count('instance=ExtResource("actor")') == 1

    for state in ("idle", "walk", "run", "jump", "boxing", "sword_attack"):
        assert state in script


def test_sademo_routes_body_control_through_character_actor() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert "begin_embodied_control_frame" in script
    assert "move_and_slide" not in script
    assert "actor.velocity.x =" not in script
    assert "actor.velocity.y =" not in script
    assert "actor.velocity.z =" not in script
    assert "play_locomotion_state" not in script
    assert "play_action_state" not in script


def test_character_actor_exposes_external_demo_motion_tuning() -> None:
    actor = ACTOR_SCRIPT.read_text(encoding="utf-8")
    for export_name in (
        "player_acceleration",
        "player_fall_gravity",
        "player_jump_impulse",
        "player_turn_speed",
    ):
        assert export_name in actor
    assert '"acceleration"' in actor
    assert '"fall_gravity"' in actor
    assert '"jump_impulse"' in actor
