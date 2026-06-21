from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_character_director_state_caches_all_observatory_families() -> None:
    source = (ROOT / "scripts" / "ui" / "CharacterDirectorState.gd").read_text(encoding="utf-8")

    assert "var latest_actor_states := {}" in source
    assert "var recent_actor_events := {}" in source
    assert "var latest_siming_state := {}" in source
    assert "var recent_siming_events: Array[Dictionary] = []" in source
    assert "var recent_world_outcomes: Array[Dictionary] = []" in source
    assert "var recent_script_beats: Array[Dictionary] = []" in source
    assert "var freeze_mode := false" in source
    assert 'character_agent_debug_snapshot_received.connect(_on_character_agent_debug_snapshot_received)' in source
    assert 'character_agent_debug_event_received.connect(_on_character_agent_debug_event_received)' in source
    assert 'siming_debug_snapshot_received.connect(_on_siming_debug_snapshot_received)' in source
    assert 'siming_debug_event_received.connect(_on_siming_debug_event_received)' in source
    assert 'world_outcome_trace_received.connect(_on_world_outcome_trace_received)' in source
    assert 'script_beat_event_received.connect(_on_script_beat_event_received)' in source


def test_character_director_state_exposes_master_mode_and_freeze_controls() -> None:
    source = (ROOT / "scripts" / "ui" / "CharacterDirectorState.gd").read_text(encoding="utf-8")

    assert "var observatory_enabled := false" in source
    assert "var director_mode := false" in source
    assert "var script_mode := false" in source
    assert "func set_observatory_enabled(enabled: bool) -> void:" in source
    assert "func set_director_mode(enabled: bool) -> void:" in source
    assert "func set_script_mode(enabled: bool) -> void:" in source
    assert "func set_freeze_mode(enabled: bool) -> void:" in source
