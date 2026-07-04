from __future__ import annotations

import os
from typing import Any

from .artifacts import ArtifactStatus, NonRuntimeProductionArtifact, ProductionArtifactKind


class MultimodalSemanticClassifier:
    def classify(
        self,
        *,
        semantic_draft: NonRuntimeProductionArtifact,
        spatial_bake: NonRuntimeProductionArtifact,
        model_readiness_status: str | None = None,
        provider_findings: list[dict[str, Any]] | None = None,
    ) -> NonRuntimeProductionArtifact:
        if semantic_draft.status == ArtifactStatus.REJECTED.value or spatial_bake.status == ArtifactStatus.REJECTED.value:
            raise ValueError("rejected artifacts cannot be classified")
        readiness = model_readiness_status or production_model_readiness_status()
        findings = list(provider_findings or [])
        if readiness != "real_provider_verified" and findings:
            raise ValueError("provider findings require real_provider_verified readiness")
        labels = []
        for candidate in semantic_draft.payload.get("semantic_candidates", []):
            if not isinstance(candidate, dict):
                continue
            labels.append(
                {
                    "element_id": candidate.get("element_id", ""),
                    "candidate_labels": list(candidate.get("semantic_tags", [])),
                    "classification_source": "offline_structured_source",
                    "model_verified": False,
                }
            )
        labels.extend({**finding, "model_verified": True} for finding in findings)
        return NonRuntimeProductionArtifact(
            artifact_id=f"nrpp:{semantic_draft.scene_id}:multimodal-classification",
            artifact_kind=ProductionArtifactKind.MULTIMODAL_CLASSIFICATION.value,
            scene_id=semantic_draft.scene_id,
            status=ArtifactStatus.DRAFT.value,
            source_refs=[semantic_draft.artifact_id, spatial_bake.artifact_id],
            payload={
                "classification_status": "model_verified" if readiness == "real_provider_verified" else "model_not_verified",
                "model_readiness_status": readiness,
                "classification_candidates": labels,
                "truth_status": "classification_draft_not_runtime_truth",
                "mock_used_as_completion_evidence": False,
            },
            provenance={
                "module": "MultimodalSemanticClassifier",
                "semantic_draft_ref": semantic_draft.artifact_id,
                "spatial_bake_ref": spatial_bake.artifact_id,
                "model_provider_contract": "7.03 model-provider-readiness production_multimodal",
            },
            model_readiness_status=readiness,
        )


def production_model_readiness_status(env: dict[str, str] | None = None) -> str:
    values = dict(os.environ if env is None else env)
    mode = str(values.get("NON_RUNTIME_MODEL_MODE", "disabled") or "disabled").strip()
    if mode == "disabled":
        return "disabled"
    if mode == "blocked":
        return "blocked_missing_artifacts"
    if mode == "local":
        return "contract_ready"
    if mode == "http":
        if not str(values.get("NON_RUNTIME_MODEL_API_KEY", "")).strip():
            return "blocked_missing_credentials"
        if not str(values.get("NON_RUNTIME_MODEL_ENDPOINT", "")).strip():
            return "not_configured"
        if str(values.get("MODEL_PROVIDER_READINESS_REAL_SMOKE", "0")).strip() == "1":
            return "http_configured_unverified"
        return "http_configured_unverified"
    return "blocked_missing_artifacts"
