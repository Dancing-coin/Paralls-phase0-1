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
