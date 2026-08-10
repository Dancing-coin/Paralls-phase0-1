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
    status: Literal["active", "suspended", "requeued", "rejected"]
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


class WorldModeProfile(ContinuityModel):
    world_ref: str = Field(min_length=1)
    mode: Literal["game", "simulation", "replay"]
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
    budget: int = Field(ge=1)
    candidates: tuple[BatchIntentCandidate, ...] = Field(min_length=1)


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
