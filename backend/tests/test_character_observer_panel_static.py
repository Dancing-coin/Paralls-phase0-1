from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_character_observer_panel_shows_single_actor_deep_fields() -> None:
    source = (ROOT / "scripts" / "ui" / "CharacterObserverPanel.gd").read_text(encoding="utf-8")

    assert 'payload.get("perception_summary"' in source
    assert 'payload.get("state_label"' in source
    assert 'payload.get("memory_summary"' in source
    assert 'payload.get("interpretation_summary"' in source
    assert 'payload.get("decision_summary"' in source
    assert 'payload.get("execution_summary"' in source
    assert 'payload.get("latest_outcome_summary"' in source
    assert 'payload.get("latest_siming_summary"' in source
