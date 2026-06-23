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
    assert "var frozen_frame := {}" in source
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
    assert "_capture_frozen_frame" in source
    assert "get_dialogue_pair_entries" in source
    assert "resolve_target_node" in source
    assert "speaker_perceived_summary" in source
    assert "listener_perceived_summary" in source
    assert "speaker_interpreted_summary" in source
    assert "listener_interpreted_summary" in source
    assert "speaker_said" in source
    assert "listener_said" in source
    assert "speaker_alignment_label" in source
    assert "listener_alignment_label" in source
    assert "func get_selected_actor_label() -> String:" in source
    assert "func get_latest_bottom_strip_entries() -> Array[Dictionary]:" in source
    assert "func get_latest_script_beat_summaries(" in source
    assert "func get_latest_siming_summaries(" in source


def test_character_director_state_emits_signal_when_tab_cycles_actor_selection() -> None:
    source = (ROOT / "scripts" / "ui" / "CharacterDirectorState.gd").read_text(encoding="utf-8")

    assert "func cycle_actor(step: int) -> void:" in source
    assert "const DEFAULT_OBSERVATORY_ACTOR_IDS" in source
    assert "_get_cycle_actor_ids()" in source
    assert "selected_actor_id = actor_ids[(current_index + step + actor_ids.size()) % actor_ids.size()]" in source
    assert 'emit_signal("observatory_state_changed")' in source
