from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_character_observer_panel_shows_single_actor_deep_fields() -> None:
    source = (ROOT / "scripts" / "ui" / "CharacterObserverPanel.gd").read_text(encoding="utf-8")

    assert "看到了什么" in source
    assert "怎么理解" in source
    assert "准备做什么" in source
    assert "世界 / 司命反馈" in source
    assert "label.position = Vector2(" in source
    assert "label.size = Vector2(" in source
    assert "他刚刚看见/听见：" not in source
    assert "他脑子里记着：" not in source
