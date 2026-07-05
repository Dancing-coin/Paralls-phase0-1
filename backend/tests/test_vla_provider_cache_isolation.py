from __future__ import annotations

import pytest

from app.world_runtime.intelligence_upgrade import PerceptionQueryFrame, SampleInputRef, SpatialReference, TimeWindow
from app.world_runtime.vla_cache import VLACache
from app.world_runtime.vla_provider import DeterministicMockVLAProvider, VLAProviderRequest


def _request(owner_kind: str, owner_id: str, fact_ref: str, ended_at: int = 1) -> VLAProviderRequest:
    context = f"character_mm:{owner_id}" if owner_kind == "character" else "siming_mm:room_demo"
    frame = PerceptionQueryFrame(
        query_id=f"pqf:{owner_id}:{ended_at}",
        consumer_kind=owner_kind,
        subject_id=owner_id,
        time_window=TimeWindow(started_at=0, ended_at=ended_at),
        spatial_reference=SpatialReference(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus"),
        visual_inputs=[SampleInputRef(provider_kind="visual_patch", ref_id="runtime://artifact/shared-visual.png")],
        structured_fact_refs=[fact_ref],
        multimodal_context_id=context,
        cache_namespace=f"{context}:vla_cache",
    )
    return VLAProviderRequest.from_pqf(frame, owner_kind=owner_kind, owner_id=owner_id, model_id="qwen3-vl-plus", model_version="qwen3-vl-plus:2026-07-02")


def test_cache_namespaces_isolate_character_and_siming_for_same_artifact() -> None:
    cache = VLACache(ttl_seconds=30.0)
    char_request = _request("character", "char_b", "raw_fact_event:1")
    siming_request = _request("siming", "siming", "raw_fact_event:1")
    result = DeterministicMockVLAProvider().interpret(char_request)

    cache.put(char_request, result, now=1.0)

    assert cache.get(char_request, now=2.0) == result
    assert cache.get(siming_request, now=2.0) is None
    assert cache.key_for_request(char_request).cache_namespace != cache.key_for_request(siming_request).cache_namespace


def test_cache_key_changes_when_l1_fact_refs_change() -> None:
    cache = VLACache(ttl_seconds=30.0)
    old_request = _request("character", "char_b", "raw_fact_event:old", ended_at=1)
    new_request = _request("character", "char_b", "raw_fact_event:new", ended_at=2)
    result = DeterministicMockVLAProvider().interpret(old_request)

    cache.put(old_request, result, now=1.0)

    assert cache.get(new_request, now=2.0) is None
    assert cache.key_for_request(old_request).structured_fact_refs_hash != cache.key_for_request(new_request).structured_fact_refs_hash


def test_cache_key_changes_when_capture_clock_changes_even_for_same_refs() -> None:
    cache = VLACache(ttl_seconds=30.0)
    first = _request("character", "char_b", "raw_fact_event:1", ended_at=1)
    second_frame = first.query_frame.model_copy(
        update={
            "capture_root_id": "capture_root:godot_main:room_demo:scene_demo:zone_focus:2",
            "capture_id": "capture:capture_root:godot_main:room_demo:scene_demo:zone_focus:2:character:char_b",
            "clock_domain": "godot_main",
            "monotonic_tick": 2,
        }
    )
    second = VLAProviderRequest.from_pqf(
        second_frame,
        owner_kind="character",
        owner_id="char_b",
        model_id="qwen3-vl-plus",
        model_version="qwen3-vl-plus:2026-07-02",
    )
    result = DeterministicMockVLAProvider().interpret(first)

    cache.put(first, result, now=1.0)

    assert cache.get(second, now=2.0) is None
    assert cache.key_for_request(first).capture_root_id != cache.key_for_request(second).capture_root_id


def test_cache_rejects_stale_result_and_shared_namespace() -> None:
    cache = VLACache(ttl_seconds=1.0)
    request = _request("character", "char_b", "raw_fact_event:1")
    result = DeterministicMockVLAProvider().interpret(request)

    cache.put(request, result, now=1.0)

    assert cache.get(request, now=100.0) is None
    with pytest.raises(ValueError, match="must not be shared"):
        bad_frame = request.query_frame.model_copy(
            update={
                "multimodal_context_id": "character_mm:shared",
                "cache_namespace": "character_mm:shared:vla_cache",
            }
        )
        VLACache().key_for_request(
            VLAProviderRequest(
                request_id="bad",
                owner_kind="character",
                owner_id="char_b",
                query_frame=bad_frame,
                context_namespace="character_mm:shared",
                cache_namespace="character_mm:shared:vla_cache",
                model_id="qwen3-vl-plus",
            )
        )
