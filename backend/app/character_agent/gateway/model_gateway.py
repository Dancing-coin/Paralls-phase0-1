from app.character_agent.gateway.context_builder import CharacterContextBuilder
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

    def prepare_run_request(
        self,
        *,
        task_kind: str,
        context: dict[str, object],
        route_override: str | None = None,
    ) -> dict[str, object]:
        route = self._router.resolve_route(route_override)
        prepared_context = self._context_builder.build_context(
            actor_id=str(context.get("actor_id", "") or ""),
            snapshot=context.get("snapshot", {}) or {},
            memory_bundle=dict(context.get("memory", {}) or {}),
            control_mode=str(context.get("control_mode", "") or ""),
            working_memory_state=context.get("working_memory_state") if context.get("working_memory_state") is not None else None,
            profile=context.get("profile") if context.get("profile") is not None else None,
        )
        for key, value in context.items():
            if key in {"actor_id", "snapshot", "memory", "control_mode", "working_memory_state"}:
                continue
            prepared_context[key] = value
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
