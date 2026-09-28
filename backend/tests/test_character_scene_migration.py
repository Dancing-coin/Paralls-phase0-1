from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_streetdemo_uses_character_actor_scene_and_no_replica_instance():
    scene=(ROOT/'scenes/phase0/StreetCombatDemo.tscn').read_text(encoding='utf-8')
    assert 'res://scenes/phase0/CharacterActor.tscn' in scene
    assert scene.count('instance=ExtResource("actor")') == 3
    assert 'CharacterReplica.tscn' not in scene

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
    assert 'concrete_behavior_callers' in source
