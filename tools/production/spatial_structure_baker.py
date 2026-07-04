from __future__ import annotations

from .artifacts import ArtifactStatus, NonRuntimeProductionArtifact, ProductionArtifactKind


class SpatialStructureBaker:
    def bake(self, semantic_draft: NonRuntimeProductionArtifact) -> NonRuntimeProductionArtifact:
        if semantic_draft.artifact_kind != ProductionArtifactKind.SCENE_SEMANTIC_DRAFT.value:
            raise ValueError("SpatialStructureBaker requires a scene semantic draft artifact")
        if semantic_draft.status == ArtifactStatus.REJECTED.value:
            raise ValueError("rejected drafts cannot be baked")
        elements = []
        for candidate in semantic_draft.payload.get("semantic_candidates", []):
            if not isinstance(candidate, dict):
                continue
            tags = set(candidate.get("semantic_tags", []))
            elements.append(
                {
                    "element_id": candidate.get("element_id", ""),
                    "walkable": bool(tags.intersection({"zone", "navigation_lane", "playable_area"})),
                    "occludes": bool(tags.intersection({"occluder", "static_obstacle"})),
                    "affordance_hint": "inspect" if "interaction_object" in tags else "",
                    "source_refs": list(candidate.get("source_refs", [])),
                    "truth_status": "spatial_bake_draft_not_runtime_truth",
                }
            )
        return NonRuntimeProductionArtifact(
            artifact_id=f"nrpp:{semantic_draft.scene_id}:spatial-bake",
            artifact_kind=ProductionArtifactKind.SPATIAL_BAKE.value,
            scene_id=semantic_draft.scene_id,
            status=ArtifactStatus.DRAFT.value,
            source_refs=[semantic_draft.artifact_id, *semantic_draft.source_refs],
            payload={
                "spatial_elements": elements,
                "bake_strategy": "offline_scene_structure",
                "runtime_forbidden_work": ["write_world_truth", "full_scene_runtime_rescan"],
            },
            provenance={"module": "SpatialStructureBaker", "semantic_draft_ref": semantic_draft.artifact_id},
        )
