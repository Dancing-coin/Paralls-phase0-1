from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _function_block(source: str, signature: str) -> str:
    start = source.index(signature)
    next_func = source.find("\nfunc ", start + len(signature))
    if next_func == -1:
        return source[start:]
    return source[start:next_func]


def test_character_director_state_caches_all_observatory_families() -> None:
    source = (ROOT / "scripts" / "ui" / "CharacterDirectorState.gd").read_text(encoding="utf-8")

    assert "var latest_actor_states := {}" in source
    assert "var recent_actor_events := {}" in source
    assert "var latest_siming_state := {}" in source
    assert "var recent_siming_events: Array[Dictionary] = []" in source
    assert "var recent_world_outcomes: Array[Dictionary] = []" in source
    assert "var recent_scheduling_rounds: Array[Dictionary] = []" in source
    assert "var recent_script_beats: Array[Dictionary] = []" in source
    assert "var freeze_mode := false" in source
    assert "var frozen_frame := {}" in source
    assert 'character_agent_debug_snapshot_received.connect(_on_character_agent_debug_snapshot_received)' in source
    assert 'character_agent_debug_event_received.connect(_on_character_agent_debug_event_received)' in source
    assert 'siming_debug_snapshot_received.connect(_on_siming_debug_snapshot_received)' in source
    assert 'siming_debug_event_received.connect(_on_siming_debug_event_received)' in source
    assert 'world_outcome_trace_received.connect(_on_world_outcome_trace_received)' in source
    assert 'scheduling_round_trace_received.connect(_on_scheduling_round_trace_received)' in source
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
    assert "func get_recent_siming_events() -> Array[Dictionary]:" in source
    assert "func get_recent_scheduling_rounds() -> Array[Dictionary]:" in source
    assert "func get_latest_siming_summaries(limit: int = 3) -> Array[String]:" in source
    assert "func get_selected_actor_latest_siming_summary() -> String:" in source
    assert "func get_selected_actor_recent_siming_reasons(limit: int = 2) -> Array[String]:" in source


def test_character_director_state_selected_actor_siming_helpers_stay_presentation_only() -> None:
    source = (ROOT / "scripts" / "ui" / "CharacterDirectorState.gd").read_text(encoding="utf-8")
    latest_summary_block = _function_block(source, "func get_selected_actor_latest_siming_summary() -> String:")
    recent_reasons_block = _function_block(source, "func get_selected_actor_recent_siming_reasons(limit: int = 2) -> Array[String]:")

    assert "latest_siming_summary" in latest_summary_block
    assert "get_selected_actor_state()" in latest_summary_block
    assert "get_recent_siming_events()" in recent_reasons_block
    assert "target_ref" in recent_reasons_block
    assert "selected_actor_id" in recent_reasons_block
    assert "reason_summary" in recent_reasons_block
    assert "summary" in recent_reasons_block
    assert "if rows.size() > limit:" in recent_reasons_block
    assert "rows.slice(rows.size() - limit, rows.size())" in recent_reasons_block
    assert "_string_array(" in recent_reasons_block


def test_character_director_state_bottom_strip_stays_single_merged_builder() -> None:
    source = (ROOT / "scripts" / "ui" / "CharacterDirectorState.gd").read_text(encoding="utf-8")
    bottom_strip_block = _function_block(source, "func get_latest_bottom_strip_entries() -> Array[Dictionary]:")

    assert "for outcome in get_recent_world_outcomes():" in bottom_strip_block
    assert "for round in get_recent_scheduling_rounds():" in bottom_strip_block
    assert "for event in get_recent_siming_events():" in bottom_strip_block
    assert "for beat in get_recent_script_beats():" in bottom_strip_block
    assert '"type": "世界"' in bottom_strip_block
    assert '"type": "调度"' in bottom_strip_block
    assert '"type": "司命"' in bottom_strip_block
    assert '"type": "节拍"' in bottom_strip_block
    assert "rows.sort_custom(" in bottom_strip_block
    assert 'a.get("producer_ts", 0)' in bottom_strip_block
    assert '> int(b.get("producer_ts", 0))' in bottom_strip_block
    assert "if rows.size() > 3:" in bottom_strip_block
    assert "rows.slice(0, 3)" in bottom_strip_block
    assert "_dictionary_array(" in bottom_strip_block


def test_character_director_state_emits_signal_when_tab_cycles_actor_selection() -> None:
    source = (ROOT / "scripts" / "ui" / "CharacterDirectorState.gd").read_text(encoding="utf-8")

    assert "func cycle_actor(step: int) -> void:" in source
    assert "const DEFAULT_OBSERVATORY_ACTOR_IDS" in source
    assert "_get_cycle_actor_ids()" in source
    assert "selected_actor_id = actor_ids[(current_index + step + actor_ids.size()) % actor_ids.size()]" in source
    assert 'emit_signal("observatory_state_changed")' in source
