import json
from typing import Protocol

import httpx
from pydantic import ValidationError

from app.models.authority_event import AuthorityEvent
from app.models.siming_event import FairnessStateSnapshot, InterventionCandidate, SimingAuditRecord
from app.config import Settings, SimingLlmRouteSettings


CHAT_COMPLETIONS_REQUIRED_CANDIDATE_FIELDS = {
    "candidate_id",
    "room_id",
    "scene_id",
    "zone_id",
    "causation_id",
    "correlation_id",
    "proposed_band",
    "established_fact_ids",
    "explanation",
    "confidence",
    "reason_tags",
    "source",
}


class SimingLlmProviderError(RuntimeError):
    pass


class SimingLlmProviderTimeout(SimingLlmProviderError):
    pass


class SimingLlmProviderInvalidOutput(SimingLlmProviderError):
    pass


class SimingLlmCandidateProvider(Protocol):
    def generate_candidates(
        self,
        *,
        snapshot: FairnessStateSnapshot,
        recent_events: list[AuthorityEvent],
        recent_audit: list[SimingAuditRecord],
    ) -> list[InterventionCandidate]:
        raise NotImplementedError


class DisabledSimingLlmCandidateProvider:
    def generate_candidates(
        self,
        *,
        snapshot: FairnessStateSnapshot,
        recent_events: list[AuthorityEvent],
        recent_audit: list[SimingAuditRecord],
    ) -> list[InterventionCandidate]:
        return []


class SimingLlmProviderRouter:
    def __init__(self, providers: list[SimingLlmCandidateProvider]) -> None:
        self.providers = list(providers)

    def generate_candidates(
        self,
        *,
        snapshot: FairnessStateSnapshot,
        recent_events: list[AuthorityEvent],
        recent_audit: list[SimingAuditRecord],
    ) -> list[InterventionCandidate]:
        last_error: SimingLlmProviderError | None = None
        for provider in self.providers:
            try:
                candidates = provider.generate_candidates(
                    snapshot=snapshot,
                    recent_events=recent_events,
                    recent_audit=recent_audit,
                )
            except SimingLlmProviderError as exc:
                last_error = exc
                continue
            if candidates:
                return candidates
        if last_error is not None:
            raise last_error
        return []


