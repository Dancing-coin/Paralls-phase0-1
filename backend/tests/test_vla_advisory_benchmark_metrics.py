from __future__ import annotations

from scripts.verification.vla_advisory_benchmark_metrics import build_sample_record, summarize_route


def _report(*, status: str = "real_provider_verified", duration: float = 2.0) -> dict[str, object]:
    return {
        "requested_route": "advisory-fast",
        "model_id": "qwen3.7-flash",
        "real_provider_status": status,
        "end_to_end_seconds": duration,
        "bridge_ok": True,
        "artifact_origin": "godot_runtime_capture",
        "advisory_boundary": {
            "writes_world_truth": False,
            "writes_esm_authority": False,
            "controls_actor": False,
        },
        "proof": {
            "result": {
                "findings": [
                    {"candidate_entity_refs": ["obj_letter"], "uncertainty": ""},
                    {"candidate_affordance_refs": [], "uncertainty": "provider returned an ungrounded textual finding"},
                ]
            }
        },
    }


def test_benchmark_record_keeps_only_safe_quality_counts() -> None:
    record = build_sample_record(_report(), archived_report=".harness/verification/benchmark/fast-1.json")

    assert record["finding_count"] == 2
    assert record["grounded_finding_count"] == 1
    assert record["ungrounded_finding_count"] == 1
    assert record["authority_boundary_ok"] is True
    assert "summary" not in record


def test_benchmark_summary_refuses_statistical_or_accuracy_claims_for_small_sample() -> None:
    summary = summarize_route(
        [
            build_sample_record(_report(duration=1.0), archived_report="one.json"),
            build_sample_record(_report(status="timeout", duration=20.0), archived_report="two.json"),
        ]
    )

    assert summary["success_rate"] == 0.5
    assert summary["end_to_end_seconds"]["p50"] == 1.0
    assert summary["end_to_end_seconds"]["p95"] == 20.0
    assert summary["statistical_readiness"] == "insufficient_samples"
    assert summary["semantic_accuracy_status"] == "not_evaluated_annotation_manifest_required"


def test_benchmark_rejects_repeated_replays_as_coverage_evidence() -> None:
    reports = [
        _report(duration=2.0)
        | {"annotation_sample_id": "same-capture", "pqf_scope": {"scene_id": "scene_demo"}}
        for _ in range(20)
    ]

    summary = summarize_route(
        [build_sample_record(report, archived_report=f"repeat-{index}.json") for index, report in enumerate(reports)]
    )

    assert summary["attempt_count"] == 20
    assert summary["distinct_annotation_sample_count"] == 1
    assert summary["statistical_readiness"] == "insufficient_distinct_annotation_samples"
    assert summary["semantic_accuracy_status"] == "not_evaluated_annotation_manifest_required"
