from pathlib import Path
import os
import subprocess


ROOT = Path(__file__).resolve().parents[3]
SCENE = ROOT / "scenes" / "phase0" / "StreetCombatActorDemo.tscn"
SCRIPT = ROOT / "scripts" / "street_combat" / "StreetCombatActorDemo.gd"
COORDINATOR = ROOT / "scripts" / "street_combat" / "StreetCombatActorCoordinator.gd"
HUD_SCRIPT = ROOT / "scripts" / "street_combat" / "StreetCombatActorHUD.gd"
HUD_SCENE = ROOT / "scenes" / "phase0" / "StreetCombatActorHUD.tscn"
ORIGINAL_SCENE = ROOT / "scenes" / "phase0" / "StreetCombatDemo.tscn"
ORIGINAL_SCRIPT = ROOT / "scripts" / "street_combat" / "StreetCombatDemo.gd"
GODOT = Path(r"D:\godot\Godot_v4.6.3-stable_win64.exe")


def test_actor_demo_is_an_independent_three_character_copy() -> None:
    scene = SCENE.read_text(encoding="utf-8")
    assert 'name="StreetCombatActorDemo"' in scene
    assert 'path="res://scripts/street_combat/StreetCombatActorDemo.gd"' in scene
    assert 'path="res://scripts/street_combat/StreetCombatActorCoordinator.gd"' in scene
    assert 'path="res://scenes/phase0/StreetCombatActorHUD.tscn"' in scene
    assert scene.count('instance=ExtResource("actor")') == 3
    for actor_name in ("PlayerCharacter", "AgentCharacterJK", "AgentCharacterT"):
        assert f'name="{actor_name}" parent="." instance=ExtResource("actor")' in scene


def test_actor_demo_routes_all_player_motion_through_character_actor() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    controller = script.split("func _probe_combat", 1)[0]
    assert "begin_embodied_control_frame" in controller
    assert "actor.move_and_slide" not in controller
    assert "player.move_and_slide" not in controller
    assert "active_actor.velocity" not in controller
    assert "clear_embodied_control_frame" in controller
    assert "controlled_actor_index" in controller
    assert "KEY_TAB" in controller


def test_actor_demo_keeps_original_street_combat_files_untouched() -> None:
    original_scene = ORIGINAL_SCENE.read_text(encoding="utf-8")
    original_script = ORIGINAL_SCRIPT.read_text(encoding="utf-8")
    assert 'name="StreetCombatDemo"' in original_scene
    assert 'path="res://scripts/street_combat/StreetCombatDemo.gd"' in original_scene
    assert "func _probe_combat" in original_script


def test_actor_demo_hud_and_coordinator_follow_active_player() -> None:
    coordinator = COORDINATOR.read_text(encoding="utf-8")
    hud = HUD_SCRIPT.read_text(encoding="utf-8")
    assert "player_actor_id" in coordinator
    assert "set_player_actor_id" in coordinator
    assert 'actor_id == player_actor_id' in coordinator
    assert 'request_attack(active_actor.actor_id' in SCRIPT.read_text(encoding="utf-8")
    assert "player_actor_id" in hud
    assert "ACTOR_NAMES" in hud
    assert HUD_SCENE.exists()


def test_agent_action_does_not_invent_a_target_when_target_ref_is_missing() -> None:
    coordinator = COORDINATOR.read_text(encoding="utf-8")
    execution_slice = coordinator.split("func _on_agent_execution", 1)[1].split(
        "func _append_event", 1
    )[0]
    assert 'str(payload.get("target_ref", "")).trim_prefix("character:")' in execution_slice
    assert 'target missing or invalid' in execution_slice
    assert "target_id = player_actor_id" not in execution_slice


def test_actor_demo_uses_sademo_movement_and_camera_policy() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert "Vector3(input.x, 0.0, input.y)" in script
    assert "Vector3(4.8, 3.1, 6.6)" in script
    assert "jump_in_flight" in script
    assert "camera_yaw" not in script
    assert '"two_foot"' in script


def test_actor_demo_switches_real_character_actor_player_shells() -> None:
    env = os.environ.copy()
    env["PARALLS_STREET_PROBE"] = "7"
    result = subprocess.run(
        [
            str(GODOT),
            "--headless",
            "--path",
            str(ROOT),
            "--scene",
            "res://scenes/phase0/StreetCombatActorDemo.tscn",
            "--quit-after",
            "240",
            "--render-thread",
            "safe",
            "--rendering-method",
            "gl_compatibility",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=45,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "street_actor_switch_probe:initial=true:char_a=true:char_b=true:round_trip=true:walk_clip=true" in output, output
