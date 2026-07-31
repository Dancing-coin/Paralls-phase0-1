from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.world_runtime.intelligence_upgrade import PerceptionQueryFrame
from app.world_runtime.vla_provider import VLAAdvisoryRoute, VLAProviderRequest, VLAProviderResult, VLAProviderStatus


@dataclass(frozen=True)
class VLAAdvisoryRouteConfig:
    fast_model_id: str
    fast_model_version: str
    fast_timeout_seconds: float
    deep_enabled: bool
    deep_model_id: str
    deep_model_version: str
    deep_timeout_seconds: float
    deep_confidence_threshold: float

    @classmethod
    def from_settings(cls, configuration: Settings) -> "VLAAdvisoryRouteConfig":
        return cls(
            fast_model_id=configuration.vla_advisory_fast_model,
            fast_model_version=configuration.vla_advisory_fast_model_version,
            fast_timeout_seconds=configuration.vla_advisory_fast_timeout_seconds,
            deep_enabled=configuration.vla_advisory_deep_enabled,
            deep_model_id=configuration.vla_advisory_deep_model,
            deep_model_version=configuration.vla_advisory_deep_model_version,
            deep_timeout_seconds=configuration.vla_advisory_deep_timeout_seconds,
            deep_confidence_threshold=configuration.vla_advisory_deep_confidence_threshold,
        )


@dataclass(frozen=True)
class VLAAdvisoryRouteDecision:
    route: VLAAdvisoryRoute
    reason: str


class VLAAdvisoryRouter:
    """Selects non-authoritative slow-path work; it never executes or settles it."""

    def __init__(self, configuration: VLAAdvisoryRouteConfig) -> None:
        self._configuration = configuration

    def initial_decision(self, frame: PerceptionQueryFrame) -> VLAAdvisoryRouteDecision:
        tags = {tag.strip().lower() for tag in frame.attention_context.reason_tags}
        if tags.intersection({"vla_deep", "high_uncertainty", "conflict", "cross_modal_conflict"}):
            if not self._configuration.deep_enabled:
                return VLAAdvisoryRouteDecision(VLAAdvisoryRoute.ADVISORY_FAST, "deep_route_disabled_use_fast")
            return VLAAdvisoryRouteDecision(VLAAdvisoryRoute.ADVISORY_DEEP, "pqf_high_uncertainty_or_conflict")
        return VLAAdvisoryRouteDecision(VLAAdvisoryRoute.ADVISORY_FAST, "default_fast")

    def request_for_frame(
        self,
        frame: PerceptionQueryFrame,
        *,
        owner_kind: str,
        owner_id: str,
        decision: VLAAdvisoryRouteDecision | None = None,
        escalation_from_request_id: str = "",
    ) -> VLAProviderRequest:
        decision = decision or self.initial_decision(frame)
        if decision.route is VLAAdvisoryRoute.ADVISORY_DEEP and not self._configuration.deep_enabled:
            decision = VLAAdvisoryRouteDecision(VLAAdvisoryRoute.ADVISORY_FAST, "deep_route_disabled_use_fast")
        if decision.route is VLAAdvisoryRoute.ADVISORY_DEEP:
            model_id = self._configuration.deep_model_id
            model_version = self._configuration.deep_model_version
            timeout_seconds = self._configuration.deep_timeout_seconds
        else:
            model_id = self._configuration.fast_model_id
            model_version = self._configuration.fast_model_version
            timeout_seconds = self._configuration.fast_timeout_seconds
        request = VLAProviderRequest.from_pqf(
            frame,
            owner_kind=owner_kind,
            owner_id=owner_id,
            model_id=model_id,
            model_version=model_version,
            timeout_seconds=timeout_seconds,
            advisory_route=decision.route,
            route_reason=decision.reason,
            escalation_from_request_id=escalation_from_request_id,
        )
        return request.model_copy(update={"request_id": f"{request.request_id}:{decision.route.value}"})

    def escalation_decision(self, result: VLAProviderResult) -> VLAAdvisoryRouteDecision | None:
        if not self._configuration.deep_enabled:
            return None
        if result.advisory_route is VLAAdvisoryRoute.ADVISORY_DEEP:
            return None
        if result.status in {VLAProviderStatus.TIMEOUT, VLAProviderStatus.ERROR}:
            return None
        if result.conflict_refs:
            return VLAAdvisoryRouteDecision(VLAAdvisoryRoute.ADVISORY_DEEP, "fast_result_conflicts_with_structured_facts")
        if result.missing_inputs:
            return VLAAdvisoryRouteDecision(VLAAdvisoryRoute.ADVISORY_DEEP, "fast_result_missing_inputs")
        if result.confidence < self._configuration.deep_confidence_threshold:
            return VLAAdvisoryRouteDecision(VLAAdvisoryRoute.ADVISORY_DEEP, "fast_result_low_confidence")
        return None
