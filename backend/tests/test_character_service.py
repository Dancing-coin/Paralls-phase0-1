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


def test_character_service_routes_dialogue_generation_through_character_model_gateway() -> None:
    class _Gateway:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def run_task(
            self,
            *,
            task_kind: str,
            context: dict[str, object],
            route_override: str | None = None,
        ) -> dict[str, object]:
            self.calls.append(
                {
                    "task_kind": task_kind,
                    "context": context,
                    "route_override": route_override,
                }
            )
            return {
                "content": "The letter has not moved.",
                "tone": "neutral",
            }

    gateway = _Gateway()
    service = CharacterService(dialogue_gateway=gateway)
    event = DialogueSubmit(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="dialogue_submit",
        producer_ts=7,
        target_actor_id="char_a",
        content="Did the letter move?",
    )

    result = service.handle_dialogue(event)

    assert gateway.calls
    assert gateway.calls[0]["task_kind"] == "dialogue_generation"
    assert gateway.calls[0]["context"]["actor_id"] == "char_a"
    assert gateway.calls[0]["context"]["event"]["content"] == "Did the letter move?"
    assert result.content == "The letter has not moved."
    assert result.tone == "neutral"


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
