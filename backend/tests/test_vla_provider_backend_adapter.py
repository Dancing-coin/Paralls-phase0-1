from __future__ import annotations

from app.world_runtime.intelligence_upgrade import PerceptionQueryFrame, SampleInputRef, SpatialReference, TimeWindow
from app.world_runtime.vla_model_registry import default_vla_model_registry
from app.world_runtime.vla_percept_bridge import vla_result_to_modality_result
from app.world_runtime.vla_provider import (
    DeterministicMockVLAProvider,
    HTTPVLAProviderAdapter,
    LocalVLAProviderAdapter,
    VLAProviderRequest,
    VLAProviderStatus,
)


def _request(with_artifacts: bool = True) -> VLAProviderRequest:
    frame = PerceptionQueryFrame(
        query_id="pqf:char_b:1",
        consumer_kind="character",
        subject_id="char_b",
        time_window=TimeWindow(started_at=0, ended_at=1),
        spatial_reference=SpatialReference(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus"),
        visual_inputs=[SampleInputRef(provider_kind="visual_patch", ref_id="runtime://artifact/visual.png")] if with_artifacts else [],
        structured_fact_refs=["raw_fact_event:visual_fact:1"],
        multimodal_context_id="character_mm:char_b",
        cache_namespace="character_mm:char_b:vla_cache",
    )
    return VLAProviderRequest.from_pqf(frame, owner_kind="character", owner_id="char_b", model_id="qwen3-vl-plus")


def test_mock_provider_returns_schema_valid_advisory_visual_spatial_result() -> None:
    result = DeterministicMockVLAProvider().interpret(_request())
    modality = vla_result_to_modality_result(result)

    assert result.status == VLAProviderStatus.MOCK_PROVIDER_VERIFIED
    assert result.advisory is True
    assert result.findings[0]["advisory"] is True
    assert modality.modality == "visual_spatial"
    assert modality.findings[0]["advisory"] is True


def test_provider_blocks_missing_artifacts_without_reading_godot_scene() -> None:
    result = DeterministicMockVLAProvider().interpret(_request(with_artifacts=False))

    assert result.status == VLAProviderStatus.BLOCKED_MISSING_ARTIFACTS
    assert result.missing_inputs == ["artifact_refs"]
    assert result.advisory is True


def test_http_and_local_adapters_report_missing_credentials_or_unverified_configuration() -> None:
    request = _request()
    missing = HTTPVLAProviderAdapter(endpoint="", api_key="", model_id="qwen3-vl-plus").interpret(request)
    configured = HTTPVLAProviderAdapter(endpoint="https://example.invalid/vla", api_key="redacted", model_id="qwen3-vl-plus").interpret(request)
    local = LocalVLAProviderAdapter(model_id="qwen3-vl-local", endpoint="local://qwen3-vl").interpret(request)

    assert missing.status == VLAProviderStatus.BLOCKED_MISSING_CREDENTIALS
    assert configured.status == VLAProviderStatus.CONFIGURED_UNVERIFIED
    assert local.status == VLAProviderStatus.CONFIGURED_UNVERIFIED


def test_model_registry_marks_qwen_seed_and_robotics_boundaries() -> None:
    registry = default_vla_model_registry()

    assert "qwen3-vl-plus" in registry
    assert "seed-vl-advisor" in registry
    assert "world_truth_write" in registry["qwen3-vl-plus"].forbidden_runtime_roles
    assert "actor_control" in registry["seed-vl-advisor"].forbidden_runtime_roles
    assert registry["openvla-action-head-research-only"].allowed_runtime_roles == []
    assert "robotics_action_head_runtime_control" in registry["openvla-action-head-research-only"].forbidden_runtime_roles
