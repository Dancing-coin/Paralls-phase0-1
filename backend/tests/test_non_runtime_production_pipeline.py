from __future__ import annotations

from pathlib import Path

import pytest

from app.world_runtime.intelligence_upgrade import default_non_runtime_tooling_manifest
from tools.production import (
    ArtifactStatus,
    DatasetAndReplayBuilder,
    MultimodalSemanticClassifier,
    ReviewWorkbench,
    SceneKnowledgeGenerator,
    SceneSemanticExtractor,
    SpatialStructureBaker,
    default_production_pipeline_manifest,
)


def _source_scene() -> dict[str, object]:
    return {
        "scene_id": "scene_demo",
        "nodes": [
            {
                "name": "ZoneFocus",
                "node_path": "/root/MainDemo/ZoneFocus",
                "groups": ["l1_zone", "production_playable_area"],
                "metadata": {"zone_id": "zone_focus", "semantic_tags": ["playable_area"]},
                "navigation_region_ref": "godot_scene://MainDemo/NavigationRegion3D",
            },
            {
                "name": "Letter",
                "node_path": "/root/MainDemo/Letter",
                "groups": ["l1_interaction_object"],
                "metadata": {"element_id": "obj_letter"},
                "collision_shape_ref": "godot_scene://MainDemo/Letter/CollisionShape3D",
            },
            {
                "name": "StaticCover",
                "node_path": "/root/MainDemo/StaticCover",
                "groups": ["l1_occluder"],
                "metadata": {"element_id": "cover_1"},
                "collision_shape_ref": "godot_scene://MainDemo/StaticCover/CollisionShape3D",
            },
        ],
    }


def _build_pipeline_artifacts(model_status: str = "blocked_missing_credentials"):
    semantic = SceneSemanticExtractor().extract(
        scene_id="scene_demo",
        source_scene=_source_scene(),
        source_ref="godot_scene://scenes/phase0/MainDemo.tscn",
    )
    spatial = SpatialStructureBaker().bake(semantic)
    classification = MultimodalSemanticClassifier().classify(
        semantic_draft=semantic,
        spatial_bake=spatial,
        model_readiness_status=model_status,
    )
    affordance = SceneKnowledgeGenerator().generate(
        semantic_draft=semantic,
        spatial_bake=spatial,
        classification=classification,
    )
    return semantic, spatial, classification, affordance


def test_pipeline_manifest_registers_six_non_runtime_modules_without_runtime_authority() -> None:
    manifest = default_production_pipeline_manifest()
    modules = {entry.module_name for entry in manifest}

    assert modules == {
        "SceneSemanticExtractor",
        "SpatialStructureBaker",
        "MultimodalSemanticClassifier",
        "SceneKnowledgeGenerator",
        "ReviewWorkbench",
        "DatasetAndReplayBuilder",
    }
    assert all(entry.reads_runtime_private_context is False for entry in manifest)
    assert all(entry.writes_world_truth is False for entry in manifest)
    assert all(entry.allowed_context_namespace.startswith("tool_mm:") for entry in manifest)


def test_existing_non_runtime_manifest_includes_full_production_chain() -> None:
    manifests = default_non_runtime_tooling_manifest()
    production_modules = {
        module
        for manifest in manifests
        if manifest.stack_kind == "production"
        for module in manifest.modules
    }

    assert {
        "SceneSemanticExtractor",
        "SpatialStructureBaker",
        "MultimodalSemanticClassifier",
        "SceneKnowledgeGenerator",
        "ReviewWorkbench",
        "DatasetAndReplayBuilder",
    }.issubset(production_modules)


def test_pipeline_rejects_runtime_private_context_inputs() -> None:
    source = _source_scene()
    source["character_private_context"] = {"memory": "must-not-enter-production"}

    with pytest.raises(ValueError, match="runtime private context"):
        SceneSemanticExtractor().extract(
            scene_id="scene_demo",
            source_scene=source,
            source_ref="godot_scene://scenes/phase0/MainDemo.tscn",
        )


