from __future__ import annotations

from app.world_runtime.intelligence_upgrade import PerceptionQueryFrame, SampleInputRef, SpatialReference, TimeWindow
from app.world_runtime.vla_provider import VLAProviderRequest, VLAProviderStatus
from app.world_runtime.vla_slow_path_scheduler import VLASlowPathScheduler


def _request(owner_kind: str, owner_id: str, ref: str, ended_at: int = 1) -> VLAProviderRequest:
    context = f"character_mm:{owner_id}" if owner_kind == "character" else "siming_mm:room_demo"
    frame = PerceptionQueryFrame(
        query_id=f"pqf:{owner_id}:{ref}:{ended_at}",
        consumer_kind=owner_kind,
        subject_id=owner_id,
        time_window=TimeWindow(started_at=0, ended_at=ended_at),
        spatial_reference=SpatialReference(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus"),
        visual_inputs=[SampleInputRef(provider_kind="visual_patch", ref_id=f"runtime://artifact/{ref}.png")],
        multimodal_context_id=context,
        cache_namespace=f"{context}:vla_cache",
    )
    return VLAProviderRequest.from_pqf(frame, owner_kind=owner_kind, owner_id=owner_id, model_id="qwen3-vl-plus", timeout_seconds=2.0)


def test_scheduler_separates_character_and_siming_queues() -> None:
    scheduler = VLASlowPathScheduler(max_queue_size=4, timeout_seconds=2.0)
    char_request = _request("character", "char_b", "visual-a")
    siming_request = _request("siming", "siming", "visual-a")

    assert scheduler.enqueue(char_request, now=1.0) == "enqueued"
    assert scheduler.enqueue(siming_request, now=1.0) == "enqueued"
    assert set(scheduler.queues) == {"character:char_b", "siming:siming"}
    assert scheduler.pop_next("character", "char_b") == char_request
    assert scheduler.pop_next("siming", "siming") == siming_request


def test_scheduler_dedupes_by_artifact_fingerprint_per_owner() -> None:
    scheduler = VLASlowPathScheduler(max_queue_size=4, timeout_seconds=2.0)
    request = _request("character", "char_b", "visual-a")
    duplicate = _request("character", "char_b", "visual-a")

    assert scheduler.enqueue(request, now=1.0) == "enqueued"
    assert scheduler.enqueue(duplicate, now=1.0) == "deduped"
    assert scheduler.trace[-1].reason == "artifact_fingerprint_duplicate"


def test_scheduler_drops_full_queue_and_discards_stale_requests() -> None:
    scheduler = VLASlowPathScheduler(max_queue_size=1, timeout_seconds=2.0)
    first = _request("character", "char_b", "visual-a")
    second = _request("character", "char_b", "visual-b")
    stale = _request("character", "char_c", "visual-c", ended_at=1)

    assert scheduler.enqueue(first, now=1.0) == "enqueued"
    assert scheduler.enqueue(second, now=1.0) == "dropped_queue_full"
    assert scheduler.enqueue(stale, now=10.0) == "discarded_stale"


def test_scheduler_timeout_result_does_not_block_current_tick() -> None:
    scheduler = VLASlowPathScheduler(max_queue_size=4, timeout_seconds=0.01)
    request = _request("character", "char_b", "visual-a")
    result = scheduler.timeout_result(request)

    assert result.status == VLAProviderStatus.TIMEOUT
    assert result.advisory is True
    assert result.fallback_reason == "timeout_use_structured_facts_next_tick"
