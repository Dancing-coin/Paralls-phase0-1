from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.gameplay.models import StrictGameplayModel


class ContinuityModel(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ActivationProposal(ContinuityModel):
    proposal_id: str = Field(min_length=1)
    profile_ref: str = Field(min_length=1)
    world_ref: str = Field(min_length=1)
    package_revision: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    activation_reason: str = Field(min_length=1)
    scope_grant: tuple[str, ...] = Field(min_length=1)
    cadence_class: str = Field(min_length=1)
    expected_revisions: dict[str, int] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_profile_ref(self) -> "ActivationProposal":
        if not self.profile_ref.startswith("character:"):
            raise ValueError("activation_profile_ref_must_be_registered_character")
        if len(set(self.scope_grant)) != len(self.scope_grant):
            raise ValueError("activation_scope_grant_duplicate")
        return self


class ActivationGrant(ContinuityModel):
    profile_ref: str = Field(min_length=1)
    world_ref: str = Field(min_length=1)
    package_revision: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    scope_grant: tuple[str, ...] = Field(min_length=1)


class ActivationReceipt(ContinuityModel):
    committed: bool
    status: Literal["active", "locked", "suspended", "requeued", "rejected"]
    profile_ref: str
    identity_digest: str = ""
    committed_event_ids: tuple[str, ...] = ()
    revision_vector: dict[str, int] = Field(default_factory=dict)
    replay_hash: str = ""
    scope: tuple[str, ...] = ()
    redaction: str = ""
    zero_write: bool = False
    idempotency_status: str = "rejected"
    stop_reason: str | None = None


class ActivationLock(ContinuityModel):
    lock_ref: str = Field(min_length=1)
    profile_ref: str = Field(min_length=1)
    world_ref: str = Field(min_length=1)
    held_revision: int = Field(ge=0)
    status: Literal["active", "released"] = "active"


class PendingChange(ContinuityModel):
    change_ref: str = Field(min_length=1)
    lock_ref: str = Field(min_length=1)
    profile_ref: str = Field(min_length=1)
    expected_revision: int = Field(ge=0)
    payload: dict[str, Any] = Field(default_factory=dict)
    privacy_scope: str = Field(min_length=1)


class WorldModeProfile(ContinuityModel):
    world_ref: str = Field(min_length=1)
    mode: Literal["game", "simulation", "preview", "replay"]
    revision: str = Field(min_length=1)
    cadence_class: str = Field(min_length=1)
    batch_limit: int = Field(ge=1)
    wake_budget: int = Field(ge=0)
    catch_up_limit: int = Field(ge=0)
    allowed_intent_kinds: tuple[str, ...] = Field(default_factory=tuple)
    survival_mode: Literal["disabled", "narrative", "simulation"] = "disabled"
    degraded_threshold: int = Field(ge=1)
    allowed_privacy_scopes: tuple[str, ...] = (
        "actor:self",
        "organization:summary",
        "public",
    )


class DueEvaluationReceipt(ContinuityModel):
    envelopes: tuple[GameplayCommandEnvelope, ...] = ()
    zero_write: bool = True
    overdue_refs: tuple[str, ...] = ()
    stop_reason: str | None = None


class WorldModeReceipt(ContinuityModel):
    committed: bool
    world_ref: str
    mode_revision: str
    action: Literal["pause", "resume", "rejected"]
    committed_event_ids: tuple[str, ...] = ()
    revision_vector: dict[str, int] = Field(default_factory=dict)
    zero_write: bool = False
    stop_reason: str | None = None


class BatchIntentCandidate(ContinuityModel):
    intent_ref: str = Field(min_length=1)
    profile_ref: str = Field(min_length=1)
    intent_kind: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0
    claim_refs: tuple[str, ...] = ()
    expected_revisions: dict[str, int] = Field(default_factory=dict)
    policy_revision: str = Field(min_length=1)
    package_revision: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    privacy_scope: str = Field(min_length=1)


class PopulationBatchPlan(ContinuityModel):
    batch_ref: str = Field(min_length=1)
    world_ref: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    package_revision: str = Field(min_length=1)
    deterministic_seed: str = Field(min_length=1)
    input_digest: str = Field(min_length=1)
    social_recipient_ref: str | None = None
    social_observed_at: str | None = None
    social_projection_digest: str | None = None
    social_source_revision_vector: dict[str, int] = Field(default_factory=dict)
    household_recipient_ref: str | None = None
    household_observed_at: str | None = None
    household_projection_digest: str | None = None
    household_source_revision_vector: dict[str, int] = Field(default_factory=dict)
    organization_recipient_ref: str | None = None
    organization_observed_at: str | None = None
    organization_projection_digest: str | None = None
    organization_source_revision_vector: dict[str, int] = Field(default_factory=dict)
    budget: int = Field(ge=1)
    candidates: tuple[BatchIntentCandidate, ...] = Field(min_length=1)


class PopulationWorldPlan(ContinuityModel):
    batch_ref: str = Field(min_length=1)
    world_ref: str = Field(min_length=1)
    mode: Literal["game", "simulation", "preview"]
    mode_revision: str = Field(min_length=1)
    package_revision: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    deterministic_seed: str = Field(min_length=1)
    input_digest: str = Field(min_length=1)
    source_vectors: dict[str, dict[str, int]] = Field(default_factory=dict)
    base_checkpoint_event_count: int = Field(ge=0)
    tail_event_count: int = Field(ge=0)
    budget: int = Field(ge=1)
    activation_locks: tuple[str, ...] = ()
    idempotency_keys: tuple[str, ...] = ()
    report_scope: str = Field(min_length=1)
    candidates: tuple[BatchIntentCandidate, ...] = Field(min_length=1)
    base_event_digest: str = Field(default="sha256:unbound")
    base_checkpoint_sequence: int = Field(default=0, ge=0)
    tail_boundary: int = Field(default=0, ge=0)
    active_revision_refs: tuple[str, ...] = Field(default_factory=tuple)
    source_revision_vector: dict[str, int] = Field(default_factory=dict)
    activation_lock_refs: tuple[str, ...] = Field(default_factory=tuple)
    social_input_digest: str | None = None
    social_recipient_ref: str | None = None
    household_input_digest: str | None = None
    household_recipient_ref: str | None = None
    organization_input_digest: str | None = None
    organization_recipient_ref: str | None = None
    organization_schedule_ref: str | None = None
    capability_ref: str | None = None
    capability_jurisdiction_ref: str | None = None
    capability_revision: int | None = Field(default=None, ge=1)
    capability_policy_revision: str | None = None
    capability_evaluated_tick: int | None = Field(default=None, ge=0)
    capability_source_event_refs: tuple[str, ...] = ()
    capability_projection_digest: str | None = None
    capability_source_revision_vector: dict[str, int] = Field(default_factory=dict)
    capability_reader_scope: str | None = None
    capability_eligibility_digest: str | None = None
    production_evidence_recipient_ref: str | None = None
    production_evidence_observed_at: str | None = None
    production_evidence_projection_digest: str | None = None
    production_evidence_refs: tuple[str, ...] = ()
    production_evidence_rows: tuple[dict[str, object], ...] = ()
    production_evidence_event_refs: tuple[str, ...] = ()
    production_evidence_source_revision_vector: dict[str, int] = Field(default_factory=dict)
    production_evidence_input_digest: str | None = None

    @model_validator(mode="after")
    def validate_boundaries(self) -> "PopulationWorldPlan":
        if self.tail_boundary < self.base_checkpoint_sequence:
            raise ValueError("population_world_plan_tail_before_base")
        if any(revision < 0 or isinstance(revision, bool) for revision in self.source_revision_vector.values()):
            raise ValueError("population_world_plan_source_revision_invalid")
        if len(set(self.active_revision_refs)) != len(self.active_revision_refs):
            raise ValueError("population_world_plan_revision_duplicate")
        capability_fields = (
            self.capability_ref,
            self.capability_jurisdiction_ref,
            self.capability_revision,
            self.capability_policy_revision,
            self.capability_evaluated_tick,
            self.capability_projection_digest,
            self.capability_reader_scope,
            self.capability_eligibility_digest,
        )
        if any(value is not None for value in capability_fields):
            if any(value is None for value in capability_fields):
                raise ValueError("population_world_plan_capability_pin_incomplete")
            if not self.capability_source_event_refs or not self.capability_source_revision_vector:
                raise ValueError("population_world_plan_capability_source_missing")
        production_fields = (
            self.production_evidence_recipient_ref,
            self.production_evidence_observed_at,
            self.production_evidence_projection_digest,
            self.production_evidence_input_digest,
        )
        if any(value is not None for value in production_fields):
            if any(value is None for value in production_fields):
                raise ValueError("population_world_plan_production_evidence_pin_incomplete")
            if not self.production_evidence_refs or not self.production_evidence_rows or not self.production_evidence_event_refs or not self.production_evidence_source_revision_vector:
                raise ValueError("population_world_plan_production_evidence_source_missing")
        schedule_fields = (
            self.social_input_digest,
            self.social_recipient_ref,
            self.household_input_digest,
            self.household_recipient_ref,
            self.organization_input_digest,
            self.organization_recipient_ref,
            self.organization_schedule_ref,
        )
        if any(value is not None for value in schedule_fields):
            if any(value is None for value in schedule_fields):
                raise ValueError("population_world_plan_schedule_source_pin_incomplete")
            if len({self.social_recipient_ref, self.household_recipient_ref, self.organization_recipient_ref}) != 1:
                raise ValueError("population_world_plan_schedule_recipient_mismatch")
        return self


class MergeRejection(ContinuityModel):
    intent_ref: str
    error_code: str
    retriable: bool = False
    claim_refs: tuple[str, ...] = ()


class ContinuityMergeReceipt(ContinuityModel):
    committed: bool
    batch_ref: str
    accepted_intent_refs: tuple[str, ...] = ()
    deferred_intent_refs: tuple[str, ...] = ()
    rejections: tuple[MergeRejection, ...] = ()
    committed_event_ids: tuple[str, ...] = ()
    revision_vector: dict[str, int] = Field(default_factory=dict)
    replay_hash: str = ""
    scope: tuple[str, ...] = ()
    redaction: str = ""
    zero_write: bool = False
    idempotency_status: str = "rejected"
    stop_reason: str | None = None
    owner_receipt_ref: str | None = None
