from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "vla-advisory-replay-annotations.v1"
MINIMUM_SAMPLE_COUNT = 20
MINIMUM_SCENE_COUNT = 2
REQUIRED_SAMPLE_KEYS = {
    "sample_id",
    "scene_asset",
    "room_id",
    "scene_id",
    "zone_id",
    "subject_id",
    "target_ref",
    "capture_source",
    "runtime_capture",
    "visible_scene_truth",
    "advisory_grounding",
    "score_policy",
}


def load_annotation_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def validate_annotation_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append("invalid_schema_version")
    samples = manifest.get("samples")
    if not isinstance(samples, list) or not samples:
        return [*errors, "missing_samples"]
    sample_ids: set[str] = set()
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            errors.append(f"sample_{index}_not_object")
            continue
        missing = REQUIRED_SAMPLE_KEYS.difference(sample)
        if missing:
            errors.append(f"sample_{index}_missing_{','.join(sorted(missing))}")
        sample_id = str(sample.get("sample_id", ""))
        if not sample_id or sample_id in sample_ids:
            errors.append(f"sample_{index}_invalid_or_duplicate_id")
        sample_ids.add(sample_id)
        if sample.get("capture_source") != "godot_runtime_capture":
            errors.append(f"sample_{index}_capture_source_must_be_godot_runtime_capture")
        visible_truth = sample.get("visible_scene_truth")
        grounding = sample.get("advisory_grounding")
        policy = sample.get("score_policy")
        runtime_capture = sample.get("runtime_capture")
        if not isinstance(visible_truth, dict) or not isinstance(visible_truth.get("visual_markers"), list):
            errors.append(f"sample_{index}_invalid_visible_scene_truth")
        if not isinstance(grounding, dict) or not all(
            isinstance(grounding.get(key), list) and all(isinstance(ref, str) and ref for ref in grounding[key])
            for key in ("entity_refs", "collider_refs", "anchor_refs", "affordance_refs")
        ):
            errors.append(f"sample_{index}_invalid_advisory_grounding")
        if not isinstance(runtime_capture, dict) or not all(
            isinstance(runtime_capture.get(key), str) and runtime_capture.get(key)
            for key in ("report_path", "capture_path", "expected_status")
        ):
            errors.append(f"sample_{index}_invalid_runtime_capture")
        if not isinstance(policy, dict) or policy.get("semantic_scoring") != "manual_review_required":
            errors.append(f"sample_{index}_semantic_scoring_must_require_manual_review")
        forbidden_credit = policy.get("must_not_award_credit_for") if isinstance(policy, dict) else None
        if not isinstance(forbidden_credit, list) or not {"pqf_subject_id", "advisory_grounding_catalog"}.issubset(forbidden_credit):
            errors.append(f"sample_{index}_must_exclude_prompt_context_credit")
    return errors


def coverage_status(manifest: dict[str, Any]) -> dict[str, object]:
    samples = manifest.get("samples") if isinstance(manifest.get("samples"), list) else []
    scenes = {str(sample.get("scene_asset", "")) for sample in samples if isinstance(sample, dict) and sample.get("scene_asset")}
    return {
        "sample_count": len(samples),
        "scene_count": len(scenes),
        "minimum_sample_count": MINIMUM_SAMPLE_COUNT,
        "minimum_scene_count": MINIMUM_SCENE_COUNT,
        "semantic_scoring_ready": len(samples) >= MINIMUM_SAMPLE_COUNT and len(scenes) >= MINIMUM_SCENE_COUNT,
        "status": (
            "annotation_coverage_ready"
            if len(samples) >= MINIMUM_SAMPLE_COUNT and len(scenes) >= MINIMUM_SCENE_COUNT
            else "bootstrap_valid_not_coverage_ready"
        ),
    }
