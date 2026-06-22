from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_observatory_input_controller_binds_required_developer_controls() -> None:
    source = (ROOT / "scripts" / "ui" / "ObservatoryInputController.gd").read_text(encoding="utf-8")

    assert "KEY_F6" in source
    assert "KEY_F7" in source
    assert "KEY_F8" in source
    assert "KEY_TAB" in source
    assert "KEY_SPACE" in source
    assert "KEY_ESCAPE" in source
    assert "click-to-lock" not in source.lower()
    assert "select_actor_by_click" in source
