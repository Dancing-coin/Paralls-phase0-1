from __future__ import annotations

from app.config import Settings
from app.world_runtime.intelligence_upgrade import AttentionContext, PerceptionQueryFrame, SpatialReference, TimeWindow
from app.world_runtime.vla_cache import VLACache
from app.world_runtime.vla_provider import VLAAdvisoryRoute, VLAProviderResult, VLAProviderStatus
from app.world_runtime.vla_routing import VLAAdvisoryRouteConfig, VLAAdvisoryRouter
from app.world_runtime.vla_slow_path_scheduler import VLASlowPathScheduler


def _frame(*, tags: list[str] | None = None) -> PerceptionQueryFrame:
    return PerceptionQueryFrame(
        query_id="pqf:char_b:routing",
        consumer_kind="character",
        subject_id="char_b",
        time_window=TimeWindow(started_at=0, ended_at=0),
        spatial_reference=SpatialReference(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus"),
        multimodal_context_id="character_mm:char_b",
        cache_namespace="character_mm:char_b:vla_cache",
        attention_context=AttentionContext(reason_tags=tags or []),
    )


def _router(*, deep_enabled: bool = False) -> VLAAdvisoryRouter:
    return VLAAdvisoryRouter(VLAAdvisoryRouteConfig.from_settings(Settings(vla_advisory_deep_enabled=deep_enabled)))


def _result(request, **overrides: object) -> VLAProviderResult:
    values: dict[str, object] = {
        "result_id": "result:routing",
        "request_id": request.request_id,
        "status": VLAProviderStatus.MOCK_PROVIDER_VERIFIED,
        "provider_id": "test",
        "model_id": request.model_id,
        "model_version": request.model_version,
        "advisory_route": request.advisory_route,
        "route_reason": request.route_reason,
        "confidence": 0.8,
        "expires_at": 60,
    }
    values.update(overrides)
    return VLAProviderResult(**values)


def test_default_pqf_uses_qwen_fast_route_and_fast_timeout() -> None:
    request = _router().request_for_frame(_frame(), owner_kind="character", owner_id="char_b")

    assert request.advisory_route is VLAAdvisoryRoute.ADVISORY_FAST
    assert request.model_id == "qwen3.7-flash"
    assert request.timeout_seconds == 12.0
    assert request.route_reason == "default_fast"


def test_production_default_keeps_conflict_or_high_uncertainty_on_fast_route() -> None:
    router = _router()
    request = router.request_for_frame(_frame(tags=["cross_modal_conflict"]), owner_kind="character", owner_id="char_b")

    assert request.advisory_route is VLAAdvisoryRoute.ADVISORY_FAST
    assert request.model_id == "qwen3.7-flash"
    assert request.route_reason == "deep_route_disabled_use_fast"
    assert request.context_namespace == "character_mm:char_b"


def test_fast_result_escalates_once_for_conflict_or_low_confidence_but_not_timeout() -> None:
    router = _router(deep_enabled=True)
    fast = router.request_for_frame(_frame(), owner_kind="character", owner_id="char_b")

    conflict = router.escalation_decision(_result(fast, conflict_refs=["l1:conflict"]))
    low_confidence = router.escalation_decision(_result(fast, confidence=0.2))
    timeout = router.escalation_decision(_result(fast, status=VLAProviderStatus.TIMEOUT))
    deep = router.request_for_frame(_frame(), owner_kind="character", owner_id="char_b", decision=conflict, escalation_from_request_id=fast.request_id)

    assert conflict is not None and conflict.route is VLAAdvisoryRoute.ADVISORY_DEEP
    assert low_confidence is not None and low_confidence.route is VLAAdvisoryRoute.ADVISORY_DEEP
    assert timeout is None
    assert deep.escalation_from_request_id == fast.request_id
    assert router.escalation_decision(_result(deep, conflict_refs=["l1:conflict"])) is None


def test_route_and_model_isolate_cache_and_fast_precedes_deep_at_equal_priority() -> None:
    router = _router(deep_enabled=True)
    fast = router.request_for_frame(_frame(), owner_kind="character", owner_id="char_b")
    deep = router.request_for_frame(_frame(tags=["vla_deep"]), owner_kind="character", owner_id="char_b")
    cache = VLACache()
    scheduler = VLASlowPathScheduler()

    assert cache.key_for_request(fast).advisory_route != cache.key_for_request(deep).advisory_route
    assert cache.key_for_request(fast).model_id != cache.key_for_request(deep).model_id
    assert scheduler.enqueue(deep, now=0) == "enqueued"
    assert scheduler.enqueue(fast, now=0) == "enqueued"
    assert scheduler.pop_next("character", "char_b") == fast
