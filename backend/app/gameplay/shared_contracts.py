from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.models import AppendBatchResult, StrictGameplayModel


def _stable_tuple(value: tuple[str, ...]) -> tuple[str, ...]:
    if len(set(value)) != len(value):
        raise ValueError("shared_contract_values_must_be_unique")
    return value


class EntityRef(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_type: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)


class SourceRef(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_type: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_revision: str | None = None


class RevisionVector(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entries: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_entries(self) -> "RevisionVector":
        for key, value in self.entries.items():
            if not key or value < 0:
                raise ValueError("revision_vector_invalid")
        return self


class EntityRecord(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_ref: EntityRef
    entity_kind: str = Field(min_length=1)
    lifecycle: str = Field(min_length=1)
    location_ref: EntityRef | None = None
    component_refs: tuple[str, ...] = Field(default_factory=tuple)
    source_refs: tuple[SourceRef, ...] = Field(default_factory=tuple)
    revision: RevisionVector


class ThingRecord(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_ref: EntityRef
    type_refs: tuple[str, ...] = Field(default_factory=tuple)
    material_refs: tuple[str, ...] = Field(default_factory=tuple)
    property_refs: tuple[str, ...] = Field(default_factory=tuple)
    status_refs: tuple[str, ...] = Field(default_factory=tuple)
    ownership_ref: str | None = None
    domain_projection_refs: tuple[str, ...] = Field(default_factory=tuple)
    revision: RevisionVector


class EnvironmentRecord(ThingRecord):
    pass


class RelationshipRecord(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    relationship_ref: str = Field(min_length=1)
    source_ref: EntityRef
    target_ref: EntityRef
    relation_kind: str = Field(min_length=1)
    terms_ref: str | None = None
    visibility_scope: str = Field(min_length=1)
    lifecycle: str = Field(min_length=1)
    revision: RevisionVector


class CausalEventRecord(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_ref: str = Field(min_length=1)
    trigger_ref: str = Field(min_length=1)
    causal_parent_refs: tuple[str, ...] = Field(default_factory=tuple)
    affected_entity_refs: tuple[EntityRef, ...] = Field(default_factory=tuple)
    observed_by: tuple[str, ...] = Field(default_factory=tuple)
    rule_revision_refs: tuple[str, ...] = Field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    settlement_refs: tuple[str, ...] = Field(default_factory=tuple)


class GameplayCommandEnvelope(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    command_id: str = Field(min_length=1)
    command_type: str = Field(min_length=1)
    command_version: int = Field(ge=1)
    principal_ref: str = Field(min_length=1)
    actor_ref: str | None = None
    project_ref: str | None = None
    transaction_id: str | None = None
    idempotency_key: str = Field(min_length=1)
    expected_revisions: dict[str, int] = Field(default_factory=dict)
    read_set_revisions: dict[str, int] = Field(default_factory=dict)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)
    pinned_revisions: dict[str, int] = Field(default_factory=dict)
    payload: dict[str, object] = Field(default_factory=dict)


class GameplayEventEnvelope(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    stream_ref: str = Field(min_length=1)
    stream_revision: int = Field(ge=0)
    global_sequence: int = Field(ge=0)
    transaction_id: str = Field(min_length=1)
    command_id: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    occurred_at: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    visibility_policy: str = Field(min_length=1)
    pinned_revisions: dict[str, int] = Field(default_factory=dict)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    payload: dict[str, object] = Field(default_factory=dict)


class EvidenceEnvelope(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_ref: str = Field(min_length=1)
    evidence_kind: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    observed_at: str = Field(min_length=1)
    verification_state: str = Field(min_length=1)
    payload_digest: str = Field(min_length=1)
    visibility_scope: str = Field(min_length=1)
    provenance_refs: tuple[str, ...] = Field(default_factory=tuple)


class SemanticDefinition(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    namespace: str = Field(min_length=1)
    semantic_id: str = Field(min_length=1)
    semantic_version: str = Field(min_length=1)
    tags: tuple[str, ...] = Field(default_factory=tuple)
    materials: tuple[str, ...] = Field(default_factory=tuple)
    properties: tuple[str, ...] = Field(default_factory=tuple)
    source_revision: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_values(self) -> "SemanticDefinition":
        _stable_tuple(self.tags)
        _stable_tuple(self.materials)
        _stable_tuple(self.properties)
        return self


class SemanticSnapshot(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_ref: str = Field(min_length=1)
    component_refs: tuple[str, ...] = Field(default_factory=tuple)
    resolved_tags: tuple[str, ...] = Field(default_factory=tuple)
    resolved_parameters: dict[str, object] = Field(default_factory=dict)
    statuses: tuple[str, ...] = Field(default_factory=tuple)
    relation_refs: tuple[str, ...] = Field(default_factory=tuple)
    policy_context_ref: str = Field(min_length=1)
    source_revision_vector: dict[str, int] = Field(default_factory=dict)
    digest: str = Field(min_length=1)


class ActionPrimitiveDefinition(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action_ref: str = Field(min_length=1)
    action_version: str = Field(min_length=1)
    target_kinds: tuple[str, ...] = Field(default_factory=tuple)
    required_capabilities: tuple[str, ...] = Field(default_factory=tuple)
    observation_requirements: tuple[str, ...] = Field(default_factory=tuple)
    physical_or_logical_fact_kind: Literal["physical", "logical"]
    cost_policy: dict[str, object] = Field(default_factory=dict)
    failure_policy: dict[str, object] = Field(default_factory=dict)


class EffectDefinition(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    effect_id: str = Field(min_length=1)
    effect_version: str = Field(min_length=1)
    inputs: tuple[str, ...] = Field(default_factory=tuple)
    preconditions: tuple[str, ...] = Field(default_factory=tuple)
    outputs: tuple[str, ...] = Field(default_factory=tuple)
    trace_policy: str = Field(min_length=1)


class ActionIntent(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    intent_id: str = Field(min_length=1)
    principal_ref: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    action_ref: str = Field(min_length=1)
    target_refs: tuple[str, ...] = Field(default_factory=tuple)
    requested_at: str = Field(min_length=1)
    required_observation_scope: str = Field(min_length=1)
    expected_revisions: dict[str, int] = Field(default_factory=dict)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)


class _FactBase(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fact_id: str = Field(min_length=1)
    source_ref: SourceRef
    observed_at: str = Field(min_length=1)
    subject_refs: tuple[str, ...] = Field(default_factory=tuple)
    payload: dict[str, object] = Field(default_factory=dict)
    confidence: str | None = None
    verification_state: str | None = None
    visibility_scope: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_fact_state(self) -> "_FactBase":
        if self.confidence is None and self.verification_state is None:
            raise ValueError("fact_state_missing")
        return self


class PhysicalFact(_FactBase):
    fact_kind: Literal["physical"] = "physical"


class LogicalFact(_FactBase):
    fact_kind: Literal["logical"] = "logical"


class SelectorQuery(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query_id: str = Field(min_length=1)
    query_version: str = Field(min_length=1)
    principal_ref: str = Field(min_length=1)
    selectors: tuple[str, ...] = Field(default_factory=tuple)
    expected_revisions: dict[str, int] = Field(default_factory=dict)
    privacy_scope: str = Field(min_length=1)


class EffectProposal(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: str = Field(min_length=1)
    effect_ref: str = Field(min_length=1)
    target_refs: tuple[str, ...] = Field(default_factory=tuple)
    preconditions: tuple[str, ...] = Field(default_factory=tuple)
    cost_reservations: tuple[str, ...] = Field(default_factory=tuple)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    source_rule_ref: str = Field(min_length=1)
    pinned_revisions: dict[str, int] = Field(default_factory=dict)


class Reservation(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reservation_ref: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    quantity_or_amount: int | float = Field(gt=0)
    status: str = Field(min_length=1)
    created_revision: int = Field(ge=0)
    expires_at_tick: int | None = None
    source_obligation_ref: str = Field(min_length=1)


class SettlementPlan(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_id: str = Field(min_length=1)
    command_id: str = Field(min_length=1)
    expected_revision_vector: dict[str, int] = Field(default_factory=dict)
    proposals: tuple[EffectProposal, ...] = Field(default_factory=tuple)
    event_mapping: dict[str, str | tuple[str, ...]] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)


class ScheduledObligation(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    obligation_id: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    due_tick: int = Field(ge=0)
    policy_revision: str = Field(min_length=1)
    status: str = Field(min_length=1)
    retry_policy: dict[str, object] = Field(default_factory=dict)
    compensation_policy: dict[str, object] = Field(default_factory=dict)
    source_refs: tuple[str, ...] = Field(default_factory=tuple)
    idempotency_key: str = Field(default="", min_length=1)
    expected_revisions: dict[str, int] = Field(default_factory=dict)
    visibility_scope: str = Field(default="project", min_length=1)

    @model_validator(mode="after")
    def _validate_lifecycle(self) -> "ScheduledObligation":
        if self.status not in {
            "open",
            "due",
            "settled",
            "cancelled",
            "expired",
            "retry",
            "compensated",
            "settling",
            "retryable",
            "closed",
            "failed",
        }:
            raise ValueError("scheduled_obligation_status_invalid")
        if any(value < 0 for value in self.expected_revisions.values()):
            raise ValueError("scheduled_obligation_revision_invalid")
        return self


class WorldConsumptionProfile(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_ref: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    tick_interval: int = Field(gt=0)
    batch_limit: int = Field(gt=0)
    catch_up_budget: int = Field(ge=0)
    reporting_projection_refs: tuple[str, ...] = Field(default_factory=tuple)
    active_revision_ref: str = Field(min_length=1)


class ActiveSemanticSet(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    world_ref: str = Field(min_length=1)
    semantic_registry_revision: str = Field(min_length=1)
    effect_registry_revision: str = Field(min_length=1)
    active_rule_revisions: tuple[str, ...] = Field(default_factory=tuple)
    policy_context_refs: tuple[str, ...] = Field(default_factory=tuple)
    activated_at_tick: int = Field(ge=0)
    digest: str = Field(min_length=1)


class ActiveWorldRevision(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    world_ref: str = Field(min_length=1)
    content_package_revisions: tuple[str, ...] = Field(default_factory=tuple)
    semantic_set_ref: str = Field(min_length=1)
    schema_registry_revision: str = Field(min_length=1)
    policy_revision_refs: tuple[str, ...] = Field(default_factory=tuple)
    core_compatibility_version: str = Field(min_length=1)
    digest: str = Field(min_length=1)


class GameplayPackageManifest(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    package_id: str = Field(min_length=1)
    package_revision: str = Field(min_length=1)
    domain_id: str = Field(min_length=1)
    maturity_level: str = Field(min_length=1)
    required_core_version: str = Field(min_length=1)
    owned_aggregates: tuple[str, ...] = Field(default_factory=tuple)
    state_groups: tuple[str, ...] = Field(default_factory=tuple)
    commands: tuple[str, ...] = Field(default_factory=tuple)
    events: tuple[str, ...] = Field(default_factory=tuple)
    projections: tuple[str, ...] = Field(default_factory=tuple)
    declared_schemas: tuple[str, ...] = Field(default_factory=tuple)
    dependencies: tuple[str, ...] = Field(default_factory=tuple)
    conflicts: tuple[str, ...] = Field(default_factory=tuple)
    capabilities: tuple[str, ...] = Field(default_factory=tuple)
    privacy_policies: tuple[str, ...] = Field(default_factory=tuple)
    mirror_bindings: tuple[str, ...] = Field(default_factory=tuple)
    compatibility_range: str = Field(min_length=1)
    migration_refs: tuple[str, ...] = Field(default_factory=tuple)
    content_digest: str = Field(min_length=1)
    actor_refs: tuple[str, ...] = Field(default_factory=tuple)
    actor_allowlist: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_actor_refs(self) -> "GameplayPackageManifest":
        refs = self.actor_refs or self.actor_allowlist
        if len(set(refs)) != len(refs):
            raise ValueError("package_actor_refs_must_be_unique")
        if any(not value or value.startswith("character:npc:") for value in refs):
            raise ValueError("package_actor_ref_invalid")
        return self


class ProfileBackedActorRef(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_ref: str = Field(pattern=r"^character:[^:]+$")
    profile_registry_revision: str = Field(min_length=1)
    authored_identity_digest: str = Field(min_length=1)
    package_ref: str = Field(min_length=1)
    package_grant_revision: str = Field(min_length=1)
    permitted_role_refs: tuple[str, ...] = Field(default_factory=tuple)


class ActorWorkIntentEnvelope(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    envelope: GameplayCommandEnvelope
    actor: ProfileBackedActorRef


class ActorWorkIntentResult(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    envelope: GameplayCommandEnvelope | None = None
    actor: ProfileBackedActorRef | None = None
    rejection: StructuredFailure | None = None

    @model_validator(mode="after")
    def _validate_result_shape(self) -> "ActorWorkIntentResult":
        if (self.envelope is None) == (self.rejection is None):
            raise ValueError("actor_work_intent_result_requires_one_outcome")
        if self.envelope is not None and self.actor is None:
            raise ValueError("actor_work_intent_actor_required")
        return self


class ProjectionEnvelope(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_id: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    projection_revision: str = Field(min_length=1)
    source_revision_vector: dict[str, int] = Field(default_factory=dict)
    privacy_scope: str = Field(min_length=1)
    payload: dict[str, object] = Field(default_factory=dict)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)


class SettlementReceipt(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    transaction_id: str = Field(min_length=1)
    committed_event_ids: tuple[str, ...] = Field(default_factory=tuple)
    stream_revisions: dict[str, int] = Field(default_factory=dict)
    projection_digests: dict[str, str] = Field(default_factory=dict)
    rejected_effects: tuple[str, ...] = Field(default_factory=tuple)
    audit_refs: tuple[str, ...] = Field(default_factory=tuple)
    pinned_revisions: dict[str, int] = Field(default_factory=dict)
    idempotency_status: Literal["new_commit", "duplicate_replayed", "rejected"] = "new_commit"
    zero_write: bool = False
    error_code: str | None = None

    @classmethod
    def from_append_result(
        cls,
        *,
        result: AppendBatchResult,
        audit_refs: tuple[str, ...] = (),
        pinned_revisions: dict[str, int] | None = None,
        projection_digests: dict[str, str] | None = None,
    ) -> "SettlementReceipt":
        """Build a read-only receipt from exactly one append result."""
        if result.committed and result.failure is not None:
            raise ValueError("settlement_receipt_append_result_invalid")
        if not result.committed and result.idempotency_status != "rejected":
            raise ValueError("settlement_receipt_append_result_invalid")
        return cls(
            transaction_id=result.transaction_id,
            committed_event_ids=tuple(result.committed_event_ids),
            stream_revisions=dict(result.resulting_stream_revisions),
            projection_digests=dict(projection_digests or {}),
            audit_refs=audit_refs,
            pinned_revisions=dict(pinned_revisions or {}),
            idempotency_status=result.idempotency_status,
            zero_write=not result.committed,
            error_code=result.failure.error_code if result.failure else None,
        )


class RevisionActivationRequest(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_ref: str = Field(min_length=1)
    project_ref: str = Field(min_length=1)
    world_ref: str = Field(min_length=1)
    candidate_revision_refs: tuple[str, ...] = Field(default_factory=tuple)
    expected_active_digest: str = Field(min_length=1)
    activation_tick: int = Field(ge=0)
    migration_ref: str | None = None
    lock_ref: str | None = None
    status: str = Field(min_length=1)


class AuthorizationDecision(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    decision_id: str = Field(min_length=1)
    principal_ref: str = Field(min_length=1)
    project_scope: str = Field(min_length=1)
    capability: str = Field(min_length=1)
    data_classification: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    reason_code: str = Field(min_length=1)
    expires_at: str | None = None
    audit_ref: str = Field(min_length=1)


class StructuredFailure(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    error_code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    blocked_owner_scope: str | None = None
    source_refs: tuple[str, ...] = Field(default_factory=tuple)
    zero_write_guarantee: bool = True
    retriable: bool = False
    details: dict[str, object] = Field(default_factory=dict)


__all__ = [
    "ActiveSemanticSet",
    "ActiveWorldRevision",
    "ActionIntent",
    "ActionPrimitiveDefinition",
    "AuthorizationDecision",
    "CausalEventRecord",
    "EffectDefinition",
    "EffectProposal",
    "EntityRecord",
    "EntityRef",
    "EnvironmentRecord",
    "EvidenceEnvelope",
    "GameplayCommandEnvelope",
    "GameplayEventEnvelope",
    "GameplayPackageManifest",
    "ProfileBackedActorRef",
    "ActorWorkIntentEnvelope",
    "ActorWorkIntentResult",
    "LogicalFact",
    "PhysicalFact",
    "ProjectionEnvelope",
    "RelationshipRecord",
    "Reservation",
    "RevisionActivationRequest",
    "RevisionVector",
    "ScheduledObligation",
    "SemanticDefinition",
    "SemanticSnapshot",
    "SelectorQuery",
    "SettlementPlan",
    "SettlementReceipt",
    "SourceRef",
    "StructuredFailure",
    "ThingRecord",
    "WorldConsumptionProfile",
]
