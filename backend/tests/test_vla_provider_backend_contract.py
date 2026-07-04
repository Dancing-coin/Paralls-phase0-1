from __future__ import annotations

import pytest

from app.world_runtime.intelligence_upgrade import PerceptionQueryFrame, SampleInputRef, SpatialReference, TimeWindow
from app.world_runtime.vla_provider import VLAProviderRequest, VLAProviderResult, VLAProviderStatus


def _frame(subject_id: str = "char_b") -> PerceptionQueryFrame:
    return PerceptionQueryFrame(
        query_id=f"pqf:{subject_id}:1",
        consumer_kind="character",
        subject_id=subject_id,
        time_window=TimeWindow(started_at=0, ended_at=1),
        spatial_reference=SpatialReference(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus"),
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
