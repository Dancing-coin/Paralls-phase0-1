from __future__ import annotations

import pytest

from app.models.capture_clock import same_capture_tick
from app.world_runtime.intelligence_upgrade import PerceptionQueryFrame, SampleInputRef, SpatialReference, TimeWindow
from app.world_runtime.vla_provider import VLAProviderRequest, VLAProviderResult, VLAProviderStatus


def _frame(subject_id: str = "char_b") -> PerceptionQueryFrame:
    return PerceptionQueryFrame(
        query_id=f"pqf:{subject_id}:1",
        consumer_kind="character",
        subject_id=subject_id,
        capture_root_id="capture_root:godot_main:room_demo:scene_demo:zone_focus:1",
        clock_domain="godot_main",
        monotonic_tick=1,
        source_frame_index=7,
        time_window=TimeWindow(started_at=0, ended_at=1),
        spatial_reference=SpatialReference(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus"),
        attention_context={"target_actor_ids": [], "target_object_ids": ["obj_letter"], "target_environment_ids": [], "reason_tags": []},
        visual_inputs=[SampleInputRef(provider_kind="visual_patch", ref_id="runtime://artifact/visual.png")],
        spatial_inputs=[SampleInputRef(provider_kind="spatial_patch", ref_id="runtime://space/zone_focus/occupancy/1")],
        structured_fact_refs=["raw_fact_event:spatial_access_fact:actor_approached_object:1"],
        multimodal_context_id=f"character_mm:{subject_id}",
        cache_namespace=f"character_mm:{subject_id}:vla_cache",
    )


def test_vla_provider_request_is_built_from_pqf_and_artifact_refs() -> None:
    frame = _frame()
    request = VLAProviderRequest.from_pqf(frame, owner_kind="character", owner_id="char_b", model_id="qwen3-vl-plus")

    assert request.context_namespace == frame.multimodal_context_id
    assert request.cache_namespace == frame.cache_namespace
    assert request.artifact_refs == ["runtime://artifact/visual.png", "runtime://space/zone_focus/occupancy/1"]
    assert request.structured_fact_refs == ["raw_fact_event:spatial_access_fact:actor_approached_object:1"]
    assert request.advisory_only is True
    assert request.capture_root_id == frame.capture_root_id
    assert request.clock_domain == "godot_main"
    assert request.monotonic_tick == 1
    assert request.target_ref == frame.target_ref
    assert request.world_anchor_id == frame.world_anchor_id


def test_vla_request_rejects_shared_context_and_wrong_owner_namespace() -> None:
    frame = _frame()

    with pytest.raises(ValueError, match="must not be shared"):
        VLAProviderRequest(
            request_id="bad",
            owner_kind="character",
            owner_id="char_b",
            query_frame=frame.model_copy(update={"multimodal_context_id": "character_mm:shared"}),
            context_namespace="character_mm:shared",
            cache_namespace="character_mm:shared:cache",
            model_id="qwen3-vl-plus",
        )

    with pytest.raises(ValueError, match="must inherit the PQF context"):
        VLAProviderRequest(
            request_id="bad",
            owner_kind="character",
            owner_id="char_b",
            query_frame=frame,
            context_namespace="siming_mm:room_demo",
            cache_namespace=frame.cache_namespace,
            model_id="qwen3-vl-plus",
        )


def test_vla_result_must_remain_advisory_and_never_authority() -> None:
    result = VLAProviderResult(
        result_id="vla_result:1",
        request_id="vla_request:1",
        status=VLAProviderStatus.MOCK_PROVIDER_VERIFIED,
        provider_id="deterministic_mock",
        model_id="mock",
        model_version="1",
        advisory=True,
        findings=[{"finding_type": "visual_spatial_advisory", "advisory": True}],
        expires_at=10,
    )

    assert result.advisory is True
    assert result.writes_world_truth is False
    assert result.writes_esm_authority is False
    assert result.controls_actor is False
    with pytest.raises(ValueError, match="must remain advisory"):
        VLAProviderResult(
            result_id="bad",
            request_id="vla_request:1",
            status=VLAProviderStatus.MOCK_PROVIDER_VERIFIED,
            provider_id="deterministic_mock",
            model_id="mock",
            model_version="1",
            advisory=False,
        )


def test_vla_result_carries_capture_clock_and_can_be_late_advisory() -> None:
    frame = _frame()
    request = VLAProviderRequest.from_pqf(frame, owner_kind="character", owner_id="char_b", model_id="qwen3-vl-plus")
    result = VLAProviderResult(
        result_id="vla_result:late",
        request_id=request.request_id,
        status=VLAProviderStatus.TIMEOUT,
        capture_root_id=request.capture_root_id,
        capture_id=request.capture_id,
        clock_domain=request.clock_domain,
        monotonic_tick=request.monotonic_tick,
        source_frame_index=request.source_frame_index,
        capture_relation="late_advisory",
        provider_id="scheduler",
        model_id=request.model_id,
        model_version=request.model_version,
        advisory=True,
    )

    assert same_capture_tick(request, result)
    assert result.capture_relation == "late_advisory"
    assert result.advisory is True
    with pytest.raises(ValueError, match="must not write"):
        VLAProviderResult(
            result_id="bad",
            request_id="vla_request:1",
            status=VLAProviderStatus.MOCK_PROVIDER_VERIFIED,
            provider_id="deterministic_mock",
            model_id="mock",
            model_version="1",
            writes_world_truth=True,
        )
