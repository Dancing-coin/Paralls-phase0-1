from __future__ import annotations

import time
from dataclasses import dataclass

from app.world_runtime.intelligence_upgrade import PerceptionQueryFrame
from app.world_runtime.vla_cache import VLACache
from app.world_runtime.vla_provider import (
    DisabledVLAProvider,
    HTTPVLAProviderAdapter,
    LocalVLAProviderAdapter,
    VLAProviderProtocol,
    VLAProviderRequest,
    VLAProviderResult,
)
from app.world_runtime.vla_routing import VLAAdvisoryRouteConfig, VLAAdvisoryRouter
from app.world_runtime.vla_slow_path_scheduler import VLASlowPathScheduler


@dataclass(frozen=True)
class VLASlowPathSubmission:
    request: VLAProviderRequest
    scheduler_status: str
    cached_result: VLAProviderResult | None = None


class VLAAdvisorySlowPath:
    """Runs bounded VLA advisory work without acquiring any authority capability."""

    def __init__(
        self,
        *,
        router: VLAAdvisoryRouter,
        scheduler: VLASlowPathScheduler,
        cache: VLACache,
        provider: VLAProviderProtocol,
    ) -> None:
        self._router = router
        self._scheduler = scheduler
        self._cache = cache
        self._provider = provider

    @classmethod
    def from_runtime_settings(cls) -> "VLAAdvisorySlowPath":
        from app.config import settings

        if settings.vla_provider_mode == "disabled":
            provider: VLAProviderProtocol = DisabledVLAProvider()
        elif settings.vla_provider_mode == "local":
            provider = LocalVLAProviderAdapter(model_id=settings.vla_advisory_fast_model)
        else:
            provider = HTTPVLAProviderAdapter.from_runtime_settings()
        return cls(
            router=VLAAdvisoryRouter(VLAAdvisoryRouteConfig.from_settings(settings)),
            scheduler=VLASlowPathScheduler(
                max_queue_size=settings.vla_provider_max_queue_size,
                timeout_seconds=settings.vla_advisory_deep_timeout_seconds,
            ),
            cache=VLACache(ttl_seconds=settings.vla_provider_cache_ttl_seconds),
            provider=provider,
        )

    def submit_frame(
        self,
        frame: PerceptionQueryFrame,
        *,
        owner_kind: str,
        owner_id: str,
        now: float | None = None,
        priority: int = 0,
    ) -> VLASlowPathSubmission:
        request = self._router.request_for_frame(frame, owner_kind=owner_kind, owner_id=owner_id)
        return self._submit_request(request, now=now if now is not None else self._request_clock_now(request), priority=priority)

    def consume_next(
        self,
        *,
        owner_kind: str,
        owner_id: str,
        now: float | None = None,
    ) -> VLAProviderResult | None:
        request = self._scheduler.pop_next(owner_kind, owner_id)
        if request is None:
            return None
        effective_now = now if now is not None else self._request_clock_now(request)
        cached = self._cache.get(request, now=effective_now)
        if cached is not None:
            self._enqueue_escalation_if_needed(request, cached, now=effective_now)
            return cached

        started_at = time.monotonic()
        result = self._provider.interpret(request)
        if time.monotonic() - started_at > request.timeout_seconds:
            result = self._scheduler.timeout_result(request)
        self._cache.put(request, result, now=effective_now)
        self._enqueue_escalation_if_needed(request, result, now=effective_now)
        return result

    def _submit_request(
        self,
        request: VLAProviderRequest,
        *,
        now: float | None,
        priority: int,
    ) -> VLASlowPathSubmission:
        cached = self._cache.get(request, now=now)
        if cached is not None:
            self._enqueue_escalation_if_needed(request, cached, now=now)
            return VLASlowPathSubmission(request=request, scheduler_status="cache_hit", cached_result=cached)
        return VLASlowPathSubmission(
            request=request,
            scheduler_status=self._scheduler.enqueue(request, now=now, priority=priority),
        )

    def _enqueue_escalation_if_needed(
        self,
        request: VLAProviderRequest,
        result: VLAProviderResult,
        *,
        now: float | None,
    ) -> None:
        decision = self._router.escalation_decision(result)
        if decision is None:
            return
        deep_request = self._router.request_for_frame(
            request.query_frame,
            owner_kind=request.owner_kind,
            owner_id=request.owner_id,
            decision=decision,
            escalation_from_request_id=request.request_id,
        )
        self._submit_request(deep_request, now=now, priority=0)

    @staticmethod
    def _request_clock_now(request: VLAProviderRequest) -> float:
        return float(request.query_frame.wall_clock_ts or request.query_frame.time_window.ended_at)
