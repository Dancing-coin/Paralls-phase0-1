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
