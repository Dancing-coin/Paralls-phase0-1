import json
from typing import Protocol

import httpx
from pydantic import ValidationError

from app.models.authority_event import AuthorityEvent
from app.models.siming_event import FairnessStateSnapshot, InterventionCandidate, SimingAuditRecord
from app.config import Settings


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


class HttpSimingLlmCandidateProvider:
    def __init__(self, *, api_key: str, endpoint: str, model: str, timeout_seconds: float) -> None:
        self._api_key = api_key
        self._endpoint = endpoint
        self._model = model
        self._timeout_seconds = timeout_seconds

    def generate_candidates(
        self,
        *,
        snapshot: FairnessStateSnapshot,
        recent_events: list[AuthorityEvent],
        recent_audit: list[SimingAuditRecord],
    ) -> list[InterventionCandidate]:
        payload = self._responses_payload(snapshot=snapshot, recent_events=recent_events, recent_audit=recent_audit)
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
            return [InterventionCandidate.model_validate(item) for item in raw_candidates]
        except (KeyError, TypeError, ValueError, ValidationError, AttributeError) as exc:
            raise SimingLlmProviderInvalidOutput(str(exc)) from exc

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

    def _candidate_data_from_response(self, data: object) -> dict[str, object]:
        if not isinstance(data, dict):
            raise TypeError("provider response JSON must be an object")
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
    if settings.siming_llm_mode != "http" or not settings.siming_llm_api_key:
        return DisabledSimingLlmCandidateProvider()
    return HttpSimingLlmCandidateProvider(
        api_key=settings.siming_llm_api_key,
        endpoint=settings.siming_llm_endpoint,
        model=settings.siming_llm_model,
        timeout_seconds=settings.siming_llm_timeout_seconds,
    )
