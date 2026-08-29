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
    cadence_ref: str = Field(min_length=1)
    cadence_owner_ref: str = Field(min_length=1)
    world_ref: str = Field(min_length=1)
    mode_ref: str = Field(min_length=1)
    mode_revision: str = Field(min_length=1)
    source_refs: tuple[str, ...] = ()
    source_revision_vector: dict[str, int] = Field(default_factory=dict)
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
        if "mode_ref" not in data and "world_mode_ref" in data:
            data["mode_ref"] = data.pop("world_mode_ref")
        if "mode_revision" not in data and "world_mode_revision" in data:
            data["mode_revision"] = data.pop("world_mode_revision")
        if "cadence_ref" not in data and "cadence_id" in data:
            data["cadence_ref"] = data.pop("cadence_id")
        return data

    @model_validator(mode="after")
    def validate_cadence(self) -> "PopulationCadenceInput":
        if self.window_end <= self.window_start:
            raise ValueError("cadence_window_invalid")
        if not self.source_refs or not self.source_revision_vector:
            raise ValueError("cadence_source_pin_incomplete")
        if len(set(self.source_refs)) != len(self.source_refs):
            raise ValueError("cadence_source_ref_duplicate")
        _check_vector(self.source_revision_vector)
        _check_vector(self.base_revision_vector)
        return self

    @property
    def cadence_id(self) -> str:
        return self.cadence_ref

    @property
    def world_mode_ref(self) -> str:
        return self.mode_ref

    @property
    def world_mode_revision(self) -> str:
        return self.mode_revision

    @classmethod
    def from_authority_event(cls, event: AuthorityEvent) -> "PopulationCadenceInput":
        if event.event_type != "population_cadence_event":
            raise ValueError("cadence_event_type_invalid")
        payload = event.payload.get("population_cadence")
        if not isinstance(payload, dict):
            raise ValueError("cadence_source_pin_incomplete")
        if payload.get("revoked") is True or payload.get("status") in {"revoked", "stale", "expired"}:
            raise ValueError("cadence_authorization_revoked")
        cadence = cls.model_validate(payload)
        if payload.get("scope") not in (None, cadence.report_scope):
            raise ValueError("cadence_scope_incompatible")
        return cadence


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


class PopulationBatchReport(ContinuityModel):
    batch_ref: str = Field(min_length=1)
    selected_cohort_refs: tuple[str, ...] = ()
    presentation_seeds: dict[str, Any] = Field(default_factory=dict)
    activation_candidates: tuple[str, ...] = ()
    owner_bound_intents: tuple[Any, ...] = ()
    rejected_candidates: tuple[Any, ...] = ()
    budget_used: int = Field(ge=0)
    budget_remaining: int = Field(ge=0)
    unprocessed_cohort_refs: tuple[str, ...] = ()
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
