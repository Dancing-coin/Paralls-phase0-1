from __future__ import annotations

from collections.abc import Iterable
from typing import Any


MINIMUM_STATISTICAL_SAMPLE_COUNT = 20
MINIMUM_DISTINCT_SCENE_COUNT = 2


def build_sample_record(report: dict[str, Any], *, archived_report: str) -> dict[str, object]:
    proof = report.get("proof") if isinstance(report.get("proof"), dict) else {}
    result = proof.get("result") if isinstance(proof.get("result"), dict) else {}
    findings = result.get("findings") if isinstance(result.get("findings"), list) else []
    grounded_findings = sum(
        1
        for finding in findings
        if isinstance(finding, dict)
        and (
            finding.get("candidate_entity_refs")
            or finding.get("candidate_collider_refs")
            or finding.get("candidate_anchor_refs")
            or finding.get("candidate_affordance_refs")
        )
    )
    ungrounded_findings = sum(
        1
        for finding in findings
        if isinstance(finding, dict) and "ungrounded" in str(finding.get("uncertainty", "")).lower()
    )
    boundary = report.get("advisory_boundary") if isinstance(report.get("advisory_boundary"), dict) else {}
    return {
        "route": str(report.get("requested_route", "")),
        "model_id": str(report.get("model_id", "")),
        "status": str(report.get("real_provider_status", "")),
        "end_to_end_seconds": _number(report.get("end_to_end_seconds")),
        "bridge_ok": report.get("bridge_ok") is True,
        "artifact_origin": str(report.get("artifact_origin", "")),
        "annotation_sample_id": str(report.get("annotation_sample_id", "")),
        "scene_id": _report_scene_id(report),
        "finding_count": len(findings),
        "grounded_finding_count": grounded_findings,
        "ungrounded_finding_count": ungrounded_findings,
        "authority_boundary_ok": all(
            boundary.get(name) is False for name in ("writes_world_truth", "writes_esm_authority", "controls_actor")
        ),
        "archived_report": archived_report,
    }


def summarize_route(samples: Iterable[dict[str, object]]) -> dict[str, object]:
    records = list(samples)
    durations = [float(sample["end_to_end_seconds"]) for sample in records if isinstance(sample.get("end_to_end_seconds"), int | float)]
    finding_count = sum(_integer(sample.get("finding_count")) for sample in records)
    grounded_count = sum(_integer(sample.get("grounded_finding_count")) for sample in records)
    distinct_annotation_sample_count = len(
        {str(sample["annotation_sample_id"]) for sample in records if sample.get("annotation_sample_id")}
    )
    distinct_scene_count = len({str(sample["scene_id"]) for sample in records if sample.get("scene_id")})
    statistical_readiness = _statistical_readiness(
        attempt_count=len(records),
        distinct_annotation_sample_count=distinct_annotation_sample_count,
        distinct_scene_count=distinct_scene_count,
    )
    return {
        "attempt_count": len(records),
        "successful_count": sum(sample.get("status") == "real_provider_verified" for sample in records),
        "success_rate": _ratio(sum(sample.get("status") == "real_provider_verified" for sample in records), len(records)),
        "bridge_success_rate": _ratio(sum(sample.get("bridge_ok") is True for sample in records), len(records)),
        "authority_boundary_compliance_rate": _ratio(
            sum(sample.get("authority_boundary_ok") is True for sample in records), len(records)
        ),
        "end_to_end_seconds": {
            "p50": _percentile(durations, 0.50),
            "p95": _percentile(durations, 0.95),
            "sample_count": len(durations),
            "scope": "live-proof end-to-end wall clock; includes local capture encoding and bridge work",
        },
        "grounded_finding_rate": _ratio(grounded_count, finding_count),
        "distinct_annotation_sample_count": distinct_annotation_sample_count,
        "distinct_scene_count": distinct_scene_count,
        "semantic_accuracy_status": (
            "not_evaluated_annotation_manifest_required"
            if statistical_readiness != "descriptive_only"
            else "annotation_manifest_required"
        ),
        "statistical_readiness": statistical_readiness,
    }


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile)
    return round(ordered[index], 3)


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def _integer(value: object) -> int:
    return int(value) if isinstance(value, int) else 0


def _report_scene_id(report: dict[str, Any]) -> str:
    scope = report.get("pqf_scope")
    return str(scope.get("scene_id", "")) if isinstance(scope, dict) else ""


def _statistical_readiness(
    *,
    attempt_count: int,
    distinct_annotation_sample_count: int,
    distinct_scene_count: int,
) -> str:
    if attempt_count < MINIMUM_STATISTICAL_SAMPLE_COUNT:
        return "insufficient_samples"
    if distinct_annotation_sample_count < MINIMUM_STATISTICAL_SAMPLE_COUNT:
        return "insufficient_distinct_annotation_samples"
    if distinct_scene_count < MINIMUM_DISTINCT_SCENE_COUNT:
        return "insufficient_scene_coverage"
    return "descriptive_only"
