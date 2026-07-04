from __future__ import annotations

from app.world_runtime.intelligence_upgrade import CanonicalPerceptBundle
from app.world_runtime.vla_percept_bridge import (
    merge_vla_advisory_into_bundle,
    modality_result_to_cross_modal_result,
    vla_result_to_modality_result,
)
from app.world_runtime.vla_provider import VLAProviderResult, VLAProviderStatus


def _result() -> VLAProviderResult:
    return VLAProviderResult(
        result_id="vla_result:1",
        request_id="pqf:char_b:1",
        status=VLAProviderStatus.MOCK_PROVIDER_VERIFIED,
        provider_id="deterministic_mock",
        model_id="mock",
        model_version="1",
        findings=[{"finding_type": "visual_spatial_advisory", "summary": "target likely occluded", "advisory": True}],
        confidence=0.61,
        conflict_refs=["raw_fact_event:los_conflict:1"],
        missing_inputs=["depth_ref"],
        freshness="fresh",
        expires_at=10,
        trace_refs=["vla_request:1"],
    )


def test_vla_result_converts_to_visual_spatial_modality_result() -> None:
    modality = vla_result_to_modality_result(_result())

    assert modality.modality == "visual_spatial"
    assert modality.findings[0]["advisory"] is True
    assert modality.findings[0]["freshness"] == "fresh"
    assert modality.findings[0]["expires_at"] == 10
    assert modality.conflict_refs == ["raw_fact_event:los_conflict:1"]
    assert modality.missing_inputs == ["depth_ref"]


def test_modality_result_converts_to_cross_modal_understanding_without_authority() -> None:
    cross_modal = modality_result_to_cross_modal_result(vla_result_to_modality_result(_result()))

    assert cross_modal.world_hypotheses[0]["advisory"] is True
    assert cross_modal.confidence_adjustments["visual_spatial"] == 0.61
    assert cross_modal.modality_conflicts == ["raw_fact_event:los_conflict:1"]
    assert "vla_advisory_available" in cross_modal.attention_updates


def test_vla_advisory_merges_into_bundle_uncertainty_without_overwriting_l1_truth() -> None:
    bundle = CanonicalPerceptBundle(
        bundle_id="bundle:character:char_b:1",
        consumer_kind="character",
        subject_id="char_b",
        query_id="pqf:char_b:1",
        percept_context_id="character_mm:char_b",
        local_spatial_state={"passability": "passable", "source": "L1"},
        structured_fact_refs=["raw_fact_event:l1:1"],
        uncertainty={"occluded_fact_count": 0},
    )

    merged = merge_vla_advisory_into_bundle(bundle, _result())

    assert merged.local_spatial_state == bundle.local_spatial_state
    assert merged.structured_fact_refs == bundle.structured_fact_refs
    assert merged.uncertainty["vla_advisory"]["advisory"] is True
    assert merged.uncertainty["vla_advisory"]["conflict_refs"] == ["raw_fact_event:los_conflict:1"]
    assert merged.world_hypotheses[0]["hypothesis_type"] == "vla_visual_spatial_advisory"
