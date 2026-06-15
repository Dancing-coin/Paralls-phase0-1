from typing import Protocol

from app.models.authority_event import AuthorityEvent
from app.models.siming_event import FairnessStateSnapshot, InterventionCandidate, SimingAuditRecord


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
