from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ProductionPipelineModuleManifest:
    module_name: str
    input_contracts: list[str]
    output_contracts: list[str]
    reads_runtime_private_context: bool = False
    writes_world_truth: bool = False
    allowed_context_namespace: str = "tool_mm:production_scene_knowledge"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def default_production_pipeline_manifest() -> list[ProductionPipelineModuleManifest]:
    return [
        ProductionPipelineModuleManifest(
            module_name="SceneSemanticExtractor",
            input_contracts=["offline_scene_manifest", "asset_metadata_refs"],
            output_contracts=["scene_semantic_draft"],
        ),
        ProductionPipelineModuleManifest(
            module_name="SpatialStructureBaker",
            input_contracts=["scene_semantic_draft"],
            output_contracts=["spatial_bake"],
        ),
        ProductionPipelineModuleManifest(
            module_name="MultimodalSemanticClassifier",
            input_contracts=["scene_semantic_draft", "spatial_bake", "model-provider-readiness.production_multimodal"],
            output_contracts=["multimodal_classification"],
        ),
        ProductionPipelineModuleManifest(
            module_name="SceneKnowledgeGenerator",
            input_contracts=["scene_semantic_draft", "spatial_bake", "multimodal_classification"],
            output_contracts=["affordance_annotation"],
        ),
        ProductionPipelineModuleManifest(
            module_name="ReviewWorkbench",
            input_contracts=["draft_artifact"],
            output_contracts=["review_report", "approved_seed_artifact", "rejected_artifact"],
        ),
        ProductionPipelineModuleManifest(
            module_name="DatasetAndReplayBuilder",
            input_contracts=["approved_artifact", "approved_verification_artifact"],
            output_contracts=["replay_dataset"],
        ),
    ]
