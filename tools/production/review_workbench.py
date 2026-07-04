from __future__ import annotations

import json
from pathlib import Path

from .artifacts import ArtifactStatus, NonRuntimeProductionArtifact, ProductionArtifactKind, require_seed_eligible


class ReviewWorkbench:
    def __init__(self, evidence_dir: str | Path) -> None:
        self.evidence_dir = Path(evidence_dir)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    def submit_for_review(
        self,
        artifact: NonRuntimeProductionArtifact,
        *,
        reviewer: str,
        reason: str,
    ) -> tuple[NonRuntimeProductionArtifact, NonRuntimeProductionArtifact]:
        if artifact.status != ArtifactStatus.DRAFT.value:
            raise ValueError("only draft artifacts can be submitted for review")
        reviewed = artifact.transition(
            ArtifactStatus.REVIEW,
            payload_updates={"review_state": {"reviewer": reviewer, "reason": reason, "status": "review"}},
        )
        report = self._write_review_report(reviewed, reviewer=reviewer, status=ArtifactStatus.REVIEW, reason=reason)
        return reviewed.transition(ArtifactStatus.REVIEW, review_evidence_refs=[report.artifact_id]), report

    def approve(
        self,
        artifact: NonRuntimeProductionArtifact,
        *,
        reviewer: str,
        reason: str,
        allow_l1_seed: bool = True,
        allow_verification_seed: bool = True,
    ) -> tuple[NonRuntimeProductionArtifact, NonRuntimeProductionArtifact]:
        if artifact.status not in {ArtifactStatus.DRAFT.value, ArtifactStatus.REVIEW.value}:
            raise ValueError("only draft/review artifacts can be approved")
        approved = artifact.transition(
            ArtifactStatus.APPROVED,
            eligible_l1_seed=allow_l1_seed,
            eligible_verification_seed=allow_verification_seed,
            payload_updates={"review_state": {"reviewer": reviewer, "reason": reason, "status": "approved"}},
        )
        report = self._write_review_report(approved, reviewer=reviewer, status=ArtifactStatus.APPROVED, reason=reason)
        approved = approved.transition(
            ArtifactStatus.APPROVED,
            review_evidence_refs=[
                *artifact.review_evidence_refs,
                report.artifact_id,
                str(self.evidence_dir / f"{approved.artifact_id.replace(':', '_')}_approved.json"),
            ],
            eligible_l1_seed=allow_l1_seed,
            eligible_verification_seed=allow_verification_seed,
        )
        approved.write_json(self.evidence_dir / f"{approved.artifact_id.replace(':', '_')}_approved.json")
        return approved, report

    def reject(
        self,
        artifact: NonRuntimeProductionArtifact,
        *,
        reviewer: str,
        reason: str,
    ) -> tuple[NonRuntimeProductionArtifact, NonRuntimeProductionArtifact]:
        if artifact.status not in {ArtifactStatus.DRAFT.value, ArtifactStatus.REVIEW.value}:
            raise ValueError("only draft/review artifacts can be rejected")
        rejected = artifact.transition(
            ArtifactStatus.REJECTED,
            eligible_l1_seed=False,
            eligible_verification_seed=False,
            payload_updates={"review_state": {"reviewer": reviewer, "reason": reason, "status": "rejected"}},
        )
        report = self._write_review_report(rejected, reviewer=reviewer, status=ArtifactStatus.REJECTED, reason=reason)
        rejected = rejected.transition(ArtifactStatus.REJECTED, review_evidence_refs=[*artifact.review_evidence_refs, report.artifact_id])
        rejected.write_json(self.evidence_dir / f"{rejected.artifact_id.replace(':', '_')}_rejected.json")
        return rejected, report

    def export_l1_seed(self, artifact: NonRuntimeProductionArtifact) -> dict[str, object]:
        require_seed_eligible(artifact, seed_kind="l1")
        return {
            "seed_kind": "l1_scene_space_model_seed",
            "artifact_id": artifact.artifact_id,
            "scene_id": artifact.scene_id,
            "payload": artifact.payload,
            "review_evidence_refs": artifact.review_evidence_refs,
            "writes_world_truth": False,
            "runtime_truth_status": "reviewed_seed_only",
        }

    def _write_review_report(
        self,
        artifact: NonRuntimeProductionArtifact,
        *,
        reviewer: str,
        status: ArtifactStatus,
        reason: str,
    ) -> NonRuntimeProductionArtifact:
        report = NonRuntimeProductionArtifact(
            artifact_id=f"nrpp:{artifact.scene_id}:review-report:{status.value}:{artifact.artifact_kind}",
            artifact_kind=ProductionArtifactKind.REVIEW_REPORT.value,
            scene_id=artifact.scene_id,
            status=status.value,
            source_refs=[artifact.artifact_id, *artifact.source_refs],
            payload={
                "reviewer": reviewer,
                "status": status.value,
                "reason": reason,
                "source_artifact_ref": artifact.artifact_id,
                "source_refs": artifact.source_refs,
                "seed_decision": {
                    "eligible_l1_seed": artifact.eligible_l1_seed,
                    "eligible_verification_seed": artifact.eligible_verification_seed,
                },
            },
            provenance={"module": "ReviewWorkbench"},
            eligible_l1_seed=status == ArtifactStatus.APPROVED,
            eligible_verification_seed=status == ArtifactStatus.APPROVED,
        )
        report_path = self.evidence_dir / f"{report.artifact_id.replace(':', '_')}.json"
        report.write_json(report_path)
        md_path = self.evidence_dir / f"{report.artifact_id.replace(':', '_')}.md"
        md_path.write_text(
            "\n".join(
                [
                    "# Non-Runtime Production Review Report",
                    "",
                    f"- Artifact: `{artifact.artifact_id}`",
                    f"- Status: `{status.value}`",
                    f"- Reviewer: `{reviewer}`",
                    f"- Reason: `{reason}`",
                    f"- L1 seed eligible: `{artifact.eligible_l1_seed}`",
                    f"- Verification seed eligible: `{artifact.eligible_verification_seed}`",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        index_path = self.evidence_dir / "non-runtime-production-review-evidence.jsonl"
        with index_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(report.to_dict(), ensure_ascii=False) + "\n")
        return report
