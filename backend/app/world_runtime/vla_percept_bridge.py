from __future__ import annotations

from app.world_runtime.intelligence_upgrade import (
    CanonicalPerceptBundle,
    CrossModalUnderstandingResult,
    ModalityInterpretationResult,
)
from app.world_runtime.vla_provider import VLAProviderResult
from app.world_runtime.vla_provider import VLAProviderRequest
from app.services.scene_affordance_registry import SceneAffordanceRegistry
from app.character_agent.models.embodied_episode import (
    CandidateActionObservation,
    forbidden_candidate_field,
)


class VLAAdvisoryCandidateAdapter:
    """Admit a VLA nomination only through reviewed scene affordances.

    The adapter produces a semantic candidate for ordinary actor-intent
    admission.  It deliberately cannot return motor, authority, or Godot data.
    """

    def __init__(
        self,
        *,
        request: VLAProviderRequest,
        registry: SceneAffordanceRegistry,
        scene_instance_id: str,
        binding_revision: int,
        required_anchor_roles: list[str],
    ) -> None:
        self._request = request
        self._registry = registry
        self._scene_instance_id = scene_instance_id
        self._binding_revision = binding_revision
        self._required_anchor_roles = list(required_anchor_roles)

    def to_candidate_action(self, result: VLAProviderResult) -> CandidateActionObservation:
        if not result.advisory or result.writes_world_truth or result.writes_esm_authority or result.controls_actor:
            raise ValueError("VLA candidate input must remain advisory-only")
        if result.request_id != self._request.request_id:
            raise ValueError("VLA candidate request provenance is scope-mismatched")
        self._validate_capture_provenance(result)
        finding = self._candidate_finding(result)
        forbidden = forbidden_candidate_field(finding)
        if forbidden:
            raise ValueError(f"VLA candidate contains forbidden control/world field: {forbidden}")
        target_ref = str(finding.get("target_ref", "") or result.target_ref or "")
        affordance_ref = str(finding.get("affordance_id", "") or "")
        if not target_ref or target_ref not in self._request.grounding_entity_refs:
            raise ValueError("VLA candidate target is not in the reviewed grounding catalog")
        if affordance_ref == "" or affordance_ref not in self._request.grounding_affordance_refs:
            raise ValueError("VLA candidate affordance is not in the reviewed grounding catalog")
        if result.target_ref and result.target_ref != target_ref:
            raise ValueError("VLA candidate target does not match result provenance")
        resolved = self._registry.resolve(
            scene_id=self._request.query_frame.spatial_reference.scene_id,
            scene_instance_id=self._scene_instance_id,
            entity_ref=target_ref,
            affordance_id=affordance_ref,
            expected_binding_revision=self._binding_revision,
            required_anchor_roles=self._required_anchor_roles,
            view="public",
        )
        if resolved.status != "available" or resolved.record is None:
            raise ValueError(f"VLA candidate target/affordance is not reviewed: {resolved.status}")
        affordance = next(
            (item for item in resolved.record.affordances if item.affordance_id == affordance_ref),
            None,
        )
        if affordance is None:
            raise ValueError("VLA candidate affordance is not reviewed")
        expected = finding.get("expected_observation", {})
        if not isinstance(expected, dict):
            raise ValueError("VLA candidate expected observation must be an object")
        evidence_refs = [
            result.result_id, self._request.request_id, result.capture_root_id,
            result.capture_id, *result.trace_refs,
        ]
        return CandidateActionObservation(
            candidate_id=f"candidate:{result.result_id}:{target_ref}:{affordance_ref}",
            target_ref=target_ref,
            semantic_action_id=affordance.action_semantic,
            reviewed_target_ref=resolved.record.entity_ref,
            reviewed_action_ref=affordance.affordance_id,
            preconditions=tuple(affordance.preconditions),
            expected_observation=expected,
            confidence=result.confidence,
            uncertainty={
                "provider_advisory": True,
                "freshness": result.freshness,
                "conflict_refs": list(result.conflict_refs),
                "missing_inputs": list(result.missing_inputs),
                "candidate_interpretation": str(finding.get("summary", "")),
            },
            evidence_refs=tuple(ref for ref in evidence_refs if ref),
            reobserve_required=bool(result.conflict_refs or result.missing_inputs),
        )

    def _validate_capture_provenance(self, result: VLAProviderResult) -> None:
        if result.capture_relation != "same_capture_tick" or result.freshness in {"stale", "expired"}:
            raise ValueError("VLA candidate capture provenance is stale")
        for name in ("capture_root_id", "capture_id", "clock_domain", "monotonic_tick"):
            expected = getattr(self._request, name)
            actual = getattr(result, name)
            if expected is not None and actual != expected:
                raise ValueError(f"VLA candidate {name} provenance is scope-mismatched")

    @staticmethod
    def _candidate_finding(result: VLAProviderResult) -> dict[str, object]:
        candidates = [
            dict(finding) for finding in result.findings
            if isinstance(finding, dict) and (finding.get("affordance_id") or finding.get("semantic_action_id"))
        ]
        if len(candidates) != 1:
            raise ValueError("VLA result must nominate exactly one reviewed candidate")
        return candidates[0]


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
                "subject_ref": result.subject_ref,
                "target_ref": result.target_ref,
                "world_anchor_id": result.world_anchor_id,
                "source_ref_lineage": result.source_ref_lineage,
                "capture_root_id": result.capture_root_id,
                "capture_id": result.capture_id,
                "clock_domain": result.clock_domain,
                "monotonic_tick": result.monotonic_tick,
                "source_frame_index": result.source_frame_index,
                "capture_relation": result.capture_relation,
                "advisory_route": result.advisory_route.value,
                "route_reason": result.route_reason,
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
        "advisory_route": result.advisory_route.value,
        "route_reason": result.route_reason,
        "escalation_from_request_id": result.escalation_from_request_id,
        "advisory": True,
        "subject_ref": result.subject_ref,
        "target_ref": result.target_ref,
        "world_anchor_id": result.world_anchor_id,
        "source_ref_lineage": result.source_ref_lineage,
        "capture_root_id": result.capture_root_id,
        "capture_id": result.capture_id,
        "clock_domain": result.clock_domain,
        "monotonic_tick": result.monotonic_tick,
        "source_frame_index": result.source_frame_index,
        "capture_relation": result.capture_relation,
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
