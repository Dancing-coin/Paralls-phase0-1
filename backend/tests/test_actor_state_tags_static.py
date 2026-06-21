from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_actor_state_tags_surface_exposes_required_fields() -> None:
    source = (ROOT / "scripts" / "ui" / "ActorStateTags.gd").read_text(encoding="utf-8")

    assert "actor name" not in source.lower()  # avoid comment-only stubs
    assert 'payload.get("actor_id"' in source
    assert 'payload.get("current_intent"' in source
    assert 'payload.get("focus_target"' in source
    assert 'payload.get("state_label"' in source
    assert 'payload.get("why_now_summary"' in source
    assert 'payload.get("latest_siming_summary"' in source

