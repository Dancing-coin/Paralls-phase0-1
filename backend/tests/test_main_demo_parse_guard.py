from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_main_demo_camera_local_is_explicitly_typed_for_godot_parser() -> None:
    source = (ROOT / "scripts" / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")
    assert "var camera: Variant = player.get_camera()" in source
