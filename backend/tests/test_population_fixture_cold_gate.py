from types import SimpleNamespace

import pytest

from app import main
from app.models.player_input import DialogueSubmit
from app.population_continuity.vertical import _run_fixture_player_dialogue


def test_offline_dialogue_failure_preserves_rejection_and_closes_resources(monkeypatch):
    closed = []
    original_runtime = object()
    monkeypatch.setattr(main, "character_agent_runtime", original_runtime, raising=False)
    monkeypatch.setattr(main, "activation_policy", object(), raising=False)
    monkeypatch.setattr(main, "runtime", object(), raising=False)
    monkeypatch.setattr(main, "_publish_debug_event", lambda event: None)
    monkeypatch.setattr(main, "reset_runtime_state", lambda: None)
    monkeypatch.setattr(main, "close_runtime_resources", lambda: closed.append(True))
    monkeypatch.setattr(main, "_handle_envelope", lambda envelope: [{
        "message_type": "ack",
        "payload": {"accepted": False, "error_code": "activation_failed:ValueError"},
    }])
    dialogue = DialogueSubmit(
        player_id="player:fixture", room_id="room:fixture", scene_id="scene:fixture",
        zone_id="zone:fixture", actor_id="player_avatar", producer_ts=101,
        request_id="request:fixture:cold", target_actor_id="char_a", content="Hello",
    )

    with pytest.raises(RuntimeError, match="activation_failed:ValueError") as error:
        _run_fixture_player_dialogue(SimpleNamespace(), object(), dialogue)

    assert "request:fixture:cold" in str(error.value)
    assert main.character_agent_runtime is original_runtime
    assert closed == [True]
