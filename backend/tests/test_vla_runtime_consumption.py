from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.world_runtime.intelligence_upgrade import CanonicalPerceptBundle, PerceptionQueryFrame, SampleInputRef, SpatialReference, TimeWindow
from app.world_runtime.vla_percept_bridge import VLAAdvisoryCandidateAdapter, merge_vla_advisory_into_bundle
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


def _reviewed_adapter() -> tuple[VLAAdvisoryCandidateAdapter, VLAProviderRequest]:
    frame = PerceptionQueryFrame(
        query_id="pqf:archive-door:1",
        consumer_kind="character",
        subject_id="char_b",
        target_ref="obj_archive_door",
        time_window=TimeWindow(started_at=0, ended_at=1),
        spatial_reference=SpatialReference(room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus"),
        visual_inputs=[SampleInputRef(provider_kind="visual_patch", ref_id="runtime://archive-door.png")],
        grounding_entity_refs=["obj_archive_door"],
        grounding_affordance_refs=["affordance:archive-door:open-close"],
        multimodal_context_id="character_mm:char_b",
        cache_namespace="character_mm:char_b:vla_cache",
    )
    request = VLAProviderRequest.from_pqf(frame, owner_kind="character", owner_id="char_b", model_id="mock")
    record = SimpleNamespace(
        entity_ref="obj_archive_door",
        affordances=[SimpleNamespace(
            affordance_id="affordance:archive-door:open-close",
            action_semantic="open_close",
            preconditions=["door_closed"],
        )],
    )
    registry = SimpleNamespace(resolve=lambda **_: SimpleNamespace(status="available", record=record))
    return VLAAdvisoryCandidateAdapter(
        request=request,
        registry=registry,
        scene_instance_id="scene_instance:main:1",
        binding_revision=1,
        required_anchor_roles=["contact"],
    ), request


def _door_result(request: VLAProviderRequest, *, freshness: str = "fresh") -> VLAProviderResult:
    return VLAProviderResult(
        result_id="vla_result:archive-door",
        request_id=request.request_id,
        status=VLAProviderStatus.MOCK_PROVIDER_VERIFIED,
        subject_ref=request.subject_ref,
        target_ref="obj_archive_door",
        world_anchor_id=request.world_anchor_id,
        source_ref_lineage=list(request.source_ref_lineage),
        capture_root_id=request.capture_root_id,
        capture_id=request.capture_id,
        clock_domain=request.clock_domain,
        monotonic_tick=request.monotonic_tick,
        source_frame_index=request.source_frame_index,
        provider_id="mock",
        model_id="mock",
        model_version="1",
        findings=[{
            "affordance_id": "affordance:archive-door:open-close",
            "target_ref": "obj_archive_door",
            "expected_observation": {"observed_state": "open"},
        }],
        confidence=0.8,
        freshness=freshness,
        expires_at=2,
    )


def test_vla_candidate_becomes_intent_candidate_not_motor_command() -> None:
    adapter, request = _reviewed_adapter()

    candidate = adapter.to_candidate_action(_door_result(request))

    assert candidate.semantic_action_id == "open_close"
    assert candidate.target_ref == "obj_archive_door"
    assert "velocity" not in candidate.model_dump()
    assert "global_position" not in candidate.model_dump()


def test_vla_candidate_rejects_stale_capture_before_intent_admission() -> None:
    adapter, request = _reviewed_adapter()

    with pytest.raises(ValueError, match="stale"):
        adapter.to_candidate_action(_door_result(request, freshness="stale"))


def test_vla_candidate_rejects_identity_envelope_mismatch() -> None:
    adapter, request = _reviewed_adapter()
    with pytest.raises(ValueError, match="world_anchor_id"):
        adapter.to_candidate_action(_door_result(request).model_copy(update={"world_anchor_id": "world_anchor:other"}))
    with pytest.raises(ValueError, match="source_ref_lineage"):
        adapter.to_candidate_action(_door_result(request).model_copy(update={"source_ref_lineage": ["lineage:other"]}))
    with pytest.raises(ValueError, match="source_frame_index"):
        adapter.to_candidate_action(_door_result(request).model_copy(update={"source_frame_index": 99}))


def test_http_provider_candidate_refs_normalize_to_reviewed_action_candidate() -> None:
    adapter, request = _reviewed_adapter()
    result = _door_result(request).model_copy(update={
        "findings": [{
            "summary": "candidate door affordance",
            "candidate_entity_refs": ["obj_archive_door"],
            "candidate_affordance_refs": ["affordance:archive-door:open-close"],
            "uncertainty": "",
            "evidence_artifact_refs": ["runtime://archive-door.png"],
        }]
    })
    candidate = adapter.to_candidate_action(result)
    assert candidate.target_ref == "obj_archive_door"
    assert candidate.reviewed_action_ref == "affordance:archive-door:open-close"
    assert candidate.semantic_action_id == "open_close"
