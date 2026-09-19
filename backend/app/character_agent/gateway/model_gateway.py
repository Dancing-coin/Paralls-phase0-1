import json
from collections.abc import Callable, Iterator

from pydantic import BaseModel

from app.character_agent.gateway.context_builder import CharacterContextBuilder
from app.character_agent.gateway.memory_recall import CharacterMemoryRecallPolicy, MemoryRecallResult, MissingRequiredMemoryEvidence
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
        prepared_recall: MemoryRecallResult | None = None,
    ) -> dict[str, object]:
        route = self._router.resolve_route(route_override)
        recall = prepared_recall if prepared_recall is not None else self._memory_recall.select(
            dict(context.get("memory", {}) or {}),
            context=context,
        )
        if recall.metadata.get("missing_required_refs"):
            raise MissingRequiredMemoryEvidence(list(recall.metadata["missing_required_refs"]))
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

    @staticmethod
    def freeze_prepared_request(request: dict[str, object]) -> bytes:
        """只冻结请求数据；Pydantic 值使用既有 JSON 合同。"""
        def model_json(value: object) -> object:
            if isinstance(value, BaseModel):
                return value.model_dump(mode="json")
            raise TypeError("character request contains a non-JSON value")

        try:
            return json.dumps(request, ensure_ascii=False, allow_nan=False, default=model_json).encode("utf-8")
        except (TypeError, ValueError):
            raise ValueError("character prepared request must contain JSON data") from None

    @staticmethod
    def _restore_prepared_request(request_json: bytes) -> dict[str, object]:
        if not isinstance(request_json, bytes):
            raise ValueError("character prepared request must be UTF-8 JSON bytes")

        def reject_constant(_value: str) -> object:
            raise ValueError("non-JSON numeric constant")

        try:
            request = json.loads(request_json.decode("utf-8"), parse_constant=reject_constant)
        except (ValueError, UnicodeError):
            raise ValueError("character prepared request must be UTF-8 JSON bytes") from None
        if not isinstance(request, dict):
            raise ValueError("character prepared request must be an object")
        task_kind = request.get("task_kind")
        if not isinstance(task_kind, str) or task_kind not in {"l2_reasoning", "l3_planning", "dialogue_generation"}:
            raise ValueError("character prepared request has an unsupported task kind")
        if not isinstance(request.get("context"), dict):
            raise ValueError("character prepared request must contain a context object")
        return request

    def complete_prepared_request(self, request_json: bytes) -> dict[str, object]:
        """Provider 阶段仅还原隔离输入、调用模型并校验输出。"""
        request = self._restore_prepared_request(request_json)
        task_kind = request["task_kind"]
        output = self._provider.complete(request)
        return self._validator.validate(task_kind=task_kind, output=output)

    def run_task(
        self,
        *,
        task_kind: str,
        context: dict[str, object],
        route_override: str | None = None,
        prepared_recall: MemoryRecallResult | None = None,
    ) -> dict[str, object]:
        request = self.prepare_run_request(
            task_kind=task_kind,
            context=context,
            route_override=route_override,
            prepared_recall=prepared_recall,
        )
        return self.complete_prepared_request(self.freeze_prepared_request(request))

    def stream_dialogue_task(
        self,
        *,
        context: dict[str, object],
        route_override: str | None = None,
        cancelled,
    ):
        """准备对话请求，再输出增量及校验后的最终结果。"""
        request = self.prepare_run_request(
            task_kind="dialogue_generation",
            context=context,
            route_override=route_override,
        )
        yield from self.stream_prepared_request(self.freeze_prepared_request(request), cancelled=cancelled)

    def stream_prepared_request(
        self, request_json: bytes, *, cancelled: Callable[[], bool],
    ) -> Iterator[dict[str, object]]:
        request = self._restore_prepared_request(request_json)
        if request["task_kind"] != "dialogue_generation":
            raise ValueError("character prepared stream requires a dialogue task")
        if cancelled():
            yield {"event": "cancelled"}
            return
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
