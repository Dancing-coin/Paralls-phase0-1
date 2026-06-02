from app.services.character_service import CharacterService
from app.models.player_input import DialogueSubmit, FocusTargetChange


def test_character_service_returns_dialogue_response() -> None:
    service = CharacterService()
    event = DialogueSubmit(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="dialogue_submit",
        producer_ts=1,
        target_actor_id="char_a",
        content="Where is the letter?",
    )
    result = service.handle_dialogue(event)
    assert result.output_type == "dialogue_response"
    assert result.target_actor_id == "char_c"
    assert result.tts_required is True
    assert result.tone == "alert"


def test_character_service_summarizes_focus_target_change() -> None:
    service = CharacterService()
    event = FocusTargetChange(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="focus_target_change",
        producer_ts=2,
        target_actor_id="char_a",
    )
    result = service.handle_focus_target_change(event)
    assert result["actor_id"] == "char_c"
    assert result["target_actor_id"] == "char_a"
    assert result["summary"] == "char_c focuses on actor char_a"
