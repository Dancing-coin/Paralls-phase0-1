from __future__ import annotations

from hashlib import sha256
import json
from collections.abc import Mapping, Sequence

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.models import StrictGameplayModel


def _digest(value: object) -> str:
    return "sha256:" + sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


class FixedBaseBranchReplayContract(StrictGameplayModel):
    """Read-only contract for an isolated branch's deterministic replay inputs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    branch_ref: str = Field(min_length=1)
    stream_id: str = Field(min_length=1)
    base_event_digest: str = Field(min_length=1)
    base_checkpoint_sequence: int = Field(ge=0)
    tail_boundary: int = Field(ge=0)
    calibration_ref: str = Field(min_length=1)
    calibration_digest: str = Field(min_length=1)
    dataset_digest: str = Field(min_length=1)
    source_digests: tuple[tuple[str, str], ...] = ()
    family_digests: tuple[str, ...] = ()
    candidate_digests: tuple[tuple[str, str], ...] = ()
    input_digest: str = Field(min_length=1)
    privacy_scope: str = Field(min_length=1)
    projection_digest: str = ""

    @model_validator(mode="after")
    def validate_contract(self) -> "FixedBaseBranchReplayContract":
        if self.tail_boundary < self.base_checkpoint_sequence:
            raise ValueError("branch_tail_before_base")
        if not self.base_event_digest.startswith("sha256:"):
            raise ValueError("branch_base_digest_invalid")
        if not self.calibration_digest.startswith("sha256:"):
            raise ValueError("branch_calibration_digest_invalid")
        if not self.dataset_digest.startswith("sha256:"):
            raise ValueError("branch_dataset_digest_invalid")
        if any(
            not key or not value.startswith("sha256:")
            for key, value in self.source_digests
        ):
            raise ValueError("branch_source_digest_invalid")
        if any(not value.startswith("sha256:") for value in self.family_digests):
            raise ValueError("branch_family_digest_invalid")
        if any(not key or not value.startswith("sha256:") for key, value in self.candidate_digests):
            raise ValueError("branch_candidate_digest_invalid")
        if not self.input_digest.startswith("sha256:"):
            raise ValueError("branch_input_digest_invalid")
        if self.projection_digest and not self.projection_digest.startswith("sha256:"):
            raise ValueError("branch_projection_digest_invalid")
        return self

    @classmethod
    def from_preview_inputs(
        cls,
        *,
        branch_ref: str,
        base_event_digest: str,
        base_checkpoint_sequence: int,
        tail_boundary: int,
        calibration_ref: str,
        calibration: Mapping[str, object],
        source_digests: Mapping[str, str],
        candidate_digests: Sequence[tuple[str, str]],
        family_digests: Sequence[str],
        dataset_digest: str,
        privacy_scope: str,
        stream_id: str | None = None,
    ) -> "FixedBaseBranchReplayContract":
        canonical_sources = tuple(sorted((str(key), str(value)) for key, value in source_digests.items()))
        canonical_candidates = tuple(sorted((str(key), str(value)) for key, value in candidate_digests))
        canonical_family = tuple(sorted(str(value) for value in family_digests))
        calibration_digest = _digest(dict(calibration))
        input_digest = _digest(
            {
                "base_event_digest": base_event_digest,
                "base_checkpoint_sequence": base_checkpoint_sequence,
                "tail_boundary": tail_boundary,
                "calibration_ref": calibration_ref,
                "calibration_digest": calibration_digest,
                "dataset_digest": dataset_digest,
                "source_digests": canonical_sources,
                "family_digests": canonical_family,
                "candidate_digests": canonical_candidates,
            }
        )
        return cls(
            branch_ref=branch_ref,
            stream_id=stream_id or f"gameplay:branch_preview:{branch_ref}",
            base_event_digest=base_event_digest,
            base_checkpoint_sequence=base_checkpoint_sequence,
            tail_boundary=tail_boundary,
            calibration_ref=calibration_ref,
            calibration_digest=calibration_digest,
            dataset_digest=dataset_digest,
            source_digests=canonical_sources,
            family_digests=canonical_family,
            candidate_digests=canonical_candidates,
            input_digest=input_digest,
            privacy_scope=privacy_scope,
        )

    @classmethod
    def from_descriptor(cls, descriptor: Mapping[str, object]) -> "FixedBaseBranchReplayContract":
        value = descriptor.get("replay_contract")
        if not isinstance(value, Mapping):
            raise ValueError("branch_replay_contract_missing")
        return cls.model_validate(dict(value))

    @property
    def contract_digest(self) -> str:
        return _digest(self.model_dump(mode="json", exclude={"projection_digest"}))

    def with_projection_digest(self, projection_digest: str) -> "FixedBaseBranchReplayContract":
        return self.model_copy(update={"projection_digest": projection_digest})

    def validate_branch_stream(
        self, *, stream_id: str, branch_ref: str, privacy_scope: str
    ) -> str | None:
        if branch_ref != self.branch_ref or stream_id != self.stream_id:
            return "branch_replay_stream_mismatch"
        if privacy_scope != self.privacy_scope:
            return "branch_replay_privacy_mismatch"
        return None

    def validate_fixed_base(
        self,
        *,
        base_event_digest: str,
        base_checkpoint_sequence: int,
        tail_boundary: int,
    ) -> str | None:
        if (
            base_event_digest != self.base_event_digest
            or base_checkpoint_sequence != self.base_checkpoint_sequence
            or tail_boundary != self.tail_boundary
        ):
            return "branch_base_mismatch"
        return None

    def validate_calibration(self, *, calibration_ref: str, calibration_digest: str) -> str | None:
        if calibration_ref != self.calibration_ref or calibration_digest != self.calibration_digest:
            return "branch_source_digest_mismatch"
        return None

    @staticmethod
    def projection_digest_for_projection(projection: Mapping[str, object]) -> str:
        canonical = {
            key: value
            for key, value in projection.items()
            if key not in {"projection_hash", "replay_contract_projection_digest"}
        }
        return _digest(canonical)


__all__ = ["FixedBaseBranchReplayContract"]
