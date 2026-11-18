from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_archive_door_probe_quiesces_unrelated_main_demo_perception() -> None:
    main_demo = (ROOT / "scripts" / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    assert 'OS.get_environment("PARALLS_OBJ_ARCHIVE_DOOR_SCENARIO")' in main_demo
    assert "suspend_near_object_visual_fact = true" in main_demo
    assert "suspend_spatial_access_fact = true" in main_demo
    assert "autotest_transport_quiescent = true" in main_demo
    assert "_set_autotest_actor_local_perception_enabled(false)" in main_demo
