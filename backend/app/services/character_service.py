from collections.abc import Callable, Mapping

from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.models.ai_output import DialogueResponse
from app.models.player_input import DialogueSubmit, FocusTargetChange
from app.services.dialogue_service import DialogueService
from app.services.tts_service import TTSService

DialogueContextProvider = Callable[[str], Mapping[str, object]]


class CharacterService:
    def __init__(
        self,
        *,
        dialogue_gateway: CharacterModelGateway | None = None,
        dialogue_service: DialogueService | None = None,
        dialogue_context_provider: DialogueContextProvider | None = None,
        tts_service: TTSService | None = None,
    ) -> None:
        self.dialogue = dialogue_service or DialogueService(
            gateway=dialogue_gateway,
            context_provider=dialogue_context_provider,
        )
        self.tts = tts_service or TTSService()

    def handle_dialogue(self, event: DialogueSubmit) -> DialogueResponse:
        if event.player_id == "character_agent":
            content, tone = self.dialogue.generate_utterance(
                event.actor_id,
                event.target_actor_id,
                event.content,
            )
            _audio = self.tts.synthesize(event.actor_id, content)
            return DialogueResponse(
                actor_id=event.actor_id,
                room_id=event.room_id,
                output_type="dialogue_response",
                causation_id=f"dialogue:{event.producer_ts}",
                producer_ts=event.producer_ts + 1,
                target_actor_id=event.target_actor_id,
                content=content,
                tone=tone,
                tts_required=True,
            )

        content, tone = self.dialogue.generate_reply(event.target_actor_id, event.content)
        _audio = self.tts.synthesize(event.target_actor_id, content)
        return DialogueResponse(
            actor_id=event.target_actor_id,
            room_id=event.room_id,
            output_type="dialogue_response",
            causation_id=f"dialogue:{event.producer_ts}",
            producer_ts=event.producer_ts + 1,
            target_actor_id=event.actor_id,
            content=content,
            tone=tone,
            tts_required=True,
        )

    def handle_focus_target_change(self, event: FocusTargetChange) -> dict[str, str]:
        return {
            "actor_id": event.actor_id,
            "target_actor_id": event.target_actor_id or "",
            "target_object_id": event.target_object_id or "",
            "summary": self._summarize_focus(event),
        }

    def _summarize_focus(self, event: FocusTargetChange) -> str:
        if event.target_actor_id:
            return f"{event.actor_id} focuses on actor {event.target_actor_id}"
        if event.target_object_id:
            return f"{event.actor_id} focuses on object {event.target_object_id}"
        return f"{event.actor_id} clears focus"
