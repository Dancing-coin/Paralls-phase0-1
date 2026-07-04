from __future__ import annotations

from app.world_runtime.intelligence_upgrade import CanonicalPerceptBundle, PerceptionQueryFrame, SampleInputRef, SpatialReference, TimeWindow
from app.world_runtime.vla_percept_bridge import merge_vla_advisory_into_bundle
from app.world_runtime.vla_provider import DeterministicMockVLAProvider, VLAProviderRequest, VLAProviderResult, VLAProviderStatus


def _frame(owner_kind: str, subject_id: str, context: str) -> PerceptionQueryFrame:
    return PerceptionQueryFrame(
        query_id=f"pqf:{subject_id}:1",
        consumer_kind=owner_kind,
        subject_id=subject_id,
        time_window=TimeWindow(started_at=0, ended_at=1),
        spatial_reference=SpatialReference(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus"),
        visual_inputs=[SampleInputRef(provider_kind="visual_patch", ref_id=f"runtime://artifact/{subject_id}-visual.png")],
        structured_fact_refs=["raw_fact_event:l1:1"],
        multimodal_context_id=context,
        cache_namespace=f"{context}:vla_cache",
    )


def _bundle(owner_kind: str, subject_id: str, context: str) -> CanonicalPerceptBundle:
    return CanonicalPerceptBundle(
        bundle_id=f"bundle:{owner_kind}:{subject_id}:1",
        consumer_kind=owner_kind,
        subject_id=subject_id,
        query_id=f"pqf:{subject_id}:1",
        percept_context_id=context,
        local_spatial_state={"source": "L1", "passability": "passable"},
        target_state={"target_object_ids": ["obj_letter"]},
        structured_fact_refs=["raw_fact_event:l1:1"],
    )


def test_disabled_vla_path_preserves_existing_structured_bundle() -> None:
    bundle = _bundle("character", "char_b", "character_mm:char_b")
    disabled_result = VLAProviderResult(
        result_id="vla_result:disabled",
        request_id=bundle.query_id,
        status=VLAProviderStatus.DISABLED,
        provider_id="disabled",
        model_id="none",
        model_version="none",
        findings=[],
        expires_at=1,
        fallback_reason="disabled_use_structured_facts",
    )
    merged = merge_vla_advisory_into_bundle(bundle, disabled_result)

    assert merged.local_spatial_state == bundle.local_spatial_state
    assert merged.target_state == bundle.target_state
    assert merged.uncertainty["vla_advisory"]["status"] == "disabled"


def test_character_and_siming_consume_only_their_private_vla_contexts() -> None:
    char_frame = _frame("character", "char_b", "character_mm:char_b")
    siming_frame = _frame("siming", "siming", "siming_mm:room_demo")
    char_request = VLAProviderRequest.from_pqf(char_frame, owner_kind="character", owner_id="char_b", model_id="qwen3-vl-plus")
    siming_request = VLAProviderRequest.from_pqf(siming_frame, owner_kind="siming", owner_id="siming", model_id="qwen3-vl-plus")
    provider = DeterministicMockVLAProvider()

    char_bundle = merge_vla_advisory_into_bundle(_bundle("character", "char_b", "character_mm:char_b"), provider.interpret(char_request))
    siming_bundle = merge_vla_advisory_into_bundle(_bundle("siming", "siming", "siming_mm:room_demo"), provider.interpret(siming_request))

    assert char_bundle.percept_context_id.startswith("character_mm:")
    assert siming_bundle.percept_context_id.startswith("siming_mm:")
    assert char_request.cache_namespace != siming_request.cache_namespace
    assert char_bundle.uncertainty["vla_advisory"]["advisory"] is True
    assert siming_bundle.uncertainty["vla_advisory"]["advisory"] is True


def test_vla_runtime_consumption_never_writes_world_truth_or_esm_or_actor_control() -> None:
    request = VLAProviderRequest.from_pqf(
        _frame("character", "char_b", "character_mm:char_b"),
        owner_kind="character",
        owner_id="char_b",
        model_id="qwen3-vl-plus",
    )
    result = DeterministicMockVLAProvider().interpret(request)
    bundle = merge_vla_advisory_into_bundle(_bundle("character", "char_b", "character_mm:char_b"), result)

    assert result.writes_world_truth is False
    assert result.writes_esm_authority is False
    assert result.controls_actor is False
    assert bundle.local_spatial_state["source"] == "L1"
    assert "settlement" not in bundle.uncertainty["vla_advisory"]
    assert "actor_control" not in bundle.uncertainty["vla_advisory"]
