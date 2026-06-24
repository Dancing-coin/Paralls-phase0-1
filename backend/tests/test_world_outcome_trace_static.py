from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_world_outcome_trace_becomes_thin_bottom_strip_with_latest_three_entries() -> None:
    source = (ROOT / "scripts" / "ui" / "WorldOutcomeTrace.gd").read_text(encoding="utf-8")

    assert "最近 3 条" in source
    assert "世界" in source
    assert "司命" in source
    assert "节拍" in source
    assert "get_latest_bottom_strip_entries" in source
    assert 'for outcome in state.recent_world_outcomes' not in source


def test_world_outcome_trace_preserves_siming_label_and_summary_text_without_boolean_coercion() -> None:
    source = (ROOT / "scripts" / "ui" / "WorldOutcomeTrace.gd").read_text(encoding="utf-8")
    format_block = source.split("func _format_bottom_strip_row(row: Dictionary) -> String:", 1)[1]

    assert '[司命] %s' in format_block
    assert "暂无摘要" in format_block
    assert 'row.get("type", "") or ""' not in format_block
    assert 'row.get("summary", "") or "暂无摘要"' not in format_block