class HttpSimingLlmCandidateProvider:
    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str,
        model: str,
        timeout_seconds: float,
        route_id: str = "openai_responses",
        provider_name: str = "openai_responses",
    ) -> None:
        self._route_id = route_id
        self._provider_name = provider_name
        self._api_key = api_key
        self._endpoint = endpoint
        self._model = model
        self._timeout_seconds = timeout_seconds

    @property
    def route_id(self) -> str:
        return self._route_id

    @property
    def model(self) -> str:
        return self._model

    @property
    def timeout_seconds(self) -> float:
        return self._timeout_seconds

    def generate_candidates(
        self,
        *,
        snapshot: FairnessStateSnapshot,
        recent_events: list[AuthorityEvent],
        recent_audit: list[SimingAuditRecord],
    ) -> list[InterventionCandidate]:
        payload = self._request_payload(snapshot=snapshot, recent_events=recent_events, recent_audit=recent_audit)
        try:
            response = httpx.post(
                self._endpoint,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise SimingLlmProviderTimeout("Siming LLM provider timed out") from exc
        except httpx.HTTPError as exc:
            raise SimingLlmProviderError(str(exc)) from exc

        try:
            data = response.json()
            candidate_data = self._candidate_data_from_response(data)
            raw_candidates = candidate_data["candidates"]
            if not isinstance(raw_candidates, list):
                raise TypeError("provider response candidates must be a list")
            candidates: list[InterventionCandidate] = []
            for index, item in enumerate(raw_candidates):
                if self._provider_name in {"deepseek_chat", "seed_doubao", "qwen"}:
                    self._validate_chat_completions_candidate(item, index)
                candidates.append(InterventionCandidate.model_validate(item))
            return candidates
        except (KeyError, TypeError, ValueError, ValidationError, AttributeError) as exc:
            raise SimingLlmProviderInvalidOutput(str(exc)) from exc

    def _request_payload(
        self,
        *,
        snapshot: FairnessStateSnapshot,
        recent_events: list[AuthorityEvent],
        recent_audit: list[SimingAuditRecord],
    ) -> dict[str, object]:
        if self._provider_name in {"deepseek_chat", "seed_doubao", "qwen"}:
            return self._chat_completions_payload(
                snapshot=snapshot,
                recent_events=recent_events,
                recent_audit=recent_audit,
            )
        return self._responses_payload(
            snapshot=snapshot,
            recent_events=recent_events,
            recent_audit=recent_audit,
        )

    def _responses_payload(
        self,
        *,
        snapshot: FairnessStateSnapshot,
        recent_events: list[AuthorityEvent],
        recent_audit: list[SimingAuditRecord],
    ) -> dict[str, object]:
        context = {
            "snapshot": snapshot.model_dump(),
            "recent_events": [event.model_dump() for event in recent_events],
            "recent_audit": [record.model_dump() for record in recent_audit],
        }
        return {
            "model": self._model,
            "instructions": (
                "Return only candidate-level Siming intervention suggestions. "
                "Do not return authority events, selected paths, physical success claims, "
                "role belief truth, ESM mutations, or low-level character commands."
            ),
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(context, ensure_ascii=False, separators=(",", ":")),
                        }
                    ],
                }
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "siming_intervention_candidates",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["candidates"],
                        "properties": {
                            "candidates": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": [
                                        "candidate_id",
                                        "room_id",
                                        "scene_id",
                                        "zone_id",
                                        "causation_id",
                                        "correlation_id",
                                        "proposed_band",
                                        "target_actor_id",
                                        "target_object_id",
                                        "target_environment_id",
                                        "established_fact_ids",
                                        "explanation",
                                        "confidence",
                                        "reason_tags",
                                        "source",
                                    ],
                                    "properties": {
                                        "candidate_id": {"type": "string"},
                                        "room_id": {"type": "string"},
                                        "scene_id": {"type": "string"},
                                        "zone_id": {"type": "string"},
                                        "causation_id": {"type": "string"},
                                        "correlation_id": {"type": "string"},
                                        "proposed_band": {
                                            "type": "string",
                                            "enum": ["impulse", "opportunity", "fact_reveal", "environment_request", "none"],
                                        },
                                        "target_actor_id": {"type": ["string", "null"]},
                                        "target_object_id": {"type": ["string", "null"]},
                                        "target_environment_id": {"type": ["string", "null"]},
                                        "established_fact_ids": {"type": "array", "items": {"type": "string"}},
                                        "explanation": {"type": "string"},
                                        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                                        "reason_tags": {"type": "array", "items": {"type": "string"}},
                                        "source": {"type": "string", "enum": ["llm"]},
                                    },
                                },
                            }
                        },
                    },
                }
            },
        }

    def _chat_completions_payload(
        self,
        *,
        snapshot: FairnessStateSnapshot,
        recent_events: list[AuthorityEvent],
        recent_audit: list[SimingAuditRecord],
    ) -> dict[str, object]:
        context = {
            "snapshot": snapshot.model_dump(),
            "recent_events": [event.model_dump() for event in recent_events],
            "recent_audit": [record.model_dump() for record in recent_audit],
        }
        return {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return only candidate-level Siming intervention suggestions as a JSON object "
                        "with a single top-level key named candidates. Do not return authority events, "
                        "selected paths, physical success claims, role belief truth, ESM mutations, "
                        "or low-level character commands. Each candidate must explicitly include "
                        "candidate_id, room_id, scene_id, zone_id, causation_id, correlation_id, "
                        "proposed_band, target_actor_id, target_object_id, target_environment_id, "
                        "established_fact_ids, explanation, confidence, reason_tags, and source=\"llm\". "
                        "Do not omit keys. Use null for target_actor_id, target_object_id, or "
                        "target_environment_id when that target does not apply. For a known visual_fact_event "
                        "with an established_fact_id, return exactly one candidate using proposed_band "
                        "fact_reveal, source=\"llm\", the event room_id/scene_id/zone_id/correlation_id, "
                        "the event event_id as causation_id, and established_fact_ids containing the "
                        "event established_fact_id from recent_events. If target_actor_id is present, it "
                        "must be one of snapshot.eligible_actor_ids; otherwise use null. Do not invent "
                        "established_fact_ids or actor ids outside the supplied recent_events and snapshot."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(context, ensure_ascii=False, separators=(",", ":")),
                },
            ],
            "response_format": {"type": "json_object"},
        }

    def _candidate_data_from_response(self, data: object) -> dict[str, object]:
        if not isinstance(data, dict):
            raise TypeError("provider response JSON must be an object")
        if self._provider_name in {"deepseek_chat", "seed_doubao", "qwen"}:
            return self._candidate_data_from_deepseek_response(data)
        if isinstance(data.get("output_text"), str):
            parsed = json.loads(str(data["output_text"]))
            if not isinstance(parsed, dict):
                raise TypeError("provider output_text must decode to an object")
            return parsed
        output = data.get("output")
        if not isinstance(output, list):
            raise KeyError("provider response missing output text")
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for content_item in content:
                if not isinstance(content_item, dict):
                    continue
                text = content_item.get("text")
                if content_item.get("type") == "output_text" and isinstance(text, str):
                    parsed = json.loads(text)
                    if not isinstance(parsed, dict):
                        raise TypeError("provider output text must decode to an object")
                    return parsed
        raise KeyError("provider response missing output_text content")

    def _candidate_data_from_deepseek_response(self, data: dict[str, object]) -> dict[str, object]:
        choices = data.get("choices")
        if not isinstance(choices, list):
            raise KeyError("provider response missing choices")
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if isinstance(content, str):
                parsed = json.loads(content)
                if not isinstance(parsed, dict):
                    raise TypeError("provider content must decode to an object")
                return parsed
        raise KeyError("provider response missing message content")

    def _validate_chat_completions_candidate(self, item: object, index: int) -> None:
        if not isinstance(item, dict):
            raise TypeError(f"chat-completions candidate {index} must be an object")
        missing = sorted(CHAT_COMPLETIONS_REQUIRED_CANDIDATE_FIELDS.difference(item.keys()))
        if missing:
            raise ValueError(f"chat-completions candidate {index} missing explicit field(s): {', '.join(missing)}")
        target_actor_id = str(item.get("target_actor_id", "") or "").strip()
        target_environment_id = str(item.get("target_environment_id", "") or "").strip()
        if target_actor_id == "" and target_environment_id == "":
            raise ValueError(
                f"chat-completions candidate {index} missing explicit target_actor_id or target_environment_id"
            )
        if item.get("source") != "llm":
            raise ValueError(f"chat-completions candidate {index} source must be llm")


