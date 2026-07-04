from __future__ import annotations

from app.world_runtime.intelligence_upgrade import (
    CanonicalPerceptBundle,
    CrossModalUnderstandingResult,
    ModalityInterpretationResult,
)
from app.world_runtime.vla_provider import VLAProviderResult


def vla_result_to_modality_result(result: VLAProviderResult) -> ModalityInterpretationResult:
    return ModalityInterpretationResult(
        result_id=f"modality:{result.result_id}",
        query_id=result.request_id,
        modality="visual_spatial",
        findings=[
            {
                **finding,
                "advisory": True,
                "source_result_id": result.result_id,
                "freshness": result.freshness,
                "expires_at": result.expires_at,
            }
            for finding in result.findings
        ],
        confidence=result.confidence,
        missing_inputs=list(result.missing_inputs),
        conflict_refs=list(result.conflict_refs),
    )


def modality_result_to_cross_modal_result(
    modality: ModalityInterpretationResult,
    *,
    missing_modalities: list[str] | None = None,
) -> CrossModalUnderstandingResult:
    return CrossModalUnderstandingResult(
        result_id=f"cross_modal:{modality.result_id}",
        query_id=modality.query_id,
        world_hypotheses=[
            {
                "hypothesis_type": "vla_visual_spatial_advisory",
                "findings": modality.findings,
                "advisory": True,
            }
        ],
        confidence_adjustments={"visual_spatial": modality.confidence},
        modality_conflicts=list(modality.conflict_refs),
        missing_modalities=missing_modalities or [],
        attention_updates=["vla_advisory_available"] if modality.findings else [],
    )


def merge_vla_advisory_into_bundle(
    bundle: CanonicalPerceptBundle,
    result: VLAProviderResult,
) -> CanonicalPerceptBundle:
    modality = vla_result_to_modality_result(result)
    cross_modal = modality_result_to_cross_modal_result(modality)
    advisory_state = {
        "vla_result_id": result.result_id,
        "status": result.status.value,
        "advisory": True,
        "findings": modality.findings,
        "confidence": result.confidence,
        "conflict_refs": result.conflict_refs,
        "missing_inputs": result.missing_inputs,
        "freshness": result.freshness,
        "expires_at": result.expires_at,
        "trace_refs": result.trace_refs,
    }
    uncertainty = dict(bundle.uncertainty)
    uncertainty["vla_advisory"] = advisory_state
    return bundle.model_copy(
        update={
            "world_hypotheses": [*bundle.world_hypotheses, *cross_modal.world_hypotheses],
            "uncertainty": uncertainty,
        }
    )
