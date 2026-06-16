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
        payload = {
            "model": self._model,
            "input": {
                "snapshot": snapshot.model_dump(),
                "recent_events": [event.model_dump() for event in recent_events],
                "recent_audit": [record.model_dump() for record in recent_audit],
            },
        }
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
            raw_candidates = data.get("candidates", [])
            return [InterventionCandidate.model_validate(item) for item in raw_candidates]
        except (ValueError, ValidationError, AttributeError) as exc:
            raise SimingLlmProviderInvalidOutput(str(exc)) from exc


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