class FakeSimingLlmCandidateProvider:
    def __init__(self, candidates: list[InterventionCandidate], *, timeout: bool = False) -> None:
        self._candidates = [candidate.model_copy(deep=True) for candidate in candidates]
        self._timeout = timeout

    def generate_candidates(
        self,
        *,
        snapshot: FairnessStateSnapshot,
        recent_events: list[AuthorityEvent],
        recent_audit: list[SimingAuditRecord],
    ) -> list[InterventionCandidate]:
        if self._timeout:
            raise SimingLlmProviderTimeout("Siming LLM provider timed out")
        return [candidate.model_copy(deep=True) for candidate in self._candidates]


def build_siming_llm_provider(settings: Settings) -> SimingLlmCandidateProvider:
    providers: list[SimingLlmCandidateProvider] = []
    if settings.siming_llm_routes:
        for route in settings.siming_llm_routes:
            providers.append(_build_route_provider(settings, route))

    if not settings.siming_llm_routes or "siming_llm_provider_order" in settings.model_fields_set:
        for provider_name in settings.siming_llm_provider_order:
            if provider_name == "disabled":
                providers.append(DisabledSimingLlmCandidateProvider())
            elif provider_name in {"openai_responses", "deepseek_chat", "seed_doubao", "qwen"}:
                providers.append(_build_openai_responses_provider(settings))
    return SimingLlmProviderRouter(providers or [DisabledSimingLlmCandidateProvider()])


def _build_route_provider(settings: Settings, route: SimingLlmRouteSettings) -> SimingLlmCandidateProvider:
    if not route.enabled or route.provider == "disabled":
        return DisabledSimingLlmCandidateProvider()
    if route.provider in {"openai_responses", "deepseek_chat", "seed_doubao", "qwen"}:
        return _build_openai_responses_provider(settings, route=route)
    return DisabledSimingLlmCandidateProvider()


def _build_openai_responses_provider(
    settings: Settings,
    *,
    route: SimingLlmRouteSettings | None = None,
    ) -> SimingLlmCandidateProvider:
    api_key = route.api_key if route is not None and route.api_key is not None else settings.siming_llm_api_key
    if settings.siming_llm_mode != "http" or not api_key:
        return DisabledSimingLlmCandidateProvider()
    provider_name = route.provider if route is not None else settings.siming_llm_provider_order[0]
    route_id = route.route_id if route is not None else settings.siming_llm_provider_order[0]
    return HttpSimingLlmCandidateProvider(
        api_key=api_key,
        endpoint=route.endpoint if route is not None and route.endpoint is not None else settings.siming_llm_endpoint,
        model=route.model if route is not None and route.model is not None else settings.siming_llm_model,
        timeout_seconds=(
            route.timeout_seconds
            if route is not None and route.timeout_seconds is not None
            else settings.siming_llm_timeout_seconds
        ),
        route_id=route_id,
        provider_name=provider_name,
    )
