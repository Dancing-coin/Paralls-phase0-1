from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.world_runtime.model_provider_readiness import build_model_provider_readiness_report  # noqa: E402
from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown  # noqa: E402
from tools.production import (  # noqa: E402
    DatasetAndReplayBuilder,
    MultimodalSemanticClassifier,
    ReviewWorkbench,
    SceneKnowledgeGenerator,
    SceneSemanticExtractor,
    SpatialStructureBaker,
    default_production_pipeline_manifest,
)


ALLOWED_EXTERNAL_MODEL_STATUSES = {
    "disabled",
    "contract_ready",
    "http_configured_unverified",
    "real_provider_verified",
    "blocked_missing_artifacts",
    "blocked_missing_credentials",
    "blocked_model_unavailable",
}


def _result(result_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def _sample_scene() -> dict[str, object]:
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


def _production_model_status() -> str:
    report = build_model_provider_readiness_report()
    for row in report.rows:
        if row.provider_kind == "production_multimodal":
            return row.readiness_status
    return "blocked_missing_artifacts"


def _run_pipeline(log_dir: Path, model_status: str) -> dict[str, object]:
    artifact_dir = log_dir / "non-runtime-production-pipeline-artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    semantic = SceneSemanticExtractor().extract(
        scene_id="scene_demo",
        source_scene=_sample_scene(),
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

    workbench = ReviewWorkbench(log_dir)
    review_artifact, review_report = workbench.submit_for_review(
        affordance,
        reviewer="verification-reviewer",
        reason="focused harness review gate smoke",
    )
    approved, approval_report = workbench.approve(
        review_artifact,
        reviewer="verification-reviewer",
        reason="approved as reviewed seed and replay dataset input",
    )
    rejected, rejection_report = workbench.reject(
        affordance,
        reviewer="verification-reviewer",
        reason="negative control rejected draft",
    )
    l1_seed = workbench.export_l1_seed(approved)
    dataset = DatasetAndReplayBuilder().build(
        dataset_id="scene-demo-verification",
        artifacts=[approved],
        scene_id="scene_demo",
    )

    artifacts = [semantic, spatial, classification, affordance, review_artifact, approved, rejected, dataset]
    artifact_paths = []
    for index, artifact in enumerate(artifacts):
        path = artifact_dir / f"{index:02d}_{artifact.status}_{artifact.artifact_id.replace(':', '_')}.json"
        artifact.write_json(path)
        artifact_paths.append(str(path))
    l1_seed_path = artifact_dir / "approved-l1-seed.json"
    l1_seed_path.write_text(json.dumps(l1_seed, ensure_ascii=False, indent=2), encoding="utf-8")
    dataset_path = artifact_dir / "approved-replay-dataset.json"
    dataset.write_json(dataset_path)

    rejected_blocked = False
    try:
        workbench.export_l1_seed(rejected)
    except ValueError:
        rejected_blocked = True

    return {
        "manifest_modules": [entry.to_dict() for entry in default_production_pipeline_manifest()],
        "artifact_paths": artifact_paths,
        "review_report_refs": [review_report.artifact_id, approval_report.artifact_id, rejection_report.artifact_id],
        "approved_artifact": approved.to_dict(),
        "rejected_artifact": rejected.to_dict(),
        "l1_seed_path": str(l1_seed_path),
        "dataset_path": str(dataset_path),
        "dataset": dataset.to_dict(),
        "rejected_blocked_from_l1_seed": rejected_blocked,
        "model_status": model_status,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    pytest_log = log_dir / "non-runtime-production-pipeline-pytest.log"
    pytest_result = run_command(
        [python_exe, "-m", "pytest", "-q", "backend/tests/test_non_runtime_production_pipeline.py"],
        project_root,
        pytest_log,
    )

    model_status = _production_model_status()
    trace = _run_pipeline(log_dir, model_status)
    trace_path = log_dir / "non-runtime-production-pipeline-trace.json"
    write_json(trace_path, trace)

    modules = {entry["module_name"] for entry in trace["manifest_modules"] if isinstance(entry, dict)}
    manifest_ok = {
        "SceneSemanticExtractor",
        "SpatialStructureBaker",
        "MultimodalSemanticClassifier",
        "SceneKnowledgeGenerator",
        "ReviewWorkbench",
        "DatasetAndReplayBuilder",
    }.issubset(modules)
    approved = trace["approved_artifact"]
    rejected = trace["rejected_artifact"]
    dataset = trace["dataset"]
    statuses_ok = (
        isinstance(approved, dict)
        and isinstance(rejected, dict)
        and approved.get("status") == "approved"
        and rejected.get("status") == "rejected"
        and approved.get("eligible_l1_seed") is True
        and approved.get("eligible_verification_seed") is True
        and rejected.get("eligible_l1_seed") is False
        and rejected.get("eligible_verification_seed") is False
    )
    dataset_ok = (
        isinstance(dataset, dict)
        and dataset.get("status") == "approved"
        and dataset.get("payload", {}).get("retention") == "verification_replay_dataset"
        and Path(str(trace["dataset_path"])).exists()
    )
    l1_seed_ok = Path(str(trace["l1_seed_path"])).exists() and bool(approved.get("review_evidence_refs"))
    no_runtime_private_context_ok = pytest_result.returncode == 0
    external_model_status_ok = str(model_status) in ALLOWED_EXTERNAL_MODEL_STATUSES

    results = [
        _result("backend-tests-pass", "Focused non-runtime production pipeline pytest passes", pytest_result.returncode == 0, [str(pytest_log)]),
        _result("pipeline-manifest-registered", "Six production modules are registered in the pipeline manifest", manifest_ok, [str(trace_path)]),
        _result("runtime-private-context-rejected", "Pipeline rejects character/Siming runtime private context/cache/history inputs", no_runtime_private_context_ok, [str(pytest_log)]),
        _result("review-state-gate-verified", "draft/review/approved/rejected state transitions are traceable", statuses_ok, [str(trace_path)]),
        _result("approved-seed-consumption-verified", "Approved artifact can be exported as reviewed L1 seed and verifier replay dataset input", l1_seed_ok and dataset_ok, [str(trace_path), str(trace["l1_seed_path"]), str(trace["dataset_path"])]),
        _result("rejected-draft-blocked", "Rejected draft is blocked from L1 seed and replay dataset consumption", bool(trace["rejected_blocked_from_l1_seed"]), [str(trace_path)]),
        {
            "id": "external-model-readiness",
            "title": "Production multimodal model readiness follows 7.03 provider readiness status",
            "status": str(model_status),
            "evidence": [".harness/verification/model-provider-readiness-report.json", str(trace_path)],
            "notes": "No mock provider is used as completion evidence.",
        },
    ]
    overall = (
        pytest_result.returncode == 0
        and manifest_ok
        and statuses_ok
        and dataset_ok
        and l1_seed_ok
        and bool(trace["rejected_blocked_from_l1_seed"])
        and external_model_status_ok
    )
    report = {
        "overall_non_runtime_production_pipeline_passed": overall,
        "external_model_status": model_status,
        "external_model_verified": model_status == "real_provider_verified",
        "blocked_missing_credentials": model_status == "blocked_missing_credentials",
        "results": results,
        "artifacts": {
            "pytest_log": str(pytest_log),
            "trace": str(trace_path),
            "l1_seed": str(trace["l1_seed_path"]),
            "replay_dataset": str(trace["dataset_path"]),
            "artifact_paths": trace["artifact_paths"],
        },
    }
    json_path = log_dir / "non-runtime-production-pipeline-report.json"
    md_path = log_dir / "non-runtime-production-pipeline-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Non-Runtime Production Pipeline Verification Report", report, "overall_non_runtime_production_pipeline_passed")

    print(f"non_runtime_production_pipeline_report_json={json_path}")
    print(f"non_runtime_production_pipeline_report_md={md_path}")
    print(f"overall_non_runtime_production_pipeline_passed={overall}")
    print(f"external_model_status={model_status}")
    for entry in results:
        print(f"{entry['id']}={entry['status']}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
