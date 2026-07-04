from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from enum import StrEnum
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "non-runtime-production-artifact.v1"


class ArtifactStatus(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"


class ProductionArtifactKind(StrEnum):
    SCENE_SEMANTIC_DRAFT = "scene_semantic_draft"
    SPATIAL_BAKE = "spatial_bake"
    MULTIMODAL_CLASSIFICATION = "multimodal_classification"
    AFFORDANCE_ANNOTATION = "affordance_annotation"
    REVIEW_REPORT = "review_report"
    REPLAY_DATASET = "replay_dataset"


FORBIDDEN_RUNTIME_PRIVATE_MARKERS = (
    "character_private_context",
    "siming_private_context",
    "private_context",
    "private_patch_session",
    "private_cache",
    "inference_history",
    "hidden_state",
    "runtime_private",
    "runtime://private",
    "character_mm:",
    "siming_mm:",
)


def assert_no_runtime_private_context(value: Any, *, path: str = "artifact") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            _assert_text_has_no_private_marker(key_text, f"{path}.{key_text}")
            assert_no_runtime_private_context(child, path=f"{path}.{key_text}")
        return
    if isinstance(value, list | tuple | set):
        for index, child in enumerate(value):
            assert_no_runtime_private_context(child, path=f"{path}[{index}]")
        return
    if isinstance(value, str):
        _assert_text_has_no_private_marker(value, path)


def _assert_text_has_no_private_marker(text: str, path: str) -> None:
    lowered = text.lower()
    for marker in FORBIDDEN_RUNTIME_PRIVATE_MARKERS:
        if marker in lowered:
            raise ValueError(f"non-runtime production artifact cannot contain runtime private context marker {marker!r} at {path}")


@dataclass(frozen=True)
class NonRuntimeProductionArtifact:
    artifact_id: str
    artifact_kind: str
    scene_id: str
    status: str
    source_refs: list[str]
    payload: dict[str, Any]
    provenance: dict[str, Any]
    schema_version: str = SCHEMA_VERSION
    review_evidence_refs: list[str] = field(default_factory=list)
    created_by: str = "non_runtime_production"
    writes_world_truth: bool = False
    enters_runtime: bool = False
    shares_runtime_private_context: bool = False
    eligible_l1_seed: bool = False
    eligible_verification_seed: bool = False
    model_readiness_status: str = ""

    def __post_init__(self) -> None:
        if self.status not in {status.value for status in ArtifactStatus}:
            raise ValueError(f"unsupported artifact status: {self.status}")
        if self.artifact_kind not in {kind.value for kind in ProductionArtifactKind}:
            raise ValueError(f"unsupported artifact kind: {self.artifact_kind}")
        if self.writes_world_truth or self.enters_runtime or self.shares_runtime_private_context:
            raise ValueError("non-runtime production artifacts must not enter runtime, share private context, or write world truth")
        assert_no_runtime_private_context(self.source_refs, path=f"{self.artifact_id}.source_refs")
        assert_no_runtime_private_context(self.payload, path=f"{self.artifact_id}.payload")
        assert_no_runtime_private_context(self.provenance, path=f"{self.artifact_id}.provenance")
        if self.status != ArtifactStatus.APPROVED.value and (self.eligible_l1_seed or self.eligible_verification_seed):
            raise ValueError("only approved artifacts can become L1 or verification seeds")
        if self.status == ArtifactStatus.REJECTED.value and (self.eligible_l1_seed or self.eligible_verification_seed):
            raise ValueError("rejected artifacts must never become seeds")

    def transition(
        self,
        status: ArtifactStatus,
        *,
        review_evidence_refs: list[str] | None = None,
        eligible_l1_seed: bool | None = None,
        eligible_verification_seed: bool | None = None,
        payload_updates: dict[str, Any] | None = None,
    ) -> "NonRuntimeProductionArtifact":
        payload = dict(self.payload)
        if payload_updates:
            payload.update(payload_updates)
        return replace(
            self,
            status=status.value,
            review_evidence_refs=list(review_evidence_refs if review_evidence_refs is not None else self.review_evidence_refs),
            eligible_l1_seed=bool(eligible_l1_seed) if eligible_l1_seed is not None else self.eligible_l1_seed,
            eligible_verification_seed=bool(eligible_verification_seed) if eligible_verification_seed is not None else self.eligible_verification_seed,
            payload=payload,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write_json(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path


def require_seed_eligible(artifact: NonRuntimeProductionArtifact, *, seed_kind: str) -> None:
    if artifact.status != ArtifactStatus.APPROVED.value:
        raise ValueError(f"{seed_kind} can only consume approved artifacts")
    if seed_kind == "l1" and not artifact.eligible_l1_seed:
        raise ValueError("artifact is not approved as an L1 seed")
    if seed_kind == "verification" and not artifact.eligible_verification_seed:
        raise ValueError("artifact is not approved as a verification seed")
