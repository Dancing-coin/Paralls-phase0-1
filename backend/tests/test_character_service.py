from app.services.character_service import CharacterService
from app.models.dialogue_audio import DialogueAudio
from app.models.player_input import DialogueSubmit, FocusTargetChange


def test_character_service_returns_dialogue_response() -> None:
    class _Gateway:
        def run_task(
            self,
            *,
            task_kind: str,
            context: dict[str, object],
            route_override: str | None = None,
        ) -> dict[str, object]:
            return {
                "content": "I saw something move near the desk.",
                "tone": "alert",
            }

    service = CharacterService(dialogue_gateway=_Gateway())
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
    assert result.audio is not None
    assert result.audio.mode == "stub"


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


def test_tts_fallback_preserves_completed_dialogue_text_without_a_second_generation_call() -> None:
    class _Gateway:
        def __init__(self) -> None:
            self.calls = 0

        def run_task(self, **_kwargs: object) -> dict[str, object]:
            self.calls += 1
            return {"content": "The message remains unchanged.", "tone": "neutral"}

    class _FallbackTTS:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def synthesize(self, actor_id: str, content: str) -> DialogueAudio:
            self.calls.append((actor_id, content))
            return DialogueAudio(
                mode="stub",
                status="fallback",
                provider="stub",
                voice_id="legacy-voice",
                fallback_reason="provider_unavailable:char_a",
            )

    gateway = _Gateway()
    tts = _FallbackTTS()
    service = CharacterService(dialogue_gateway=gateway, tts_service=tts)
    event = DialogueSubmit(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="dialogue_submit",
        producer_ts=9,
        target_actor_id="char_a",
        content="Please respond.",
    )

    result = service.handle_dialogue(event)

    assert gateway.calls == 1
    assert tts.calls == [("char_a", "The message remains unchanged.")]
    assert result.content == "The message remains unchanged."
    assert result.audio is not None
    assert result.audio.status == "fallback"


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


def test_agent_initiated_utterance_preserves_speaking_actor() -> None:
    class _Gateway:
        def run_task(
            self,
            *,
            task_kind: str,
            context: dict[str, object],
            route_override: str | None = None,
        ) -> dict[str, object]:
            return {
                "content": "approach greeting",
                "tone": "warm",
            }

    service = CharacterService(dialogue_gateway=_Gateway())
    event = DialogueSubmit(
        player_id="character_agent",
        room_id="room_demo",
        actor_id="char_a",
        intent_type="dialogue_submit",
        producer_ts=1,
        target_actor_id="char_c",
        content="approach greeting",
    )

    result = service.handle_dialogue(event)

    assert result.actor_id == "char_a"
    assert result.target_actor_id == "char_c"
