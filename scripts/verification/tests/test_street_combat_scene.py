from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCENE = ROOT / "scenes" / "phase0" / "StreetCombatDemo.tscn"


def test_default_scene_uses_staged_street_and_only_user_characters() -> None:
    project = (ROOT / "project.godot").read_text(encoding="utf-8")
    scene = SCENE.read_text(encoding="utf-8")
    assert 'run/main_scene="res://scenes/phase0/StreetCombatDemo.tscn"' in project
    for name in ("environment.glb", "collision.glb", "navigation.glb"):
        assert f"res://assets/active/citystreets_209/0.3.0/{name}" in scene
    for name in ("female_jk_external", "female_t_external", "female_bandage_external"):
        assert f"res://assets/active/{name}/{name}.glb" in scene
    assert scene.count('instance=ExtResource("replica")') == 3
    assert "ProceduralLowPolyCharacter" not in scene
    assert "paralls-art-assets/characters" not in scene
    assert scene.count("scale = Vector3(1.4, 1.4, 1.4)") == 3
    assert 'name="PlayerCharacter"' in scene
    assert 'name="AgentCharacterJK"' in scene
    assert 'name="AgentCharacterT"' in scene


def test_street_hud_exposes_action_gameplay_surfaces() -> None:
    hud = (ROOT / "scenes" / "phase0" / "StreetCombatHUD.tscn").read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "street_combat" / "StreetCombatHUD.gd").read_text(encoding="utf-8")
    for node_name in ("ScoreStrip", "MiniMap", "PlayerCard", "HealthFill", "StaminaFill", "SkillBar", "TargetCard", "CombatFeed"):
        assert f'name="{node_name}"' in hud
    for label in ("体力", "生命", "目标", "战斗记录"):
        assert label in hud
    assert "短拳" not in hud
    for node_path in (
        "$ScoreStrip/Status",
        "$CombatFeed/Feed",
        "$TargetCard/Target",
        "$TargetCard/Distance",
        "$PlayerCard/Action",
        "$PlayerCard/HealthTrack/HealthFill",
        "$PlayerCard/HealthValue",
        "$Agents",
    ):
        assert node_path in script
    assert "get_current_clip_name" in script
    assert "global_position.distance_to" in script


def test_street_combat_presents_third_person_composition() -> None:
    scene = SCENE.read_text(encoding="utf-8")
    hud = (ROOT / "scenes" / "phase0" / "StreetCombatHUD.tscn").read_text(encoding="utf-8")
    controller = (ROOT / "scripts" / "street_combat" / "StreetCombatDemo.gd").read_text(encoding="utf-8")
    skin = (ROOT / "scripts" / "street_combat" / "StreetCharacterSkin.gd").read_text(encoding="utf-8")
    replica = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(encoding="utf-8")
    assert 'position = Vector3(2.05, 0.2, -7.0)' in scene
    assert 'position = Vector3(-2.05, 0.2, -7.0)' in scene
    assert 'position = Vector3(0, 1.95, -13.15)' in scene
    assert 'fov = 48.0' in scene
    assert 'var desired_camera := player.global_position + Vector3(0.0, 1.95, -3.15)' in controller
    assert 'camera.look_at(player.global_position + Vector3(0.0, 1.28, 3.4), Vector3.UP)' in controller
    assert 'set_look_target(player.global_position + Vector3(0.0, 1.0, 0.0))' in controller
    assert 'set_guard_stance(0.34)' in controller
    assert 'ensure_guard_stance(0.34)' in controller
    assert 'phase0_jump' in controller
    assert 'camera_orbiting' in controller
    assert 'var camera_right := Vector3(-cos(camera_yaw), 0.0, -sin(camera_yaw))' in controller
    assert 'play_turn_transition' not in controller
    assert 'camera_forward * 2.0' in controller
    assert 'set_look_target(look_target)' in replica
    assert 'func get_numeric_setting(property_name: StringName, fallback: float)' in replica
    assert '&"facing_turn_speed"' in replica
    assert '"turn_left"' not in skin
    assert '"turn_right"' not in skin
    assert 'action:melee.sword_slash' in controller
    assert 'phase0_sword_attack' in (ROOT / "project.godot").read_text(encoding="utf-8")
    assert 'text = "Q   剑击"' in hud
    assert 'text = "E   短拳"' not in hud
    assert 'text = "WASD 移动' in hud
    assert "↑↓←→" not in hud
    assert 'RMB 视角' in hud
    assert scene.count('rotation = Vector3(0, 3.141593, 0)') == 3
    assert 'name="TargetRing"' in scene
    assert 'name="Ring"' in hud
    assert 'minimap_shader' in hud
    assert 'name="StatusBadge"' in hud
    assert 'KEY_UP' not in controller
    assert 'KEY_DOWN' not in controller
    assert 'KEY_LEFT' not in controller
    assert 'KEY_RIGHT' not in controller
    assert 'Input.get_vector("phase0_move_left", "phase0_move_right", "phase0_move_forward", "phase0_move_backward")' in controller
    assert "const IDLE_PLAYBACK_SPEED := 0.45" in skin
    assert '"idle")), IDLE_PLAYBACK_SPEED' in skin
    assert "_stabilize_idle_root_height" in skin
    assert "stable_value.y = locked_height" in skin
    assert scene.count("sway_amount = 0.0") == 3
