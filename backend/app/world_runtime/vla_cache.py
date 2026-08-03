from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field

from app.world_runtime.vla_provider import VLAProviderRequest, VLAProviderResult


@dataclass(frozen=True)
class VLACacheKey:
    context_namespace: str
    cache_namespace: str
    capture_root_id: str
    capture_id: str
    clock_domain: str
    monotonic_tick: int | None
    query_window: tuple[int, int]
    artifact_refs_hash: str
    structured_fact_refs_hash: str
    advisory_route: str
    model_id: str
    model_version: str


@dataclass
class VLACacheEntry:
    result: VLAProviderResult
    stored_at: float
    expires_at: float


@dataclass
class VLACache:
    ttl_seconds: float = 30.0
    entries: dict[VLACacheKey, VLACacheEntry] = field(default_factory=dict)
    trace: list[dict[str, str]] = field(default_factory=list)

    def key_for_request(self, request: VLAProviderRequest) -> VLACacheKey:
        if "shared" in request.context_namespace or "shared" in request.cache_namespace:
            raise ValueError("VLA cache namespace must not be shared")
        return VLACacheKey(
            context_namespace=request.context_namespace,
            cache_namespace=request.cache_namespace,
            capture_root_id=request.capture_root_id,
            capture_id=request.capture_id,
            clock_domain=request.clock_domain,
            monotonic_tick=request.monotonic_tick,
            query_window=(request.query_frame.time_window.started_at, request.query_frame.time_window.ended_at),
            artifact_refs_hash=self._hash_list(request.artifact_refs),
            structured_fact_refs_hash=self._hash_list(request.structured_fact_refs),
            advisory_route=request.advisory_route.value,
            model_id=request.model_id,
            model_version=request.model_version,
        )

    def get(self, request: VLAProviderRequest, *, now: float | None = None) -> VLAProviderResult | None:
        now = now if now is not None else time.time()
        key = self.key_for_request(request)
        entry = self.entries.get(key)
        if entry is None:
            self.trace.append({"event": "miss", "request_id": request.request_id})
            return None
        if entry.expires_at <= now or entry.result.expires_at <= int(now):
            self.trace.append({"event": "stale", "request_id": request.request_id})
            return None
        self.trace.append({"event": "hit", "request_id": request.request_id})
        return entry.result

    def put(self, request: VLAProviderRequest, result: VLAProviderResult, *, now: float | None = None) -> VLACacheKey:
        now = now if now is not None else time.time()
        key = self.key_for_request(request)
        self.entries[key] = VLACacheEntry(result=result, stored_at=now, expires_at=now + self.ttl_seconds)
        self.trace.append({"event": "put", "request_id": request.request_id})
        return key

    @staticmethod
    def _hash_list(values: list[str]) -> str:
        return hashlib.sha256("|".join(sorted(values)).encode("utf-8")).hexdigest()
