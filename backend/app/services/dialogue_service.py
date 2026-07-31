from collections.abc import Callable, Mapping

from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.config import settings

DialogueContextProvider = Callable[[str], Mapping[str, object]]


class DialogueService:
    def __init__(
        self,
        gateway: CharacterModelGateway | None = None,
        context_provider: DialogueContextProvider | None = None,
    ) -> None:
        self._gateway = gateway or CharacterModelGateway()
        self._context_provider = context_provider

    def generate_reply(self, actor_id: str, content: str) -> tuple[str, str]:
        route_override = "local_only" if settings.dialogue_mode == "stub" else None
        output = self._gateway.run_task(
            task_kind="dialogue_generation",
            context=self._context(
                actor_id=actor_id,
                content=content,
                target_actor_id=actor_id,
                control_mode="dialogue_service",
                intent_type="dialogue_submit",
            ),
            route_override=route_override,
        )
        return (
            str(output.get("content", "") or ""),
            str(output.get("tone", "") or "neutral"),
        )

    def generate_utterance(self, actor_id: str, target_actor_id: str, content: str) -> tuple[str, str]:
        route_override = "local_only" if settings.dialogue_mode == "stub" else None
        output = self._gateway.run_task(
            task_kind="dialogue_generation",
            context=self._context(
                actor_id=actor_id,
                content=content,
                target_actor_id=target_actor_id,
                control_mode="agent_initiated_utterance",
                intent_type="agent_initiated_utterance",
            ),
            route_override=route_override,
        )
        return (
            str(output.get("content", "") or ""),
            str(output.get("tone", "") or "neutral"),
        )

    def stream_reply(self, actor_id: str, content: str, *, cancelled):
        yield from self._stream_dialogue(
            context=self._context(
                actor_id=actor_id,
                content=content,
                target_actor_id=actor_id,
                control_mode="dialogue_service",
                intent_type="dialogue_submit",
            ),
            cancelled=cancelled,
        )

    def stream_utterance(self, actor_id: str, target_actor_id: str, content: str, *, cancelled):
        yield from self._stream_dialogue(
            context=self._context(
                actor_id=actor_id,
                content=content,
                target_actor_id=target_actor_id,
                control_mode="agent_initiated_utterance",
                intent_type="agent_initiated_utterance",
            ),
            cancelled=cancelled,
        )

    def _stream_dialogue(self, *, context: dict[str, object], cancelled):
        route_override = "local_only" if settings.dialogue_mode == "stub" else None
        stream_task = getattr(self._gateway, "stream_dialogue_task", None)
        if callable(stream_task):
            yield from stream_task(context=context, route_override=route_override, cancelled=cancelled)
            return
        # Compatibility for constrained test/runtime gateway adapters. Their
        # completed output still came through the same gateway validation path.
        output = self._gateway.run_task(
            task_kind="dialogue_generation",
            context=context,
            route_override=route_override,
        )
        if cancelled():
            yield {"event": "cancelled"}
            return
        content = str(output.get("content", "") or "")
        yield {"event": "delta", "delta": content}
        yield {"event": "completed", "output": output, "fallback_used": False}

    def _context(
        self,
        *,
        actor_id: str,
        content: str,
        target_actor_id: str,
        control_mode: str,
        intent_type: str,
    ) -> dict[str, object]:
        context: dict[str, object] = {
            "actor_id": actor_id,
            "control_mode": control_mode,
            "snapshot": {},
            "memory": {
                "working_memory": [],
                "episodic_memories": [],
                "relational_memories": [],
            },
            "event": {
                "content": content,
                "target_actor_id": target_actor_id,
                "intent_type": intent_type,
            },
        }
        if self._context_provider is None:
            return context
        runtime_context = self._context_provider(actor_id)
        if not isinstance(runtime_context, Mapping):
            return context
        for key, value in runtime_context.items():
            if key in {"actor_id", "control_mode", "event"}:
                continue
            context[str(key)] = value
        return context
