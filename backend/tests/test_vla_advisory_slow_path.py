from __future__ import annotations

from app.config import Settings
from app.world_runtime.intelligence_upgrade import AttentionContext, PerceptionQueryFrame, SampleInputRef, SpatialReference, TimeWindow
from app.world_runtime.vla_cache import VLACache
from app.world_runtime.vla_provider import VLAAdvisoryRoute, VLAProviderResult, VLAProviderStatus
from app.world_runtime.vla_routing import VLAAdvisoryRouteConfig, VLAAdvisoryRouter
from app.world_runtime.vla_slow_path import VLAAdvisorySlowPath
from app.world_runtime.vla_slow_path_scheduler import VLASlowPathScheduler


def _frame(*, tags: list[str] | None = None) -> PerceptionQueryFrame:
    return PerceptionQueryFrame(
        query_id="pqf:char_b:slow_path",
        consumer_kind="character",
        subject_id="char_b",
        time_window=TimeWindow(started_at=0, ended_at=0),
        spatial_reference=SpatialReference(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus"),
        visual_inputs=[SampleInputRef(provider_kind="visual_patch", ref_id="artifact:visual:1")],
        attention_context=AttentionContext(reason_tags=tags or []),
        multimodal_context_id="character_mm:char_b",
        cache_namespace="character_mm:char_b:vla_cache",
    )


class _Provider:
    provider_id = "test_vla_provider"
    model_id = "unused"
    model_version = "unused"

    def __init__(self, *, fast_conflict: bool = False) -> None:
        self.calls = []
        self.fast_conflict = fast_conflict

    def interpret(self, request):
        self.calls.append(request)
        return VLAProviderResult(
            result_id=f"result:{request.request_id}",
            request_id=request.request_id,
            status=VLAProviderStatus.REAL_PROVIDER_VERIFIED,
            provider_id=self.provider_id,
            model_id=request.model_id,
            model_version=request.model_version,
            advisory_route=request.advisory_route,
            route_reason=request.route_reason,
            escalation_from_request_id=request.escalation_from_request_id,
            findings=[{"finding_type": "visual_spatial_advisory", "summary": "advisory only"}],
            confidence=0.9 if request.advisory_route is VLAAdvisoryRoute.ADVISORY_DEEP else 0.3,
            conflict_refs=["l1:conflict"] if self.fast_conflict and request.advisory_route is VLAAdvisoryRoute.ADVISORY_FAST else [],
            expires_at=60,
        )


def _slow_path(provider: _Provider, *, deep_enabled: bool = False) -> VLAAdvisorySlowPath:
    return VLAAdvisorySlowPath(
        router=VLAAdvisoryRouter(VLAAdvisoryRouteConfig.from_settings(Settings(vla_advisory_deep_enabled=deep_enabled))),
        scheduler=VLASlowPathScheduler(),
        cache=VLACache(),
        provider=provider,
    )


def test_fast_result_is_cached_then_escalated_once_to_deep_without_authority_write() -> None:
    provider = _Provider(fast_conflict=True)
    slow_path = _slow_path(provider, deep_enabled=True)

    submitted = slow_path.submit_frame(_frame(), owner_kind="character", owner_id="char_b", now=0)
    fast = slow_path.consume_next(owner_kind="character", owner_id="char_b", now=0)
    deep = slow_path.consume_next(owner_kind="character", owner_id="char_b", now=0)

    assert submitted.scheduler_status == "enqueued"
    assert fast is not None and fast.advisory_route is VLAAdvisoryRoute.ADVISORY_FAST
    assert deep is not None and deep.advisory_route is VLAAdvisoryRoute.ADVISORY_DEEP
    assert deep.escalation_from_request_id == fast.request_id
    assert [call.model_id for call in provider.calls] == ["qwen3.7-flash", "qwen3.7-plus"]
    assert deep.advisory is True
    assert deep.writes_world_truth is False
    assert deep.writes_esm_authority is False
    assert deep.controls_actor is False
    assert slow_path.consume_next(owner_kind="character", owner_id="char_b", now=0) is None


def test_cache_hit_does_not_repeat_provider_call_for_a_sufficient_fast_result() -> None:
    provider = _Provider()
    slow_path = _slow_path(provider)

    slow_path.submit_frame(_frame(), owner_kind="character", owner_id="char_b", now=0)
    first = slow_path.consume_next(owner_kind="character", owner_id="char_b", now=0)
    second = slow_path.submit_frame(_frame(), owner_kind="character", owner_id="char_b", now=1)

    assert first is not None and first.advisory_route is VLAAdvisoryRoute.ADVISORY_FAST
    assert second.scheduler_status == "cache_hit"
    assert second.cached_result == first
    assert len(provider.calls) == 1


def test_pqf_deep_hint_skips_fast_and_uses_deep_route_directly() -> None:
    provider = _Provider()
    slow_path = _slow_path(provider, deep_enabled=True)

    submitted = slow_path.submit_frame(_frame(tags=["vla_deep"]), owner_kind="character", owner_id="char_b", now=0)
    result = slow_path.consume_next(owner_kind="character", owner_id="char_b", now=0)

    assert submitted.request.advisory_route is VLAAdvisoryRoute.ADVISORY_DEEP
    assert result is not None and result.advisory_route is VLAAdvisoryRoute.ADVISORY_DEEP
    assert [call.advisory_route for call in provider.calls] == [VLAAdvisoryRoute.ADVISORY_DEEP]


def test_slow_path_uses_pqf_clock_domain_when_callers_do_not_supply_now() -> None:
    provider = _Provider()
    slow_path = _slow_path(provider)

    submitted = slow_path.submit_frame(_frame(), owner_kind="character", owner_id="char_b")
    result = slow_path.consume_next(owner_kind="character", owner_id="char_b")

    assert submitted.scheduler_status == "enqueued"
    assert result is not None and result.status is VLAProviderStatus.REAL_PROVIDER_VERIFIED
