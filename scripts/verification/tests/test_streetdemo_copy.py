from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCENE = ROOT / "scenes" / "phase0" / "streetdemo.tscn"
SCRIPT = ROOT / "scripts" / "street_combat" / "streetdemo.gd"


def test_streetdemo_is_single_model2_external_controller_copy() -> None:
    assert SCENE.exists()
    assert SCRIPT.exists()
    scene = SCENE.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")
    assert 'node name="streetdemo"' in scene
    assert 'female_t_external/female_t_external.glb' in scene
    assert 'female_jk_external/female_jk_external.glb' not in scene
    assert 'StreetCombatCoordinator' not in scene
    assert scene.count('type="CharacterBody3D"') == 1
    assert 'package_id = "female_t_external"' in scene
    for state in ("idle", "walk", "run", "jump", "boxing", "sword_attack"):
        assert state in script
    assert 'get_source_animation_states().size()' in script
