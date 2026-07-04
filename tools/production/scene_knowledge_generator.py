from __future__ import annotations

from .artifacts import ArtifactStatus, NonRuntimeProductionArtifact, ProductionArtifactKind


class SceneKnowledgeGenerator:
    def generate(
        self,
        *,
        semantic_draft: NonRuntimeProductionArtifact,
        spatial_bake: NonRuntimeProductionArtifact,
        classification: NonRuntimeProductionArtifact,
    ) -> NonRuntimeProductionArtifact:
        if any(artifact.status == ArtifactStatus.REJECTED.value for artifact in (semantic_draft, spatial_bake, classification)):
            raise ValueError("rejected artifacts cannot generate scene knowledge")
        spatial_by_id = {
            str(element.get("element_id")): element
            for element in spatial_bake.payload.get("spatial_elements", [])
            if isinstance(element, dict)
        }
        class_by_id = {
            str(entry.get("element_id")): entry
            for entry in classification.payload.get("classification_candidates", [])
            if isinstance(entry, dict)
        }
        annotations = []
        for candidate in semantic_draft.payload.get("semantic_candidates", []):
            if not isinstance(candidate, dict):
                continue
            element_id = str(candidate.get("element_id", ""))
            spatial = spatial_by_id.get(element_id, {})
            classified = class_by_id.get(element_id, {})
            affordances = []
            if spatial.get("affordance_hint"):
                affordances.append(spatial["affordance_hint"])
            if "interaction_object" in classified.get("candidate_labels", []):
                affordances.append("interact")
            annotations.append(
                {
                    "element_id": element_id,
                    "affordances": sorted(set(affordances)),
                    "navigation": {"walkable": bool(spatial.get("walkable")), "occludes": bool(spatial.get("occludes"))},
                    "source_refs": [semantic_draft.artifact_id, spatial_bake.artifact_id, classification.artifact_id],
                    "truth_status": "affordance_annotation_draft_not_runtime_truth",
                }
            )
        return NonRuntimeProductionArtifact(
            artifact_id=f"nrpp:{semantic_draft.scene_id}:affordance-annotation",
            artifact_kind=ProductionArtifactKind.AFFORDANCE_ANNOTATION.value,
            scene_id=semantic_draft.scene_id,
            status=ArtifactStatus.DRAFT.value,
            source_refs=[semantic_draft.artifact_id, spatial_bake.artifact_id, classification.artifact_id],
            payload={
                "affordance_annotations": annotations,
                "seed_use_requires_review_status": "approved",
                "truth_status": "draft_not_runtime_truth",
            },
            provenance={"module": "SceneKnowledgeGenerator"},
            model_readiness_status=classification.model_readiness_status,
        )