def test_artifact_contracts_and_model_status_stay_draft_until_review() -> None:
    semantic, spatial, classification, affordance = _build_pipeline_artifacts()

    assert semantic.status == "draft"
    assert spatial.artifact_kind == "spatial_bake"
    assert classification.artifact_kind == "multimodal_classification"
    assert classification.payload["model_readiness_status"] == "blocked_missing_credentials"
    assert classification.payload["mock_used_as_completion_evidence"] is False
    assert affordance.artifact_kind == "affordance_annotation"
    assert all(not artifact.writes_world_truth for artifact in [semantic, spatial, classification, affordance])
    assert all(not artifact.eligible_l1_seed for artifact in [semantic, spatial, classification, affordance])


def test_review_gate_tracks_review_approved_rejected_and_writes_evidence(tmp_path: Path) -> None:
    _, _, _, affordance = _build_pipeline_artifacts()
    workbench = ReviewWorkbench(tmp_path)

    in_review, review_report = workbench.submit_for_review(
        affordance,
        reviewer="production-reviewer",
        reason="scene affordance candidates are ready for human review",
    )
    approved, approval_report = workbench.approve(
        in_review,
        reviewer="production-reviewer",
        reason="source refs and affordances match scene contract",
    )
    rejected, rejection_report = workbench.reject(
        affordance,
        reviewer="production-reviewer",
        reason="negative control rejected draft",
    )

    assert in_review.status == ArtifactStatus.REVIEW.value
    assert approved.status == ArtifactStatus.APPROVED.value
    assert approved.eligible_l1_seed is True
    assert approved.eligible_verification_seed is True
    assert rejected.status == ArtifactStatus.REJECTED.value
    assert rejected.eligible_l1_seed is False
    assert rejected.eligible_verification_seed is False
    assert review_report.payload["reviewer"] == "production-reviewer"
    assert approval_report.payload["status"] == "approved"
    assert rejection_report.payload["status"] == "rejected"
    assert (tmp_path / "non-runtime-production-review-evidence.jsonl").exists()


def test_approved_artifact_can_be_consumed_as_l1_seed_or_verification_dataset(tmp_path: Path) -> None:
    _, _, _, affordance = _build_pipeline_artifacts()
    workbench = ReviewWorkbench(tmp_path)
    reviewed, _ = workbench.submit_for_review(affordance, reviewer="reviewer", reason="ready")
    approved, _ = workbench.approve(reviewed, reviewer="reviewer", reason="approved")

    l1_seed = workbench.export_l1_seed(approved)
    dataset = DatasetAndReplayBuilder().build(
        dataset_id="scene-demo-smoke",
        artifacts=[approved],
        scene_id="scene_demo",
    )

    assert l1_seed["runtime_truth_status"] == "reviewed_seed_only"
    assert l1_seed["writes_world_truth"] is False
    assert dataset.status == "approved"
    assert dataset.payload["retention"] == "verification_replay_dataset"
    assert dataset.payload["entries"][0]["artifact_id"] == approved.artifact_id


def test_rejected_draft_never_enters_l1_seed_or_replay_dataset(tmp_path: Path) -> None:
    _, _, _, affordance = _build_pipeline_artifacts()
    workbench = ReviewWorkbench(tmp_path)
    reviewed, _ = workbench.submit_for_review(affordance, reviewer="reviewer", reason="ready")
    rejected, _ = workbench.reject(reviewed, reviewer="reviewer", reason="bad source ref")

    with pytest.raises(ValueError, match="approved artifacts"):
        workbench.export_l1_seed(rejected)
    with pytest.raises(ValueError, match="approved artifacts"):
        DatasetAndReplayBuilder().build(dataset_id="bad", artifacts=[rejected], scene_id="scene_demo")
