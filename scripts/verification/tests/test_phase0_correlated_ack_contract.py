from pathlib import Path


SCRIPTS_ROOT = Path(__file__).resolve().parents[2]


def test_player_intent_mapper_generates_collision_safe_request_ids() -> None:
    source = (SCRIPTS_ROOT / "player" / "PlayerIntentMapper.gd").read_text(encoding="utf-8")
    player_input_source = source.split("func emit_visual_fact_event", 1)[0]

    assert "var request_sequence := 0" in player_input_source
    assert "request_sequence += 1" in source
    assert '"player_input:%s:%s:%s:%s"' in source
    assert "[player_actor_id, intent_type, producer_ts, request_sequence]" in source
    assert player_input_source.count('"request_id": request_id') == 4
    assert player_input_source.count('"producer_ts": producer_ts') == 4
    assert "\"producer_ts\": Time.get_ticks_msec()" not in player_input_source
