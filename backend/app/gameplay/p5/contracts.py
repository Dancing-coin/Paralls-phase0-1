from __future__ import annotations

import json
from hashlib import sha256
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.models import StrictGameplayModel


def _canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def canonical_sha256_digest(payload: object) -> str:
    return f"sha256:{sha256(_canonical_json_bytes(payload)).hexdigest()}"


def _stable_unique(values: tuple[str, ...], error_code: str) -> tuple[str, ...]:
    if len(set(values)) != len(values):
        raise ValueError(error_code)
    return values


class P5FrozenModel(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DirectedRelationshipRef(P5FrozenModel):
    relationship_ref: str = Field(pattern=r"^gameplay:relationship:[0-9a-f]{64}$")
    source_ref: str = Field(min_length=1)
    relation_kind: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)

    @classmethod
    def build(cls, *, source_ref: str, relation_kind: str, target_ref: str) -> "DirectedRelationshipRef":
        payload = {
            "relation_kind": relation_kind,
            "source_ref": source_ref,
            "target_ref": target_ref,
        }
        digest = sha256(_canonical_json_bytes(payload)).hexdigest()
        return cls(
            relationship_ref=f"gameplay:relationship:{digest}",
            source_ref=source_ref,
            relation_kind=relation_kind,
            target_ref=target_ref,
        )


def build_directed_relationship_ref(*, source_ref: str, relation_kind: str, target_ref: str) -> str:
    return DirectedRelationshipRef.build(
        source_ref=source_ref,
        relation_kind=relation_kind,
        target_ref=target_ref,
    ).relationship_ref


class P5SchemaPin(P5FrozenModel):
    schema_ref: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    schema_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class P5RevisionVector(P5FrozenModel):
    entries: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_mapping(cls, value: object) -> object:
        if isinstance(value, dict) and "entries" not in value:
            return {"entries": value}
        return value

    @model_validator(mode="after")
    def _validate_entries(self) -> "P5RevisionVector":
        for stream_ref, revision in self.entries.items():
            if not stream_ref:
                raise ValueError("p5_revision_vector_stream_ref_required")
            if revision < 0 or isinstance(revision, bool):
                raise ValueError("p5_revision_vector_invalid")
        return self


class QuestObjectiveDefinition(P5FrozenModel):
    objective_ref: str = Field(min_length=1)
    prerequisite_fact_refs: tuple[str, ...] = Field(default_factory=tuple)
    accepted_evidence_kind_refs: tuple[str, ...] = Field(min_length=1)
    visibility: str = Field(min_length=1)
    expiry_policy_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_objective(self) -> "QuestObjectiveDefinition":
        _stable_unique(self.prerequisite_fact_refs, "p5_objective_prerequisites_must_be_unique")
        _stable_unique(self.accepted_evidence_kind_refs, "p5_objective_evidence_kinds_must_be_unique")
        return self


class QuestPackageDefinition(P5FrozenModel):
    package_ref: str = Field(min_length=1)
    package_revision: str = Field(min_length=1)
    package_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    ruleset_revision: str = Field(min_length=1)
    objectives: tuple[QuestObjectiveDefinition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_objectives(self) -> "QuestPackageDefinition":
        objective_refs = tuple(objective.objective_ref for objective in self.objectives)
        _stable_unique(objective_refs, "p5_package_objective_refs_must_be_unique")
        return self


class P5ProposedEvent(P5FrozenModel):
    event_name: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    stream_ref: str = Field(min_length=1)
    visibility: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_visibility(self) -> "P5ProposedEvent":
        if self.visibility in {"authority_only", "public"}:
            return self
        if self.visibility.startswith("actor:") and len(self.visibility) > len("actor:"):
            return self
        raise ValueError("p5_event_visibility_invalid")


class P5ResolutionRequest(P5FrozenModel):
    request_ref: str = Field(min_length=1)
    registry_ref: str = Field(min_length=1)
    registry_revision: str = Field(min_length=1)
    registry_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    package_ref: str = Field(min_length=1)
    package_revision: str = Field(min_length=1)
    ruleset_revision: str = Field(min_length=1)
    evidence_provider_ref: str = Field(min_length=1)
    owner_adapter_ref: str = Field(min_length=1)
    provenance_source_ref: str = Field(min_length=1)
    subject_scope_ref: str = Field(min_length=1)
    expected_revisions: P5RevisionVector
    read_set_revisions: P5RevisionVector
    required_schema_pins: tuple[P5SchemaPin, ...] = Field(min_length=1)
    relationship_ref: str = Field(pattern=r"^gameplay:relationship:[0-9a-f]{64}$")
    proposed_events: tuple[P5ProposedEvent, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_request(self) -> "P5ResolutionRequest":
        _stable_unique(
            tuple(f"{schema.schema_ref}@{schema.schema_version}" for schema in self.required_schema_pins),
            "p5_required_schema_pins_must_be_unique",
        )
        return self


P5ResolutionResultKind = Literal[
    "rejected_zero_write",
    "committed_success",
    "committed_adverse_outcome",
]


class P5ResolutionResult(P5FrozenModel):
    result_kind: P5ResolutionResultKind
    registry_ref: str = Field(min_length=1)
    registry_revision: str = Field(min_length=1)
    registry_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    committed_event_refs: tuple[str, ...] = Field(default_factory=tuple)
    failure_code: str | None = None

    @model_validator(mode="after")
    def _validate_result(self) -> "P5ResolutionResult":
        if self.result_kind == "rejected_zero_write":
            if self.committed_event_refs:
                raise ValueError("p5_zero_write_result_must_not_commit")
            if not self.failure_code:
                raise ValueError("p5_zero_write_result_requires_failure_code")
            return self
        if not self.committed_event_refs:
            raise ValueError("p5_committed_result_requires_event_refs")
        if self.failure_code is not None:
            raise ValueError("p5_committed_result_must_not_include_failure")
        return self


__all__ = [
    "DirectedRelationshipRef",
    "P5FrozenModel",
    "P5ProposedEvent",
    "P5RevisionVector",
    "P5ResolutionRequest",
    "P5ResolutionResult",
    "P5ResolutionResultKind",
    "P5SchemaPin",
    "QuestObjectiveDefinition",
    "QuestPackageDefinition",
    "build_directed_relationship_ref",
    "canonical_sha256_digest",
]
