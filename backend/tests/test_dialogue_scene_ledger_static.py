from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_dialogue_scene_ledger_supports_pair_review_and_mismatch_cues() -> None:
    source = (ROOT / "scripts" / "ui" / "DialogueSceneLedger.gd").read_text(encoding="utf-8")

    assert "selected_pair_key" in source
    assert "pair_key" in source
    assert "perceived" in source
    assert "interpreted" in source
    assert "said" in source
    assert "mismatch" in source
    assert "alignment" in source
    assert "_build_pair_rows" in source
    assert "get_dialogue_pair_entries" in source
    assert "speaker_perceived_summary" in source
    assert "listener_perceived_summary" in source
    assert "speaker_interpreted_summary" in source
    assert "listener_interpreted_summary" in source
    assert "speaker_said" in source
    assert "listener_said" in source
    assert "speaker_alignment_label" in source
    assert "listener_alignment_label" in source
    assert "司命压力上下文" in source
    assert "_resolve_siming_pressure_context" in source
    assert '_resolve_siming_pressure_context(selected_row)' in source
    assert 'row.get("siming_pressure_context"' in source
    assert 'row.get("siming_context"' in source
    assert 'row.get("siming_summary"' in source
    assert "还没有对话对账记录。先面对角色说一句话，再回来查看。" in source
    assert 'state.get("observatory_enabled")' in source
    assert 'state.get("script_mode")' in source
