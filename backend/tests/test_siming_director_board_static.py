from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_siming_director_board_shows_director_seat_fields() -> None:
    source = (ROOT / "scripts" / "ui" / "SimingDirectorBoard.gd").read_text(encoding="utf-8")

    assert 'payload.get("fairness_summary"' in source
    assert 'payload.get("intervention_candidate"' in source
    assert 'payload.get("intervention_decision"' in source
    assert 'payload.get("selected_path"' in source
    assert 'payload.get("intervention_band"' in source
    assert 'payload.get("target_ref"' in source
    assert 'payload.get("reason_summary"' in source
    assert 'payload.get("downstream_status"' in source
