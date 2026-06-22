from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_director_monitor_panel_includes_cast_scene_world_and_siming_boards() -> None:
    source = (ROOT / "scripts" / "ui" / "DirectorMonitorPanel.gd").read_text(encoding="utf-8")

    assert "Cast Board" in source
    assert "Scene State" in source
    assert "World / Constraint Status" in source
    assert "SimingDirectorBoard" in source
    assert "_build_cast_board" in source
    assert "_build_scene_state_board" in source
    assert "_build_world_board" in source
    assert "latest_actor_states" in source
    assert "recent_world_outcomes" in source
