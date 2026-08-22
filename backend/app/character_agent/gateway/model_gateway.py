from app.character_agent.gateway.context_builder import CharacterContextBuilder
from app.character_agent.gateway.memory_recall import CharacterMemoryRecallPolicy
from app.character_agent.gateway.model_provider import CharacterModelProvider
from app.character_agent.gateway.model_router import CharacterModelRouter
from app.character_agent.gateway.output_validator import CharacterStructuredOutputValidator
from app.character_agent.gateway.prompt_policy import CharacterPromptPolicy


class CharacterModelGateway:
    def __init__(
        self,
        *,
        provider: CharacterModelProvider | None = None,
        prompt_policy: CharacterPromptPolicy | None = None,
        validator: CharacterStructuredOutputValidator | None = None,
        router: CharacterModelRouter | None = None,
        context_builder: CharacterContextBuilder | None = None,
    ) -> None:
        self._provider = provider or CharacterModelProvider()
        self._prompt_policy = prompt_policy or CharacterPromptPolicy()
        self._validator = validator or CharacterStructuredOutputValidator()
        self._router = router or CharacterModelRouter()
        self._context_builder = context_builder or CharacterContextBuilder()
        self._memory_recall = CharacterMemoryRecallPolicy()

    def prepare_run_request(
        self,
        *,
        task_kind: str,
        context: dict[str, object],
        route_override: str | None = None,
    ) -> dict[str, object]:
        route = self._router.resolve_route(route_override)
        recall = self._memory_recall.select(
            dict(context.get("memory", {}) or {}),
            context=context,
        )
        prepared_context = self._context_builder.build_context(
            actor_id=str(context.get("actor_id", "") or ""),
            snapshot=context.get("snapshot", {}) or {},
            memory_bundle=recall.memory,
            control_mode=str(context.get("control_mode", "") or ""),
            working_memory_state=context.get("working_memory_state") if context.get("working_memory_state") is not None else None,
            profile=context.get("profile") if context.get("profile") is not None else None,
        )
        for key, value in context.items():
            if key in {"actor_id", "snapshot", "memory", "control_mode", "working_memory_state"}:
                continue
            prepared_context[key] = value
        prepared_context["memory_recall"] = recall.metadata
        return {
            "task_kind": task_kind,
            "route": route,
            "context": prepared_context,
            "prompt": self._prompt_policy.build_prompt(
                task_kind=task_kind,
                context={
                    **context,
                    "snapshot": prepared_context["snapshot"],
                    "memory": prepared_context["memory"],
                    "memory_recall": recall.metadata,
                    "working_memory_state": prepared_context.get("working_memory_state", context.get("working_memory_state")),
                },
                route=route,
            ),
            "policy": self._prompt_policy.build_policy(task_kind=task_kind, route=route),
        }

    def run_task(
        self,
        *,
        task_kind: str,
        context: dict[str, object],
        route_override: str | None = None,
    ) -> dict[str, object]:
        request = self.prepare_run_request(
            task_kind=task_kind,
            context=context,
            route_override=route_override,
        )
        output = self._provider.complete(request)
        return self._validator.validate(task_kind=task_kind, output=output)

    def stream_dialogue_task(
        self,
        *,
        context: dict[str, object],
        route_override: str | None = None,
        cancelled,
    ):
        """Yield display deltas and then one completed, validated dialogue output."""
        request = self.prepare_run_request(
            task_kind="dialogue_generation",
            context=context,
            route_override=route_override,
        )
        for provider_event in self._provider.stream_dialogue(request, cancelled=cancelled):
            event_type = str(provider_event.get("event", "") or "")
            if event_type == "cancelled" or cancelled():
                yield {"event": "cancelled"}
                return
            if event_type == "delta":
                delta = str(provider_event.get("delta", "") or "")
                if delta:
                    yield {"event": "delta", "delta": delta}
                continue
            if event_type != "completed":
                raise ValueError("character dialogue stream emitted an unsupported event")
            output = provider_event.get("output", {})
            if not isinstance(output, dict):
                raise ValueError("character dialogue stream completed without an output object")
            yield {
                "event": "completed",
                "output": self._validator.validate(task_kind="dialogue_generation", output=output),
                "fallback_used": bool(provider_event.get("fallback_used", False)),
            }
            return
        raise ValueError("character dialogue stream ended without a completed output")
