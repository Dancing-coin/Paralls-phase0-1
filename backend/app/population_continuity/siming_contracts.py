from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Sequence

from pydantic import Field, model_validator

from app.models.authority_event import AuthorityEvent
from app.population_continuity.models import ContinuityModel


def _check_vector(value: dict[str, int]) -> None:
    if any(not key or isinstance(revision, bool) or revision < 0 for key, revision in value.items()):
        raise ValueError("revision_vector_invalid")


class PopulationCadenceInput(ContinuityModel):
    cadence_id: str = Field(min_length=1)
    world_ref: str = Field(min_length=1)
    world_mode_ref: str = Field(min_length=1)
    world_mode_revision: str = Field(min_length=1)
    cadence_source_ref: str = ""
    cadence_source_revision: int = Field(default=0, ge=0)
    window_start: int = Field(ge=0)
    window_end: int = Field(ge=0)
    base_checkpoint_ref: str = Field(min_length=1)
    base_checkpoint_digest: str = Field(min_length=1)
    base_revision_vector: dict[str, int] = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    selector_revision: str = Field(min_length=1)
    ruleset_revision: str = Field(min_length=1)
    deterministic_seed: str = Field(min_length=1)
    catch_up_limit: int = Field(ge=0)
    budget: int = Field(ge=0)
    report_scope: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def accept_world_mode_names(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        if "cadence_id" not in data and "cadence_ref" in data:
            data["cadence_id"] = data.pop("cadence_ref")
        if "world_mode_ref" not in data and "mode_ref" in data:
            data["world_mode_ref"] = data.pop("mode_ref")
        if "world_mode_revision" not in data and "mode_revision" in data:
            data["world_mode_revision"] = data.pop("mode_revision")
        legacy_refs = data.pop("source_refs", None)
        legacy_vector = data.pop("source_revision_vector", None)
        if legacy_refs is not None or legacy_vector is not None:
            if not isinstance(legacy_refs, (list, tuple)) or len(legacy_refs) != 1 or not isinstance(legacy_refs[0], str) or not legacy_refs[0]:
                raise ValueError("cadence_source_pin_incomplete")
            if not isinstance(legacy_vector, dict) or len(legacy_vector) != 1:
                raise ValueError("cadence_source_pin_incomplete")
            vector_ref, vector_revision = next(iter(legacy_vector.items()))
            if vector_ref != legacy_refs[0]:
                raise ValueError("revision_vector_invalid")
            canonical_ref = data.get("cadence_source_ref")
            canonical_revision = data.get("cadence_source_revision")
            if canonical_ref is not None and canonical_ref != legacy_refs[0]:
                raise ValueError("cadence_source_pin_incomplete")
            if canonical_revision is not None and canonical_revision != vector_revision:
                raise ValueError("revision_vector_invalid")
            data.setdefault("cadence_source_ref", legacy_refs[0])
            data.setdefault("cadence_source_revision", vector_revision)
        return data

    @model_validator(mode="after")
    def validate_cadence(self) -> "PopulationCadenceInput":
        if self.window_end <= self.window_start:
            raise ValueError("cadence_window_invalid")
        if not self.cadence_source_ref:
            raise ValueError("cadence_source_pin_incomplete")
        if isinstance(self.cadence_source_revision, bool) or self.cadence_source_revision < 0:
            raise ValueError("cadence_source_pin_incomplete")
        _check_vector(self.base_revision_vector)
        return self

    @property
    def cadence_ref(self) -> str:
        return self.cadence_id

    @property
    def source_refs(self) -> tuple[str, ...]:
        return (self.cadence_source_ref,)

    @property
    def source_revision_vector(self) -> dict[str, int]:
        return {self.cadence_source_ref: self.cadence_source_revision}

    @classmethod
    def from_authority_event(cls, event: AuthorityEvent) -> "PopulationCadenceInput":
        if event.event_type != "population_cadence_event":
            raise ValueError("cadence_event_type_invalid")
        payload_value = event.payload.get("population_cadence")
        if not isinstance(payload_value, dict):
            raise ValueError("cadence_source_pin_incomplete")
        payload = dict(payload_value)
        if payload.get("revoked") is True or payload.get("status") in {"revoked", "stale", "expired"}:
            raise ValueError("cadence_authorization_revoked")
        envelope_scope = payload.pop("scope", None)
        if envelope_scope not in (None, payload.get("report_scope")):
            raise ValueError("cadence_scope_incompatible")
        return cls.model_validate(payload)


class PopulationProjection(ContinuityModel):
    ref: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    revision_vector: dict[str, int] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_projection(self) -> "PopulationProjection":
        _check_vector(self.revision_vector)
        return self


class PopulationReadSet(ContinuityModel):
    cadence: PopulationCadenceInput
    projections: tuple[PopulationProjection, ...] = ()
    read_set_digest: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_projection_refs(self) -> "PopulationReadSet":
        refs = [projection.ref for projection in self.projections]
        if len(refs) != len(set(refs)):
            raise ValueError("read_set_projection_duplicate")
        return self

    @classmethod
    def from_inputs(cls, cadence: PopulationCadenceInput, projections: Sequence[PopulationProjection]) -> "PopulationReadSet":
        ordered = tuple(sorted(projections, key=lambda item: item.ref))
        canonical = {"cadence": cadence.model_dump(mode="json"), "projections": [item.model_dump(mode="json") for item in ordered]}
        encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        return cls(cadence=cadence, projections=ordered, read_set_digest="sha256:" + hashlib.sha256(encoded).hexdigest())


class PopulationOwnerReceipt(ContinuityModel):
    receipt_ref: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    event_family: str = Field(min_length=1)
    committed: bool
    revision_vector: dict[str, int] = Field(default_factory=dict)
    zero_write: bool
    idempotency_status: str = "new_commit"

    @model_validator(mode="after")
    def validate_receipt_vector(self) -> "PopulationOwnerReceipt":
        _check_vector(self.revision_vector)
        return self


class PopulationBatchReport(ContinuityModel):
    batch_ref: str = Field(min_length=1)
    cohort_ref: str | None = None
    cohort_member_refs: tuple[str, ...] = ()
    selected_cohort_refs: tuple[str, ...] = ()
    presentation_seeds: dict[str, Any] = Field(default_factory=dict)
    activation_candidates: tuple[str, ...] = ()
    owner_bound_intents: tuple[Any, ...] = ()
    rejected_candidates: tuple[Any, ...] = ()
    budget_used: int = Field(ge=0)
    budget_remaining: int = Field(ge=0)
    unprocessed_cohort_refs: tuple[str, ...] = ()
    selected_count: int = Field(default=0, ge=0)
    unprocessed_count: int = Field(default=0, ge=0)
    presentation_seed_count: int = Field(default=0, ge=0)
    activation_candidate_count: int = Field(default=0, ge=0)
    owner_intent_count: int = Field(default=0, ge=0)
    owner_committed_count: int = Field(default=0, ge=0)
    continuity_committed_count: int = Field(default=0, ge=0)
    continuity_requeue_count: int = Field(default=0, ge=0)
    read_set_digest: str = Field(min_length=1)
    result_digest: str = Field(min_length=1)


class PopulationCycleResult(ContinuityModel):
    status: Literal["accepted", "owner_settlement_required", "requeue", "rejected"]
    batch_ref: str = Field(min_length=1)
    report: PopulationBatchReport
    seed_candidates: tuple[Any, ...] = ()
    owner_receipts: tuple[PopulationOwnerReceipt, ...] = ()
    continuity_receipts: tuple[Any, ...] = ()
    audits: tuple[Any, ...] = ()
    reason: str = ""
    production_append_count: int = Field(ge=0)
