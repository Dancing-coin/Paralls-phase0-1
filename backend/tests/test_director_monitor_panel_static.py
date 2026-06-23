from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_director_monitor_panel_includes_cast_scene_world_and_siming_boards() -> None:
    source = (ROOT / "scripts" / "ui" / "DirectorMonitorPanel.gd").read_text(encoding="utf-8")

    assert "演员总览" in source
    assert "现场状态" in source
    assert "世界结算 / 约束结果" in source
    assert "司命导演席" in source
    assert "_build_cast_board" in source
    assert "_build_scene_state_board" in source
    assert "_build_world_board" in source
    assert 'state.call("get_visible_actor_states")' in source or "get_visible_actor_states" in source
    assert 'state.call("get_recent_world_outcomes")' in source or "get_recent_world_outcomes" in source
    assert 'payload.get("state_label"' in source
    assert 'payload.get("latest_outcome_summary"' in source
    assert 'payload.get("latest_siming_summary"' in source
    assert 'beat.get("dramatic_summary"' in source
    assert 'outcome.get("constraint_summary"' in source
    assert 'outcome.get("world_change_summary"' in source
    assert "siming_board._build_director_rows(" in source
    assert '" | ".join(siming_lines)' in source
    assert "剧本回放已开" in source
    assert "剧本回放未开" in source
    assert "当前已冻结" in source
    assert "当前是实时刷新" in source
    assert "当前观察角色：" in source
    assert 'state.get("observatory_enabled")' in source
    assert 'state.get("director_mode")' in source
