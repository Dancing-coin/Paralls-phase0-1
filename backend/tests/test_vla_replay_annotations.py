from __future__ import annotations

from pathlib import Path

from scripts.verification.vla_replay_annotations import coverage_status, load_annotation_manifest, validate_annotation_manifest


def test_bootstrap_manifest_is_valid_but_not_ready_for_semantic_scoring() -> None:
    root = Path(__file__).resolve().parents[2]
    manifest = load_annotation_manifest(root / "docs/verification/vla-advisory-replay-annotation-manifest.json")

    assert validate_annotation_manifest(manifest) == []
    coverage = coverage_status(manifest)
    assert coverage["status"] == "bootstrap_valid_not_coverage_ready"
    assert coverage["semantic_scoring_ready"] is False
    assert coverage["scene_count"] == 2


def test_annotation_manifest_rejects_prompt_context_as_scoring_credit() -> None:
    manifest = {
        "schema_version": "vla-advisory-replay-annotations.v1",
        "samples": [
            {
                "sample_id": "one",
                "scene_asset": "res://scene.tscn",
                "room_id": "room",
                "scene_id": "scene",
                "zone_id": "zone",
                "capture_source": "godot_runtime_capture",
                "visible_scene_truth": {"visual_markers": []},
                "advisory_grounding": {"entity_refs": [], "collider_refs": [], "anchor_refs": [], "affordance_refs": []},
                "score_policy": {"semantic_scoring": "manual_review_required", "must_not_award_credit_for": []},
            }
        ],
    }

    assert "sample_0_must_exclude_prompt_context_credit" in validate_annotation_manifest(manifest)
