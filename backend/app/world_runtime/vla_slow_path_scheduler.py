from __future__ import annotations

import hashlib
import time
from collections import deque
from dataclasses import dataclass, field

from app.world_runtime.vla_provider import VLAProviderRequest, VLAProviderResult, VLAProviderStatus


@dataclass
class VLASchedulerTrace:
    event: str
    request_id: str
    owner_queue: str
    reason: str = ""
    advisory_route: str = "advisory-fast"


@dataclass
class VLASlowPathScheduler:
    max_queue_size: int = 8
    timeout_seconds: float = 8.0
    queues: dict[str, deque[VLAProviderRequest]] = field(default_factory=dict)
    fingerprints: dict[str, set[str]] = field(default_factory=dict)
    trace: list[VLASchedulerTrace] = field(default_factory=list)

    def enqueue(self, request: VLAProviderRequest, *, now: float | None = None, priority: int = 0) -> str:
        now = now if now is not None else time.time()
        owner_queue = self._owner_queue_name(request)
        queue = self.queues.setdefault(owner_queue, deque())
        seen = self.fingerprints.setdefault(owner_queue, set())
        fingerprint = self._fingerprint(request)
        if fingerprint in seen:
            self.trace.append(VLASchedulerTrace("deduped", request.request_id, owner_queue, "artifact_fingerprint_duplicate", request.advisory_route.value))
            return "deduped"
        if self._is_stale(request, now):
            self.trace.append(VLASchedulerTrace("discarded_stale", request.request_id, owner_queue, "request_expired", request.advisory_route.value))
            return "discarded_stale"
        if len(queue) >= self.max_queue_size:
            self.trace.append(VLASchedulerTrace("dropped_queue_full", request.request_id, owner_queue, "max_queue_size", request.advisory_route.value))
            return "dropped_queue_full"
        self._insert_by_priority(queue, request, priority)
        seen.add(fingerprint)
        self.trace.append(VLASchedulerTrace("enqueued", request.request_id, owner_queue, request.route_reason, request.advisory_route.value))
        return "enqueued"

    def pop_next(self, owner_kind: str, owner_id: str) -> VLAProviderRequest | None:
        owner_queue = self._queue_name(owner_kind, owner_id)
        queue = self.queues.get(owner_queue)
        if not queue:
            return None
        request = queue.popleft()
        self.trace.append(VLASchedulerTrace("dequeued", request.request_id, owner_queue, request.route_reason, request.advisory_route.value))
        return request

    def timeout_result(self, request: VLAProviderRequest) -> VLAProviderResult:
        return VLAProviderResult(
            result_id=f"vla_result:{request.request_id}:timeout",
            request_id=request.request_id,
            status=VLAProviderStatus.TIMEOUT,
            capture_root_id=request.capture_root_id,
            capture_id=request.capture_id,
            clock_domain=request.clock_domain,
            monotonic_tick=request.monotonic_tick,
            source_frame_index=request.source_frame_index,
            capture_relation="late_advisory",
            provider_id="vla_slow_path_scheduler",
            model_id=request.model_id,
            model_version=request.model_version,
            advisory_route=request.advisory_route,
            route_reason=request.route_reason,
            escalation_from_request_id=request.escalation_from_request_id,
            confidence=0.0,
            freshness="degraded",
            expires_at=int(time.time()) + 1,
            trace_refs=[request.request_id, request.capture_root_id, request.capture_id],
            fallback_reason="timeout_use_structured_facts_next_tick",
        )

    def trace_dicts(self) -> list[dict[str, str]]:
        return [entry.__dict__.copy() for entry in self.trace]

    def _owner_queue_name(self, request: VLAProviderRequest) -> str:
        return self._queue_name(request.owner_kind, request.owner_id)

    @staticmethod
    def _queue_name(owner_kind: str, owner_id: str) -> str:
        return f"{owner_kind}:{owner_id}"

    @staticmethod
    def _fingerprint(request: VLAProviderRequest) -> str:
        data = "|".join(
            [
                request.context_namespace,
                request.cache_namespace,
                request.capture_root_id,
                request.capture_id,
                request.clock_domain,
                "" if request.monotonic_tick is None else str(request.monotonic_tick),
                request.model_id,
                request.advisory_route.value,
                *sorted(request.artifact_refs),
                *sorted(request.structured_fact_refs),
            ]
        )
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    @staticmethod
    def _is_stale(request: VLAProviderRequest, now: float) -> bool:
        ended_at = request.query_frame.time_window.ended_at
        return ended_at > 0 and now - float(ended_at) > request.timeout_seconds

    @staticmethod
    def _insert_by_priority(queue: deque[VLAProviderRequest], request: VLAProviderRequest, priority: int) -> None:
        # Fast work wins equal-priority contention; deep work is only queued after an explicit escalation.
        request_priority = priority + (1 if request.advisory_route.value == "advisory-fast" else 0)
        for index, queued in enumerate(queue):
            queued_priority = 1 if queued.advisory_route.value == "advisory-fast" else 0
            if request_priority > queued_priority:
                queue.insert(index, request)
                return
        queue.append(request)
