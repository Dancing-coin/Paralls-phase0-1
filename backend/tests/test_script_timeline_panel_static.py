from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_script_timeline_panel_supports_beat_list_filter_and_detail() -> None:
    source = (ROOT / "scripts" / "ui" / "ScriptTimelinePanel.gd").read_text(encoding="utf-8")

    assert "beat list" not in source.lower()
    assert "filter_actor_id" in source
    assert "filter_participant" in source
    assert "expanded_beat_id" in source
    assert 'beat.get("correlation_id"' in source
    assert 'beat.get("participants"' in source
    assert "_build_filtered_beats" in source
    assert "_build_beat_summary_line" in source
    assert "_build_expanded_payload_lines" in source
    assert "sort_custom" in source or ".sort()" in source
