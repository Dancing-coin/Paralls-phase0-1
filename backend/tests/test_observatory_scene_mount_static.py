from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_observatory_root_scene_exists_and_is_mounted_in_main_demo() -> None:
    root_scene = (ROOT / "scenes" / "phase0" / "ObservatoryRoot.tscn")
    main_demo = (ROOT / "scenes" / "phase0" / "MainDemo.tscn").read_text(encoding="utf-8")

    assert root_scene.exists()
    assert 'path="res://scenes/phase0/ObservatoryRoot.tscn"' in main_demo
    assert 'node name="ObservatoryRoot" parent="."' in main_demo


def test_observatory_root_wires_state_and_all_key_surfaces() -> None:
    scene_source = (ROOT / "scenes" / "phase0" / "ObservatoryRoot.tscn").read_text(encoding="utf-8")

    assert 'node name="CharacterDirectorState"' in scene_source
    assert 'node name="ActorStateTags"' in scene_source
    assert 'node name="RelationshipOverlay"' in scene_source
    assert 'node name="CharacterObserverPanel"' in scene_source
    assert 'node name="DirectorMonitorPanel"' in scene_source
    assert 'node name="SimingDirectorBoard"' in scene_source
    assert 'node name="ScriptTimelinePanel"' in scene_source
    assert 'node name="DialogueSceneLedger"' in scene_source
    assert 'node name="WorldOutcomeTrace"' in scene_source
    assert 'node name="ObservatoryInputController"' in scene_source
