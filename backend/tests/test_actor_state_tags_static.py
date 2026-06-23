from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_actor_state_tags_surface_exposes_required_fields() -> None:
    source = (ROOT / "scripts" / "ui" / "ActorStateTags.gd").read_text(encoding="utf-8")

    assert "actor name" not in source.lower()  # avoid comment-only stubs
    assert 'state.call("get_visible_actor_states")' in source or "get_visible_actor_states" in source
    assert "get_viewport().get_camera_3d()" in source
    assert "var actor_cards" in source
    assert "_refresh_card_positions" in source
    assert "当前意图" in source
    assert "当前目标" in source
    assert "原因摘要" in source
