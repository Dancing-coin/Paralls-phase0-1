from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_streetdemo_uses_character_actor_scene_and_no_replica_instance():
    scene=(ROOT/'scenes/phase0/StreetCombatDemo.tscn').read_text(encoding='utf-8')
    assert 'res://scenes/phase0/CharacterActor.tscn' in scene
    assert scene.count('instance=ExtResource("actor")') == 3
    assert 'CharacterReplica.tscn' not in scene


def test_character_base_and_validation_player_scenes_mount_actor_host():
    for name in ("CharacterBase.tscn", "ValidationCharacterReplica.tscn", "ValidationPlayerShell.tscn"):
        scene = (ROOT / "scenes" / "phase0" / name).read_text(encoding="utf-8")
        assert "res://scenes/phase0/CharacterActor.tscn" in scene or "res://scripts/character/CharacterActor.gd" in scene
        assert "res://scenes/phase0/CharacterReplica.tscn" not in scene


def test_player_callers_use_actor_capability_ingress_without_replica_lookup():
    bridge = (ROOT / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(encoding="utf-8")
    shell = (ROOT / "scripts" / "player" / "PlayerShell.gd").read_text(encoding="utf-8")
    main_demo = (ROOT / "scripts" / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    assert "get_character_actor" in bridge
    assert "get_character_replica" not in bridge
    assert "get_character_actor" in shell
    assert 'get_node_or_null("CharacterReplica")' not in shell
    assert 'get_node_or_null("PlayerCharacter/CharacterReplica")' not in main_demo
    assert "set_driver_mode" not in main_demo

def test_character_actor_scene_preserves_runtime_tree_and_motor():
    scene=(ROOT/'scenes/phase0/CharacterActor.tscn').read_text(encoding='utf-8')
    assert 'res://scripts/character/CharacterActor.gd' in scene
    assert '[node name="CharacterMotor" type="Node" parent="."]' in scene
    assert 'StreetCharacterSkin' not in scene

def test_retirement_probe_reports_streetdemo_replica_zero():
    probe=ROOT/'scripts/verification/CharacterReplicaRetirementProbe.gd'
    assert probe.exists()
    source=probe.read_text(encoding='utf-8')
    assert 'CharacterReplica.tscn' in source
    assert 'active_scene_instances' in source
    assert 'runtime_replica_lookups' in source
    assert 'compatibility_call_count' in source
