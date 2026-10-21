from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import math
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, JsonValue, PlainSerializer, model_validator

from app.gameplay.runtime_state import StateGroupDefinition


SimulationTier = Literal["B0", "B1", "B2", "B3"]
ProposalKind = Literal["continuity_delta", "activity_candidate", "action_candidate", "upgrade_request", "decision_conflict"]


def _json_containers(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _json_containers(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_containers(item) for item in value]
    return value


def _freeze_json(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("simulation_value_not_finite")
    return value


def _freeze_revisions(value: Mapping[str, int]) -> Mapping[str, int]:
    if any(not key or type(revision) is not int or revision < 0 for key, revision in value.items()):
        raise ValueError("simulation_revision_vector_invalid")
    return MappingProxyType(dict(sorted(value.items())))


FrozenJsonObject = Annotated[
    Mapping[str, JsonValue], BeforeValidator(_json_containers), AfterValidator(_freeze_json),
    PlainSerializer(_json_containers),
]
FrozenRevisionVector = Annotated[
    Mapping[str, int], AfterValidator(_freeze_revisions), PlainSerializer(dict),
]
FrozenPolicyPins = Annotated[
    Mapping[str, str], AfterValidator(lambda value: MappingProxyType(dict(sorted(value.items())))), PlainSerializer(dict),
]


def simulation_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class SimulationContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False, revalidate_instances="always")


class ParticipationPolicy(SimulationContract):
    policy_ref: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    allowed_tiers: tuple[SimulationTier, ...]
    allowed_modules: tuple[str, ...]
    forbidden_dimensions: tuple[str, ...] = ()
    upgrade_triggers: tuple[str, ...] = ()
    b0_expiry_tick: int = Field(ge=0)
    review_tick: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_references(self) -> ParticipationPolicy:
        for values in (self.allowed_tiers, self.allowed_modules, self.forbidden_dimensions, self.upgrade_triggers):
            if any(not value for value in values) or len(values) != len(set(values)):
                raise ValueError("participation_references_invalid")
        return self


class ParticipationResolution(SimulationContract):
    allowed_tiers: tuple[SimulationTier, ...]
    recommended_tier: SimulationTier | None
    allowed_modules: tuple[str, ...]
    forbidden_dimensions: tuple[str, ...] = ()
    upgrade_triggers: tuple[str, ...] = ()
    b0_expiry_tick: int = Field(ge=0)
    review_tick: int = Field(ge=0)
    policy_revision: str = Field(min_length=1)
    source_policy_pins: FrozenPolicyPins
    status: Literal["resolved", "defer"]

    @model_validator(mode="after")
    def validate_resolution(self) -> ParticipationResolution:
        if self.status == "resolved":
            if self.recommended_tier not in self.allowed_tiers or not self.source_policy_pins:
                raise ValueError("participation_resolution_invalid")
        elif self.recommended_tier is not None:
            raise ValueError("participation_defer_has_recommendation")
        if any(not ref or not revision for ref, revision in self.source_policy_pins.items()):
            raise ValueError("participation_policy_pins_invalid")
        return self


class ModuleFieldPolicy(SimulationContract):
    aggregatable: bool = False
    distributable: bool = False
    individual_only: bool = True
    group_summary_only: bool = False

    @model_validator(mode="after")
    def validate_permissions(self) -> ModuleFieldPolicy:
        if self.individual_only and (self.aggregatable or self.distributable or self.group_summary_only):
            raise ValueError("module_field_policy_conflict")
        if self.group_summary_only and self.distributable:
            raise ValueError("module_summary_not_distributable")
        return self


class ModuleDefinition(SimulationContract):
    module_ref: str = Field(min_length=1)
    definition_version: str = Field(min_length=1)
    category: Literal["identity", "needs", "schedule", "household", "supply", "situation", "affect", "behavior"]
    input_selectors: tuple[str, ...]
    state_schema: StateGroupDefinition
    supported_tiers: tuple[SimulationTier, ...]
    proposal_kinds: tuple[ProposalKind, ...]
    aggregation_policy: str = Field(min_length=1)
    distribution_policy: Literal["none"] = "none"
    upgrade_triggers: tuple[str, ...] = ()
    capability_refs: tuple[str, ...] = ()
    protocol_refs: tuple[str, ...] = ()
    codebook_refs: tuple[str, ...] = ()
    field_policies: Annotated[
        Mapping[str, ModuleFieldPolicy], AfterValidator(lambda value: MappingProxyType(dict(value))),
        PlainSerializer(lambda value: {key: item.model_dump(mode="json") for key, item in value.items()}),
    ] = Field(default_factory=lambda: MappingProxyType({}))

    @model_validator(mode="after")
    def validate_definition(self) -> ModuleDefinition:
        schema = self.state_schema
        if schema.group_id != self.module_ref or schema.definition_version != self.definition_version:
            raise ValueError("module_schema_identity_mismatch")
        if not set(self.field_policies).issubset(schema.shared_fields):
            raise ValueError("module_field_policy_not_declared")
        return self

    def field_policy(self, field_name: str) -> ModuleFieldPolicy:
        if field_name not in self.state_schema.shared_fields:
            raise ValueError("module_field_not_declared")
        return self.field_policies.get(field_name, ModuleFieldPolicy())


class CharacterSimulationFrame(SimulationContract):
    schema_revision: Literal["character-simulation-frame@1"] = "character-simulation-frame@1"
    actor_ref: str = Field(min_length=1)
    profile_ref: str = Field(min_length=1)
    profile_revision: str = Field(min_length=1)
    character_core_revision: int = Field(ge=0)
    simulation_tick_cursor: int = Field(ge=0)
    source_revision_vector: FrozenRevisionVector
    module_states: FrozenJsonObject
    domain_fact_refs: tuple[str, ...]
    situation_ref: str | None = None
    participation_resolution: ParticipationResolution
    codebook_refs: tuple[str, ...]
    activation_lock_ref: str | None
    read_set_digest: str = Field(min_length=1)
    frame_digest: str = ""

    @model_validator(mode="after")
    def validate_frame(self) -> CharacterSimulationFrame:
        if self.actor_ref != self.profile_ref:
            raise ValueError("frame_actor_profile_mismatch")
        if not set(self.module_states).issubset(self.participation_resolution.allowed_modules):
            raise ValueError("frame_module_participation_denied")
        digest = simulation_digest(self.model_dump(mode="json", exclude={"frame_digest"}))
        if self.frame_digest and self.frame_digest != digest:
            raise ValueError("frame_digest_invalid")
        object.__setattr__(self, "frame_digest", digest)
        return self


def _check_references(*groups: tuple[str, ...]) -> None:
    for refs in groups:
        if any(not ref for ref in refs) or len(refs) != len(set(refs)):
            raise ValueError("simulation_references_invalid")


class ContinuityDeltaPayload(SimulationContract):
    schema_revision: Literal["module-continuity-delta@1"] = "module-continuity-delta@1"
    kind: Literal["continuity_delta"] = "continuity_delta"
    expected_group_revision: int = Field(ge=0)
    state_delta: FrozenJsonObject = Field(min_length=1)


class ActivityCandidatePayload(SimulationContract):
    schema_revision: Literal["module-activity-candidate@1"] = "module-activity-candidate@1"
    kind: Literal["activity_candidate"] = "activity_candidate"
    activity_ref: str = Field(min_length=1)


class ActionCandidatePayload(SimulationContract):
    schema_revision: Literal["module-action-candidate@1"] = "module-action-candidate@1"
    kind: Literal["action_candidate"] = "action_candidate"
    intent_ref: str = Field(min_length=1)
    capability_ref: str = Field(min_length=1)


class UpgradeRequestPayload(SimulationContract):
    schema_revision: Literal["module-upgrade-request@1"] = "module-upgrade-request@1"
    kind: Literal["upgrade_request"] = "upgrade_request"
    trigger_ref: str = Field(min_length=1)
    target_fidelity: Literal["B1", "B2", "B3"]


class DecisionConflictPayload(SimulationContract):
    schema_revision: Literal["module-decision-conflict@1"] = "module-decision-conflict@1"
    kind: Literal["decision_conflict"] = "decision_conflict"
    constraint_refs: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_constraints(self) -> DecisionConflictPayload:
        _check_references(self.constraint_refs)
        return self


ProposalPayload = Annotated[
    ContinuityDeltaPayload | ActivityCandidatePayload | ActionCandidatePayload
    | UpgradeRequestPayload | DecisionConflictPayload,
    Field(discriminator="kind"),
]


class SimulationSubject(SimulationContract):
    actor_ref: str | None = Field(default=None, min_length=1)
    cohort_ref: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_subject(self) -> SimulationSubject:
        if (self.actor_ref is None) == (self.cohort_ref is None):
            raise ValueError("simulation_subject_invalid")
        return self


class ModuleProposal(SimulationSubject):
    schema_revision: Literal["module-proposal@1"] = "module-proposal@1"
    proposal_ref: str = Field(min_length=1)
    module_ref: str = Field(min_length=1)
    definition_version: str = Field(min_length=1)
    frame_digest: str = Field(min_length=1)
    proposal_kind: ProposalKind
    typed_payload: ProposalPayload
    read_dependencies: FrozenRevisionVector
    required_fidelity: SimulationTier
    expiry_tick: int = Field(ge=0)
    source_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_payload_kind(self) -> ModuleProposal:
        if self.proposal_kind != self.typed_payload.kind:
            raise ValueError("proposal_kind_mismatch")
        return self


class SimulationCommitPacket(SimulationSubject):
    schema_revision: Literal["simulation-commit-packet@1"] = "simulation-commit-packet@1"
    from_tick: int = Field(ge=0)
    to_tick: int = Field(ge=0)
    expected_character_revision: int | None = Field(default=None, ge=0)
    source_revision_vector: FrozenRevisionVector
    proposal_refs: tuple[str, ...]
    owner_intent_refs: tuple[str, ...]
    lock_ref: str | None = Field(default=None, min_length=1)
    lock_revision: int | None = Field(default=None, ge=0)
    read_set_digest: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_packet(self) -> SimulationCommitPacket:
        if self.to_tick <= self.from_tick:
            raise ValueError("simulation_window_invalid")
        credentials = (self.expected_character_revision, self.lock_ref, self.lock_revision)
        if self.actor_ref is not None:
            if any(value is None for value in credentials):
                raise ValueError("simulation_actor_credentials_required")
        elif any(value is not None for value in credentials):
            raise ValueError("simulation_cohort_has_actor_credentials")
        _check_references(self.proposal_refs, self.owner_intent_refs)
        return self


class IntersectionPacket(SimulationContract):
    schema_revision: Literal["intersection-packet@1"] = "intersection-packet@1"
    intersection_ref: str = Field(min_length=1)
    actor_ref: str = Field(min_length=1)
    trigger_kind: str = Field(min_length=1)
    group_ref: str = Field(min_length=1)
    last_confirmed_tick: int = Field(ge=0)
    continuity_revision: int = Field(ge=0)
    source_revision_vector: FrozenRevisionVector
    hard_constraints: tuple[str, ...]
    unresolved_proposals: tuple[str, ...]
    required_code_refs: tuple[str, ...]
    target_fidelity: SimulationTier
    lock_ref: str = Field(min_length=1)
    lock_revision: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_references(self) -> IntersectionPacket:
        _check_references(self.hard_constraints, self.unresolved_proposals, self.required_code_refs)
        return self
