from __future__ import annotations

from .artifacts import ArtifactStatus, NonRuntimeProductionArtifact, ProductionArtifactKind, require_seed_eligible


class DatasetAndReplayBuilder:
    def build(
        self,
        *,
        dataset_id: str,
        artifacts: list[NonRuntimeProductionArtifact],
        scene_id: str,
    ) -> NonRuntimeProductionArtifact:
        if not artifacts:
            raise ValueError("replay dataset requires at least one approved artifact")
        for artifact in artifacts:
            require_seed_eligible(artifact, seed_kind="verification")
        entries = [
            {
                "artifact_id": artifact.artifact_id,
                "artifact_kind": artifact.artifact_kind,
                "scene_id": artifact.scene_id,
                "payload_ref": f"artifact://{artifact.artifact_id}",
                "review_evidence_refs": artifact.review_evidence_refs,
            }
            for artifact in artifacts
        ]
        return NonRuntimeProductionArtifact(
            artifact_id=f"nrpp:{scene_id}:replay-dataset:{dataset_id}",
            artifact_kind=ProductionArtifactKind.REPLAY_DATASET.value,
            scene_id=scene_id,
            status=ArtifactStatus.APPROVED.value,
            source_refs=[artifact.artifact_id for artifact in artifacts],
            payload={
                "dataset_id": dataset_id,
                "entries": entries,
                "retention": "verification_replay_dataset",
                "runtime_truth_status": "verification_artifact_only",
            },
            provenance={"module": "DatasetAndReplayBuilder"},
            eligible_verification_seed=True,
        )
