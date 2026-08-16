from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Iterable, Literal

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.models import StrictGameplayModel
from app.gameplay.semantic_effects import StateDefinition
from app.gameplay.shared_contracts import (
    ActionIntent,
    EntityRecord,
    EnvironmentRecord,
    EffectProposal,
    RelationshipRecord,
    SemanticDefinition,
    SemanticSnapshot,
    ThingRecord,
)


def _stable_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _stable_digest(value: object) -> str:
    return f"sha256:{sha256(_stable_json(value).encode('utf-8')).hexdigest()}"


class SemanticRegistryError(ValueError):
    pass


class TagDefinition(StrictGameplayModel):
    """Versioned semantic tag declaration; assignments remain domain-owned."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tag_ref: str = Field(min_length=1)
    category: str = Field(min_length=1)
    parent_refs: tuple[str, ...] = Field(default_factory=tuple)
    parameter_schema: dict[str, str] = Field(default_factory=dict)
    merge_policy: str = Field(default="replace_by_specificity", min_length=1)
    specificity: int = 0
    version: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_tag(self) -> "TagDefinition":
        if self.category not in {"type", "material", "substance", "property", "state", "capability", "relation", "context"}:
            raise ValueError("semantic_tag_category_unsupported")
        if len(set(self.parent_refs)) != len(self.parent_refs):
            raise ValueError("semantic_tag_parent_duplicate")
        if self.merge_policy not in {"replace_by_specificity", "additive", "minimum", "maximum", "exclusive", "compose"}:
            raise ValueError("semantic_tag_merge_policy_unsupported")
        return self


class TagAssignment(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_ref: str = Field(min_length=1)
    tag_ref: str = Field(min_length=1)
    component_ref: str | None = None
    parameter_values: dict[str, object] = Field(default_factory=dict)
    source_ref: str = Field(min_length=1)
    revision: int = Field(ge=0)


class SemanticSelector(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entity_kind: str | None = None
    component_scope: str | None = None
    require_all_tags: tuple[str, ...] = Field(default_factory=tuple)
    require_any_tags: tuple[str, ...] = Field(default_factory=tuple)
    exclude_tags: tuple[str, ...] = Field(default_factory=tuple)
    parameter_predicates: dict[str, object] = Field(default_factory=dict)
    status_predicates: tuple[str, ...] = Field(default_factory=tuple)
    relation_predicates: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _validate_selector(self) -> "SemanticSelector":
        allowed_operators = {"eq", "gte", "lte", "in"}
        for predicate in self.parameter_predicates.values():
            if isinstance(predicate, dict) and set(predicate) - allowed_operators:
                raise ValueError("semantic_selector_operator_unsupported")
        return self


class EntityDossier(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entity: EntityRecord
    thing: ThingRecord | None = None
    environment: EnvironmentRecord | None = None
    relationships: tuple[RelationshipRecord, ...] = Field(default_factory=tuple)
    causal_event_refs: tuple[str, ...] = Field(default_factory=tuple)
    digest: str = Field(min_length=1)


class MetaRuleDefinition(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_ref: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    trigger_selectors: tuple[str, ...] = Field(min_length=1)
    guard_expression: str = Field(min_length=1)
    phase: str = Field(min_length=1)
    priority: int
    conflict_policy: str = Field(min_length=1)
    evaluation_budget: int = Field(gt=0)
    proposal_templates: tuple[EffectProposal, ...] = Field(default_factory=tuple)
    trace_policy: str = Field(min_length=1)
    source_revision: str = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_selectors(self) -> "MetaRuleDefinition":
        if len(set(self.trigger_selectors)) != len(self.trigger_selectors):
            raise ValueError("semantic_rule_trigger_selector_duplicate")
        if self.phase not in {"pre", "post", "normalize", "eligibility", "derive", "resolve", "propagate", "settle"}:
            raise ValueError("semantic_rule_phase_unsupported")
        if self.conflict_policy not in {"exclusive", "compose", "highest_priority", "reject"}:
            raise ValueError("semantic_rule_conflict_policy_unsupported")
        if self.trace_policy not in {"none", "summary", "full", "authority_only"}:
            raise ValueError("semantic_rule_trace_policy_unsupported")
        if not SemanticRegistry._is_closed_guard(self.guard_expression):
            raise SemanticRegistryError("semantic_guard_expression_unsupported")
        return self


class OwnerMapping(StrictGameplayModel):
    """A single approved semantic effect target; this is not a target owner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    effect_ref: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    stream_pattern: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    fragment_builder_ref: str = Field(min_length=1)
    projection_scope: Literal["project", "authority_only"]
    revision: str = Field(min_length=1)


class ClosedEffectDefinition(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    effect_ref: str = Field(min_length=1)
    input_schema_ref: str = Field(min_length=1)
    stack_policy: Literal["one_shot"]
    revision: str = Field(min_length=1)


class StateLifecyclePolicy(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state_ref: str = Field(min_length=1)
    effect_ref: str | None = None
    lifecycle: Literal["one_shot", "scheduled"]
    revision: str = Field(min_length=1)
    owner_ref: str | None = None
    stream_pattern: str | None = None
    opened_event_type: str | None = None
    settled_event_type: str | None = None
    cancelled_event_type: str | None = None
    fragment_builder_ref: str | None = None
    projection_scope: Literal["project", "authority_only"] | None = None


class StateOwnerRow(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state_ref: str = Field(min_length=1)
    effect_ref: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    stream_pattern: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    projection_scope: Literal["project", "authority_only"]
    definition: StateDefinition
    revision: str = Field(min_length=1)


class StateOwnerContract(StrictGameplayModel):
    """Closed owner contract read by existing state-writing authorities."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    effect_ref: str = Field(min_length=1)
    state_ref: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    stream_pattern: str = Field(min_length=1)
    apply_event_type: str = Field(min_length=1)
    opened_event_type: str | None = None
    expired_event_type: str | None = None
    settled_event_type: str | None = None
    projection_scope: Literal["project", "authority_only"]
    definition: StateDefinition
    revision: str = Field(min_length=1)


class LifecycleOwnerContract(StrictGameplayModel):
    """Immutable admission metadata for an already-owned lifecycle family."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    effect_ref: str = Field(min_length=1)
    state_ref: str | None = None
    owner_ref: str = Field(min_length=1)
    stream_pattern: str = Field(min_length=1)
    event_types: tuple[str, ...] = Field(min_length=1)
    action_effect_refs: tuple[str, ...] = Field(default_factory=tuple)
    projection_scope: Literal["project", "authority_only"]
    outbox_topic: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    revision_rule: str = Field(min_length=1)
    idempotency_strategy: str = Field(min_length=1)
    replay_reader_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_closed_values(self) -> "LifecycleOwnerContract":
        if len(set(self.event_types)) != len(self.event_types):
            raise ValueError("semantic_lifecycle_event_type_duplicate")
        if len(set(self.action_effect_refs)) != len(self.action_effect_refs):
            raise ValueError("semantic_lifecycle_action_duplicate")
        return self


class StateLifecycleAdapterContract(StrictGameplayModel):
    """Closed semantic adapter admission; it never carries a write callback."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    effect_ref: str = Field(min_length=1)
    state_ref: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    adapter_ref: Literal[
        "SemanticSettlementAuthority.settle_closed_survival_state",
        "SemanticSettlementAuthority.settle_closed_construction_maintenance_state",
        "SemanticSettlementAuthority.settle_closed_ecology_frost",
        "SemanticSettlementAuthority.settle_closed_ecology_drought",
    ]
    operations: tuple[Literal["apply", "expire", "dispel", "transform", "cancel"], ...] = Field(min_length=1)
    revision: str = Field(min_length=1)


class RegisteredStateOwnerRoute(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state_ref: str = Field(min_length=1)
    effect_ref: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    stream_pattern: str = Field(min_length=1)
    adapter_ref: Literal[
        "SemanticSettlementAuthority.settle_closed_survival_state",
        "SemanticSettlementAuthority.settle_closed_construction_maintenance_state",
        "SemanticSettlementAuthority.settle_closed_ecology_frost",
        "SemanticSettlementAuthority.settle_closed_ecology_drought",
    ]
    projection_scope: Literal["project"]
    revision: str = Field(min_length=1)


class RegisteredEffectOwnerRoute(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    effect_ref: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    stream_pattern: str = Field(min_length=1)
    opened_event_type: str = Field(min_length=1)
    adapter_ref: Literal["SemanticSettlementAuthority.settle_registered_wage_obligation"]
    projection_scope: Literal["project"]
    revision: str = Field(min_length=1)


class RegisteredSurvivalStateActionRoute(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    effect_ref: Literal["effect:state_dispel", "effect:state_transform_recovery"]
    owner_ref: Literal["actor_gameplay.survival_domain"]
    source_state_refs: tuple[Literal["state:cold", "state:overheated", "state:dehydrated", "state:fatigued"], ...]
    stream_pattern: Literal["gameplay:survival:{actor_ref}"]
    event_type: Literal["gameplay.survival.state_dispelled", "gameplay.survival.state_transformed"]
    adapter_ref: Literal["SemanticSettlementAuthority.settle_registered_survival_state_action"]
    projection_scope: Literal["project"]
    revision: Literal["1"]


class RegisteredConstructionMaintenanceStateActionRoute(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    effect_ref: Literal["effect:maintenance_state_dispel"]
    owner_ref: Literal["actor_gameplay.construction_production_domain"]
    state_ref: Literal["state:maintenance_due"]
    stream_pattern: Literal["gameplay:construction_production:{facility_ref}"]
    event_type: Literal["gameplay.construction_production.maintenance_state_dispelled"]
    adapter_ref: Literal["SemanticSettlementAuthority.settle_registered_construction_maintenance_state_action"]
    projection_scope: Literal["project"]
    revision: Literal["1"]


class ClosedRuleDefinition(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_ref: str = Field(min_length=1)
    phase: Literal["normalize", "eligibility", "derive", "resolve", "propagate", "settle"]
    priority: int
    specificity: int = Field(ge=0)
    conflict_policy: Literal["exclusive", "replace", "additive", "minimum", "maximum", "suppress", "reject"]
    handler_ref: Literal["handler:production_due_finish"]
    effect_ref: str = Field(min_length=1)
    owner_mapping_ref: str = Field(min_length=1)


class RuleSetRevision(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_set_ref: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    active_semantic_set_digest: str = Field(min_length=1)
    rules: tuple[ClosedRuleDefinition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_rules(self) -> "RuleSetRevision":
        if len({rule.rule_ref for rule in self.rules}) != len(self.rules):
            raise ValueError("semantic_closed_rule_duplicate")
        return self

    @property
    def digest(self) -> str:
        return _stable_digest(self.model_dump(mode="json"))


class ClosedRuleEvaluation(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_set_ref: str = Field(min_length=1)
    rule_set_revision: str = Field(min_length=1)
    rule_refs: tuple[str, ...] = Field(min_length=1)
    effect_ref: str = Field(min_length=1)
    owner_mapping: OwnerMapping
    trace_digest: str = Field(min_length=1)


class ClosedEffectResolution(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    effect_ref: str = Field(min_length=1)
    effective_magnitude: int = Field(ge=0)


class RuleEvaluationInput(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trigger_ref: str = Field(min_length=1)
    semantic_snapshot: SemanticSnapshot
    causal_event_ref: str | None = None
    action_intent: ActionIntent | None = None
    pinned_revisions: dict[str, int] = Field(default_factory=dict)
    explicit_time_inputs: dict[str, object] = Field(default_factory=dict)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    causal_chain_id: str = Field(default="chain:root", min_length=1)
    chain_depth: int = Field(default=0, ge=0)
    chain_budget: int = Field(default=1, gt=0)
    requested_trace_scope: Literal["public", "actor", "authority"] = "authority"


class RuleEvaluationTrace(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evaluation_id: str = Field(min_length=1)
    rule_refs: tuple[str, ...] = Field(default_factory=tuple)
    matched_selectors: tuple[str, ...] = Field(default_factory=tuple)
    guard_results: dict[str, bool] = Field(default_factory=dict)
    conflict_decisions: dict[str, str] = Field(default_factory=dict)
    budget_usage: dict[str, int] = Field(default_factory=dict)
    proposal_digests: tuple[str, ...] = Field(default_factory=tuple)
    explanation_visibility: str = Field(min_length=1)
    input_digest: str = Field(min_length=1)
    output_digest: str = Field(min_length=1)
    causal_chain_id: str = Field(min_length=1)
    chain_depth: int = Field(ge=0)


class SemanticRegistry:
    """Revisioned semantic declarations and deterministic rule-trace evaluation."""

    def __init__(self) -> None:
        self._definitions: dict[str, SemanticDefinition] = {}
        self._rules: dict[str, MetaRuleDefinition] = {}
        self._tags: dict[str, TagDefinition] = {}
        self._assignments: dict[str, list[TagAssignment]] = {}
        self._owner_mappings: dict[str, OwnerMapping] = {}
        self._closed_effects: dict[str, ClosedEffectDefinition] = {}
        self._rule_sets: dict[str, RuleSetRevision] = {}
        self._state_lifecycles: dict[str, StateLifecyclePolicy] = {}

    @staticmethod
    def closed_state_lifecycle_adapter_contracts() -> tuple[StateLifecycleAdapterContract, ...]:
        """Return only the semantic adapters that already exist in this runtime."""
        survival_rows = (
            ("effect:cold_exposure", "state:cold"),
            ("effect:dehydration_exposure", "state:dehydrated"),
            ("effect:fatigue_exposure", "state:fatigued"),
            ("effect:heat_exposure", "state:overheated"),
        )
        return (
            StateLifecycleAdapterContract(
                effect_ref="effect:drought",
                state_ref="state:drought@1",
                owner_ref="authority:ecology",
                adapter_ref="SemanticSettlementAuthority.settle_closed_ecology_drought",
                operations=("apply",),
                revision="1",
            ),
            StateLifecycleAdapterContract(
                effect_ref="effect:frost",
                state_ref="state:frosted@1",
                owner_ref="authority:ecology",
                adapter_ref="SemanticSettlementAuthority.settle_closed_ecology_frost",
                operations=("apply",),
                revision="1",
            ),
            StateLifecycleAdapterContract(
                effect_ref="effect:maintenance_required",
                state_ref="state:maintenance_due",
                owner_ref="actor_gameplay.construction_production_domain",
                adapter_ref="SemanticSettlementAuthority.settle_closed_construction_maintenance_state",
                operations=("apply", "expire", "dispel", "cancel"),
                revision="1",
            ),
            *(
                StateLifecycleAdapterContract(
                    effect_ref=effect_ref,
                    state_ref=state_ref,
                    owner_ref="actor_gameplay.survival_domain",
                    adapter_ref="SemanticSettlementAuthority.settle_closed_survival_state",
                    operations=("apply", "expire", "dispel", "transform"),
                    revision="1",
                )
                for effect_ref, state_ref in survival_rows
            ),
        )

    @classmethod
    def require_closed_state_lifecycle_adapter(
        cls, *, effect_ref: str, state_ref: str, operation: str
    ) -> StateLifecycleAdapterContract:
        for contract in cls.closed_state_lifecycle_adapter_contracts():
            if contract.effect_ref == effect_ref and contract.state_ref == state_ref:
                if operation in contract.operations:
                    return contract
                raise SemanticRegistryError("semantic_lifecycle_adapter_operation_unregistered")
        raise SemanticRegistryError("semantic_lifecycle_adapter_unregistered")

    @staticmethod
    def closed_state_owner_contracts() -> tuple[StateOwnerContract, ...]:
        """Return the finite approved matrix; no caller can register a row."""
        survival_definition = {
            ("effect:cold_exposure", "state:cold"): StateDefinition(
                state_ref="state:cold",
                stack_policy="add",
                stack_limit=2,
                expiry_policy="scheduled",
                transform_targets=("state:recovering",),
            ),
            ("effect:heat_exposure", "state:overheated"): StateDefinition(
                state_ref="state:overheated",
                stack_policy="add",
                stack_limit=2,
                expiry_policy="scheduled",
                transform_targets=("state:recovering",),
            ),
            ("effect:dehydration_exposure", "state:dehydrated"): StateDefinition(
                state_ref="state:dehydrated",
                stack_policy="add",
                stack_limit=2,
                expiry_policy="scheduled",
                transform_targets=("state:recovering",),
            ),
            ("effect:fatigue_exposure", "state:fatigued"): StateDefinition(
                state_ref="state:fatigued",
                stack_policy="refresh",
                stack_limit=1,
                expiry_policy="scheduled",
                transform_targets=("state:recovering",),
            ),
        }
        contracts = [
            StateOwnerContract(
                effect_ref=effect_ref,
                state_ref=state_ref,
                owner_ref="actor_gameplay.survival_domain",
                stream_pattern="gameplay:survival:{actor_ref}",
                apply_event_type="gameplay.survival.state_applied",
                opened_event_type="gameplay.survival.obligation_opened",
                expired_event_type="gameplay.survival.state_expired",
                settled_event_type="gameplay.survival.obligation_settled",
                projection_scope="project",
                definition=definition,
                revision="1",
            )
            for (effect_ref, state_ref), definition in survival_definition.items()
        ]
        contracts.extend(
            (
                StateOwnerContract(
                    effect_ref="effect:maintenance_required",
                    state_ref="state:maintenance_due",
                    owner_ref="actor_gameplay.construction_production_domain",
                    stream_pattern="gameplay:construction_production:{facility_ref}",
                    apply_event_type="gameplay.construction_production.maintenance_state_applied",
                    projection_scope="project",
                    definition=StateDefinition(
                        state_ref="state:maintenance_due", stack_policy="replace", stack_limit=1, expiry_policy="none"
                    ),
                    revision="1",
                ),
                StateOwnerContract(
                    effect_ref="effect:drought",
                    state_ref="state:drought@1",
                    owner_ref="authority:ecology",
                    stream_pattern="gameplay:ecology:{region_ref}",
                    apply_event_type="gameplay.ecology.drought_state_applied",
                    opened_event_type="gameplay.ecology.drought_state_obligation_opened",
                    expired_event_type="gameplay.ecology.drought_state_expired",
                    settled_event_type="gameplay.ecology.drought_state_obligation_settled",
                    projection_scope="project",
                    definition=StateDefinition(
                        state_ref="state:drought@1", stack_policy="refresh", stack_limit=1, expiry_policy="scheduled"
                    ),
                    revision="1",
                ),
                StateOwnerContract(
                    effect_ref="effect:frost",
                    state_ref="state:frosted@1",
                    owner_ref="authority:ecology",
                    stream_pattern="gameplay:ecology:{region_ref}",
                    apply_event_type="gameplay.ecology.crop_state_applied",
                    opened_event_type="gameplay.ecology.crop_state_obligation_opened",
                    expired_event_type="gameplay.ecology.crop_state_expired",
                    settled_event_type="gameplay.ecology.crop_state_obligation_settled",
                    projection_scope="project",
                    definition=StateDefinition(
                        state_ref="state:frosted@1", stack_policy="refresh", stack_limit=1, expiry_policy="scheduled"
                    ),
                    revision="1",
                ),
            )
        )
        return tuple(sorted(contracts, key=lambda contract: (contract.effect_ref, contract.state_ref)))

    @classmethod
    def closed_lifecycle_owner_contracts(cls) -> tuple[LifecycleOwnerContract, ...]:
        """Return the finite, existing-owner lifecycle admission surface."""
        state_contracts = {
            (contract.effect_ref, contract.state_ref): contract for contract in cls.closed_state_owner_contracts()
        }
        metadata = {
            ("effect:cold_exposure", "state:cold"): {
                "event_types": (
                    "gameplay.survival.state_applied",
                    "gameplay.survival.obligation_opened",
                    "gameplay.survival.state_expired",
                    "gameplay.survival.obligation_settled",
                    "gameplay.survival.state_dispelled",
                    "gameplay.survival.state_transformed",
                    "gameplay.survival.obligation_cancelled",
                    "gameplay.survival.obligation_retry_scheduled",
                    "gameplay.survival.state_compensated",
                    "gameplay.survival.obligation_compensated",
                ),
                "action_effect_refs": ("effect:state_dispel", "effect:state_transform_recovery"),
                "outbox_topic": "world.survival.scoped_projection",
                "revision_rule": "expected_stream_head_and_semantic_snapshot@1",
                "idempotency_strategy": "command_digest",
                "replay_reader_ref": "ObligationSettlementCoordinator.replay",
            },
            ("effect:dehydration_exposure", "state:dehydrated"): {
                "event_types": (
                    "gameplay.survival.state_applied",
                    "gameplay.survival.obligation_opened",
                    "gameplay.survival.state_expired",
                    "gameplay.survival.obligation_settled",
                    "gameplay.survival.state_dispelled",
                    "gameplay.survival.state_transformed",
                    "gameplay.survival.obligation_cancelled",
                    "gameplay.survival.obligation_retry_scheduled",
                    "gameplay.survival.state_compensated",
                    "gameplay.survival.obligation_compensated",
                ),
                "action_effect_refs": ("effect:state_dispel", "effect:state_transform_recovery"),
                "outbox_topic": "world.survival.scoped_projection",
                "revision_rule": "expected_stream_head_and_semantic_snapshot@1",
                "idempotency_strategy": "command_digest",
                "replay_reader_ref": "ObligationSettlementCoordinator.replay",
            },
            ("effect:fatigue_exposure", "state:fatigued"): {
                "event_types": (
                    "gameplay.survival.state_applied",
                    "gameplay.survival.obligation_opened",
                    "gameplay.survival.state_expired",
                    "gameplay.survival.obligation_settled",
                    "gameplay.survival.state_dispelled",
                    "gameplay.survival.state_transformed",
                    "gameplay.survival.obligation_cancelled",
                    "gameplay.survival.obligation_retry_scheduled",
                    "gameplay.survival.state_compensated",
                    "gameplay.survival.obligation_compensated",
                ),
                "action_effect_refs": ("effect:state_dispel", "effect:state_transform_recovery"),
                "outbox_topic": "world.survival.scoped_projection",
                "revision_rule": "expected_stream_head_and_semantic_snapshot@1",
                "idempotency_strategy": "command_digest",
                "replay_reader_ref": "ObligationSettlementCoordinator.replay",
            },
            ("effect:heat_exposure", "state:overheated"): {
                "event_types": (
                    "gameplay.survival.state_applied",
                    "gameplay.survival.obligation_opened",
                    "gameplay.survival.state_expired",
                    "gameplay.survival.obligation_settled",
                    "gameplay.survival.state_dispelled",
                    "gameplay.survival.state_transformed",
                    "gameplay.survival.obligation_cancelled",
                    "gameplay.survival.obligation_retry_scheduled",
                    "gameplay.survival.state_compensated",
                    "gameplay.survival.obligation_compensated",
                ),
                "action_effect_refs": ("effect:state_dispel", "effect:state_transform_recovery"),
                "outbox_topic": "world.survival.scoped_projection",
                "revision_rule": "expected_stream_head_and_semantic_snapshot@1",
                "idempotency_strategy": "command_digest",
                "replay_reader_ref": "ObligationSettlementCoordinator.replay",
            },
            ("effect:maintenance_required", "state:maintenance_due"): {
                "event_types": (
                    "gameplay.construction_production.maintenance_state_applied",
                    "gameplay.construction_production.maintenance_state_obligation_opened",
                    "gameplay.construction_production.maintenance_state_expired",
                    "gameplay.construction_production.maintenance_state_obligation_settled",
                    "gameplay.construction_production.maintenance_state_dispelled",
                    "gameplay.construction_production.maintenance_state_obligation_cancelled",
                ),
                "action_effect_refs": ("effect:maintenance_state_dispel",),
                "outbox_topic": "construction_production.maintenance_state.scoped_projection",
                "revision_rule": "expected_stream_head_and_canonical_application",
                "idempotency_strategy": "payload_digest",
                "replay_reader_ref": "ConstructionProductionAuthority.projector",
            },
            ("effect:drought", "state:drought@1"): {
                "event_types": (
                    "gameplay.ecology.drought_state_applied",
                    "gameplay.ecology.drought_state_obligation_opened",
                    "gameplay.ecology.drought_state_expired",
                    "gameplay.ecology.drought_state_obligation_settled",
                ),
                "action_effect_refs": (),
                "outbox_topic": "world.ecology.scoped_projection",
                "revision_rule": "expected_stream_head_and_canonical_source",
                "idempotency_strategy": "committed_application_digest",
                "replay_reader_ref": "EcologyHazardAuthority.drought_state_replay",
            },
            ("effect:frost", "state:frosted@1"): {
                "event_types": (
                    "gameplay.ecology.crop_state_applied",
                    "gameplay.ecology.crop_state_obligation_opened",
                    "gameplay.ecology.crop_state_expired",
                    "gameplay.ecology.crop_state_obligation_settled",
                    "gameplay.ecology.crop_state_dispelled",
                    "gameplay.ecology.crop_state_obligation_cancelled",
                ),
                "action_effect_refs": ("effect:ecology_frost_state_dispel",),
                "outbox_topic": "world.ecology.scoped_projection",
                "revision_rule": "expected_stream_head_and_canonical_source",
                "idempotency_strategy": "committed_application_digest",
                "replay_reader_ref": "EcologyHazardAuthority.crop_state_replay",
            },
        }
        contracts = [
            LifecycleOwnerContract(
                effect_ref=state_contract.effect_ref,
                state_ref=state_contract.state_ref,
                owner_ref=state_contract.owner_ref,
                stream_pattern=state_contract.stream_pattern,
                projection_scope=state_contract.projection_scope,
                revision=state_contract.revision,
                **metadata[(state_contract.effect_ref, state_contract.state_ref)],
            )
            for state_contract in state_contracts.values()
        ]
        contracts.append(
            LifecycleOwnerContract(
                effect_ref="effect:wage_accrual_due",
                owner_ref="actor_gameplay.econ1_economy_domain",
                stream_pattern="gameplay:economy:wage:{worker_ref}",
                event_types=(
                    "gameplay.economy.wage_obligation_opened",
                    "gameplay.economy.wage_accrued",
                    "gameplay.economy.wage_obligation_settled",
                    "gameplay.economy.wage_obligation_retry_scheduled",
                    "gameplay.economy.wage_obligation_cancelled",
                    "gameplay.economy.wage_obligation_expired",
                    "gameplay.economy.wage_accrual_compensated",
                    "gameplay.economy.wage_obligation_compensated",
                ),
                projection_scope="project",
                outbox_topic="economy.wage_obligation.scoped_projection",
                revision="1",
                revision_rule="expected_stream_head_and_semantic_snapshot@1",
                idempotency_strategy="command_digest",
                replay_reader_ref="ObligationSettlementCoordinator.replay",
            )
        )
        return tuple(sorted(contracts, key=lambda contract: (contract.effect_ref, contract.state_ref or "")))

    @classmethod
    def require_closed_lifecycle_owner_contract(
        cls, *, effect_ref: str, state_ref: str | None = None
    ) -> LifecycleOwnerContract:
        for contract in cls.closed_lifecycle_owner_contracts():
            if contract.effect_ref == effect_ref and contract.state_ref == state_ref:
                return contract
        raise SemanticRegistryError("semantic_lifecycle_owner_contract_unknown")

    @classmethod
    def require_closed_state_owner_contract(cls, *, effect_ref: str, state_ref: str) -> StateOwnerContract:
        try:
            cls.require_closed_lifecycle_owner_contract(effect_ref=effect_ref, state_ref=state_ref)
        except SemanticRegistryError as exc:
            raise SemanticRegistryError("semantic_state_owner_contract_unknown") from exc
        for contract in cls.closed_state_owner_contracts():
            if contract.effect_ref == effect_ref and contract.state_ref == state_ref:
                return contract
        raise SemanticRegistryError("semantic_state_owner_contract_unknown")

    @classmethod
    def require_closed_survival_state_action_contract(cls, *, state_ref: str) -> StateOwnerContract:
        lifecycle = cls.require_closed_lifecycle_owner_contract(
            effect_ref={
                "state:cold": "effect:cold_exposure",
                "state:overheated": "effect:heat_exposure",
                "state:dehydrated": "effect:dehydration_exposure",
                "state:fatigued": "effect:fatigue_exposure",
            }.get(state_ref, ""),
            state_ref=state_ref,
        )
        if "effect:state_dispel" not in lifecycle.action_effect_refs:
            raise SemanticRegistryError("semantic_survival_state_action_contract_unknown")
        for contract in cls.closed_state_owner_contracts():
            if contract.state_ref == state_ref and contract.owner_ref == "actor_gameplay.survival_domain":
                return contract
        raise SemanticRegistryError("semantic_survival_state_action_contract_unknown")

    def register_owner_mapping(self, mapping: OwnerMapping) -> None:
        existing = self._owner_mappings.get(mapping.effect_ref)
        if existing is not None:
            if existing == mapping:
                raise SemanticRegistryError("semantic_owner_mapping_duplicate")
            raise SemanticRegistryError("semantic_owner_mapping_conflict")
        production_row = (
            mapping.effect_ref == "effect:production_due_finish"
            and mapping.owner_ref == "actor_gameplay.construction_production_domain"
            and mapping.stream_pattern == "gameplay:construction_production:{facility_ref}"
            and mapping.event_type == "gameplay.construction_production.run_finished"
            and mapping.fragment_builder_ref == "ConstructionProductionAuthority.build_due_finish_fragment"
            and mapping.projection_scope == "project"
            and mapping.revision == "1"
        )
        wage_row = (
            mapping.effect_ref == "effect:wage_accrual_due"
            and mapping.owner_ref == "actor_gameplay.econ1_economy_domain"
            and mapping.stream_pattern == "gameplay:economy:wage:{worker_ref}"
            and mapping.event_type == "gameplay.economy.wage_obligation_opened"
            and mapping.fragment_builder_ref == "EconomyAuthority.open_wage_obligation"
            and mapping.projection_scope == "project"
            and mapping.revision == "1"
        )
        survival_state_action_row = (
            mapping.effect_ref in {"effect:state_dispel", "effect:state_transform_recovery"}
            and mapping.owner_ref == "actor_gameplay.survival_domain"
            and mapping.stream_pattern == "gameplay:survival:{actor_ref}"
            and mapping.projection_scope == "project"
            and mapping.revision == "1"
            and (
                (
                    mapping.effect_ref == "effect:state_dispel"
                    and mapping.event_type == "gameplay.survival.state_dispelled"
                    and mapping.fragment_builder_ref == "SurvivalAuthority.build_state_dispel_fragment"
                )
                or (
                    mapping.effect_ref == "effect:state_transform_recovery"
                    and mapping.event_type == "gameplay.survival.state_transformed"
                    and mapping.fragment_builder_ref == "SurvivalAuthority.build_state_transform_fragment"
                )
            )
        )
        construction_maintenance_state_action_row = (
            mapping.effect_ref == "effect:maintenance_state_dispel"
            and mapping.owner_ref == "actor_gameplay.construction_production_domain"
            and mapping.stream_pattern == "gameplay:construction_production:{facility_ref}"
            and mapping.event_type == "gameplay.construction_production.maintenance_state_dispelled"
            and mapping.fragment_builder_ref == "ConstructionProductionAuthority.build_maintenance_state_dispel_fragment"
            and mapping.projection_scope == "project"
            and mapping.revision == "1"
        )
        if (
            not production_row
            and not wage_row
            and not survival_state_action_row
            and not construction_maintenance_state_action_row
        ):
            raise SemanticRegistryError("semantic_owner_mapping_unregistered")
        self._owner_mappings[mapping.effect_ref] = mapping

    def owner_mapping(self, effect_ref: str) -> OwnerMapping:
        try:
            return self._owner_mappings[effect_ref]
        except KeyError as exc:
            raise SemanticRegistryError("semantic_owner_mapping_unknown") from exc

    def owner_mappings(self) -> tuple[OwnerMapping, ...]:
        return tuple(self._owner_mappings[key] for key in sorted(self._owner_mappings))

    def register_closed_effect(self, definition: ClosedEffectDefinition) -> None:
        if definition.effect_ref not in self._owner_mappings:
            raise SemanticRegistryError("semantic_owner_mapping_unknown")
        existing = self._closed_effects.get(definition.effect_ref)
        if existing is not None:
            if existing == definition:
                raise SemanticRegistryError("semantic_closed_effect_duplicate")
            raise SemanticRegistryError("semantic_closed_effect_conflict")
        self._closed_effects[definition.effect_ref] = definition

    def register_wage_accrual_due_effect(self) -> None:
        """Register the sole admitted semantic effect row for the existing wage owner."""
        self.register_owner_mapping(
            OwnerMapping(
                effect_ref="effect:wage_accrual_due",
                owner_ref="actor_gameplay.econ1_economy_domain",
                stream_pattern="gameplay:economy:wage:{worker_ref}",
                event_type="gameplay.economy.wage_obligation_opened",
                fragment_builder_ref="EconomyAuthority.open_wage_obligation",
                projection_scope="project",
                revision="1",
            )
        )
        self.register_closed_effect(
            ClosedEffectDefinition(
                effect_ref="effect:wage_accrual_due",
                input_schema_ref="schema:economy-wage-obligation:v1",
                stack_policy="one_shot",
                revision="1",
            )
        )

    def register_survival_state_action_effects(self) -> None:
        """Register the two closed state actions for the existing Survival owner."""
        for effect_ref, event_type, fragment_builder_ref, schema_ref in (
            (
                "effect:state_dispel",
                "gameplay.survival.state_dispelled",
                "SurvivalAuthority.build_state_dispel_fragment",
                "schema:survival-state-dispel:v1",
            ),
            (
                "effect:state_transform_recovery",
                "gameplay.survival.state_transformed",
                "SurvivalAuthority.build_state_transform_fragment",
                "schema:survival-state-transform-recovery:v1",
            ),
        ):
            self.register_owner_mapping(
                OwnerMapping(
                    effect_ref=effect_ref,
                    owner_ref="actor_gameplay.survival_domain",
                    stream_pattern="gameplay:survival:{actor_ref}",
                    event_type=event_type,
                    fragment_builder_ref=fragment_builder_ref,
                    projection_scope="project",
                    revision="1",
                )
            )
            self.register_closed_effect(
                ClosedEffectDefinition(
                    effect_ref=effect_ref,
                    input_schema_ref=schema_ref,
                    stack_policy="one_shot",
                    revision="1",
                )
            )

    def register_construction_maintenance_state_action_effect(self) -> None:
        """Register the sole maintenance state dispel action for the existing Construction owner."""
        self.register_owner_mapping(
            OwnerMapping(
                effect_ref="effect:maintenance_state_dispel",
                owner_ref="actor_gameplay.construction_production_domain",
                stream_pattern="gameplay:construction_production:{facility_ref}",
                event_type="gameplay.construction_production.maintenance_state_dispelled",
                fragment_builder_ref="ConstructionProductionAuthority.build_maintenance_state_dispel_fragment",
                projection_scope="project",
                revision="1",
            )
        )
        self.register_closed_effect(
            ClosedEffectDefinition(
                effect_ref="effect:maintenance_state_dispel",
                input_schema_ref="schema:construction-maintenance-state-dispel:v1",
                stack_policy="one_shot",
                revision="1",
            )
        )

    def register_state_lifecycle(self, policy: StateLifecyclePolicy) -> None:
        if policy.lifecycle == "scheduled" and not self._is_registered_scheduled_lifecycle(policy):
            raise SemanticRegistryError("semantic_lifecycle_owner_unregistered")
        existing = self._state_lifecycles.get(policy.state_ref)
        if existing is not None:
            if existing == policy:
                raise SemanticRegistryError("semantic_state_lifecycle_duplicate")
            raise SemanticRegistryError("semantic_state_lifecycle_conflict")
        self._state_lifecycles[policy.state_ref] = policy

    def state_lifecycle(self, state_ref: str) -> StateLifecyclePolicy:
        try:
            return self._state_lifecycles[state_ref]
        except KeyError as exc:
            raise SemanticRegistryError("semantic_state_lifecycle_unknown") from exc

    def scheduled_state_owner_row(self, *, state_ref: str, effect_ref: str) -> StateLifecyclePolicy:
        policy = self.state_lifecycle(state_ref)
        if policy.lifecycle != "scheduled" or policy.effect_ref != effect_ref:
            raise SemanticRegistryError("semantic_state_effect_mapping_unregistered")
        return policy

    def scheduled_state_definition(self, *, state_ref: str, effect_ref: str) -> StateDefinition:
        self.scheduled_state_owner_row(state_ref=state_ref, effect_ref=effect_ref)
        definitions = {
            ("state:cold", "effect:cold_exposure"): StateDefinition(
                state_ref="state:cold",
                stack_policy="add",
                stack_limit=2,
                expiry_policy="scheduled",
                transform_targets=("state:recovering",),
            ),
            ("state:overheated", "effect:heat_exposure"): StateDefinition(
                state_ref="state:overheated",
                stack_policy="add",
                stack_limit=2,
                expiry_policy="scheduled",
                transform_targets=("state:recovering",),
            ),
            ("state:dehydrated", "effect:dehydration_exposure"): StateDefinition(
                state_ref="state:dehydrated",
                stack_policy="add",
                stack_limit=2,
                expiry_policy="scheduled",
                transform_targets=("state:recovering",),
            ),
            ("state:fatigued", "effect:fatigue_exposure"): StateDefinition(
                state_ref="state:fatigued",
                stack_policy="refresh",
                stack_limit=1,
                expiry_policy="scheduled",
                transform_targets=("state:recovering",),
            ),
        }
        try:
            return definitions[(state_ref, effect_ref)]
        except KeyError as exc:
            raise SemanticRegistryError("semantic_state_effect_mapping_unregistered") from exc

    def registered_state_owner_rows(self) -> tuple[StateOwnerRow, ...]:
        rows: list[StateOwnerRow] = []
        for state_ref, effect_ref in (
            ("state:cold", "effect:cold_exposure"),
            ("state:dehydrated", "effect:dehydration_exposure"),
            ("state:fatigued", "effect:fatigue_exposure"),
            ("state:overheated", "effect:heat_exposure"),
        ):
            policy = self._state_lifecycles.get(state_ref)
            if policy is None or not self._is_registered_scheduled_lifecycle(policy):
                continue
            rows.append(
                StateOwnerRow(
                    state_ref=state_ref,
                    effect_ref=effect_ref,
                    owner_ref=policy.owner_ref or "",
                    stream_pattern=policy.stream_pattern or "",
                    event_type="gameplay.survival.state_applied",
                    projection_scope="project",
                    definition=self.scheduled_state_definition(state_ref=state_ref, effect_ref=effect_ref),
                    revision=policy.revision,
                )
            )
        rows.append(
            StateOwnerRow(
                state_ref="state:maintenance_due",
                effect_ref="effect:maintenance_required",
                owner_ref="actor_gameplay.construction_production_domain",
                stream_pattern="gameplay:construction_production:{facility_ref}",
                event_type="gameplay.construction_production.maintenance_state_applied",
                projection_scope="project",
                definition=StateDefinition(
                    state_ref="state:maintenance_due",
                    stack_policy="replace",
                    stack_limit=1,
                    expiry_policy="none",
                ),
                revision="1",
            )
        )
        rows.extend(
            (
                StateOwnerRow(
                    state_ref="state:drought@1",
                    effect_ref="effect:drought",
                    owner_ref="authority:ecology",
                    stream_pattern="gameplay:ecology:{region_ref}",
                    event_type="gameplay.ecology.drought_state_applied",
                    projection_scope="project",
                    definition=StateDefinition(
                        state_ref="state:drought@1",
                        stack_policy="refresh",
                        stack_limit=1,
                        expiry_policy="scheduled",
                    ),
                    revision="1",
                ),
                StateOwnerRow(
                    state_ref="state:frosted@1",
                    effect_ref="effect:frost",
                    owner_ref="authority:ecology",
                    stream_pattern="gameplay:ecology:{region_ref}",
                    event_type="gameplay.ecology.crop_state_applied",
                    projection_scope="project",
                    definition=StateDefinition(
                        state_ref="state:frosted@1",
                        stack_policy="refresh",
                        stack_limit=1,
                        expiry_policy="scheduled",
                    ),
                    revision="1",
                ),
            )
        )
        return tuple(sorted(rows, key=lambda row: (row.state_ref, row.effect_ref)))

    def registered_state_owner_row(self, *, state_ref: str, effect_ref: str) -> StateOwnerRow:
        for row in self.registered_state_owner_rows():
            if row.state_ref == state_ref and row.effect_ref == effect_ref:
                return row
        raise SemanticRegistryError("semantic_state_effect_mapping_unregistered")

    def registered_effect_owner_route(self, *, effect_ref: str) -> RegisteredEffectOwnerRoute:
        mapping = self._owner_mappings.get(effect_ref)
        definition = self._closed_effects.get(effect_ref)
        if mapping is None or definition is None:
            raise SemanticRegistryError("semantic_effect_owner_route_unknown")
        if (
            mapping.effect_ref != "effect:wage_accrual_due"
            or mapping.owner_ref != "actor_gameplay.econ1_economy_domain"
            or mapping.stream_pattern != "gameplay:economy:wage:{worker_ref}"
            or mapping.event_type != "gameplay.economy.wage_obligation_opened"
            or mapping.fragment_builder_ref != "EconomyAuthority.open_wage_obligation"
            or mapping.projection_scope != "project"
            or mapping.revision != "1"
            or definition.effect_ref != mapping.effect_ref
            or definition.input_schema_ref != "schema:economy-wage-obligation:v1"
            or definition.stack_policy != "one_shot"
            or definition.revision != mapping.revision
        ):
            raise SemanticRegistryError("semantic_effect_owner_route_unknown")
        lifecycle = self.require_closed_lifecycle_owner_contract(effect_ref=effect_ref)
        if (
            lifecycle.owner_ref != mapping.owner_ref
            or lifecycle.stream_pattern != mapping.stream_pattern
            or lifecycle.projection_scope != mapping.projection_scope
            or mapping.event_type not in lifecycle.event_types
        ):
            raise SemanticRegistryError("semantic_effect_owner_route_unknown")
        return RegisteredEffectOwnerRoute(
            effect_ref=mapping.effect_ref,
            owner_ref=mapping.owner_ref,
            stream_pattern=mapping.stream_pattern,
            opened_event_type=mapping.event_type,
            adapter_ref="SemanticSettlementAuthority.settle_registered_wage_obligation",
            projection_scope=mapping.projection_scope,
            revision=mapping.revision,
        )

    def registered_survival_state_action_route(self, *, effect_ref: str) -> RegisteredSurvivalStateActionRoute:
        mapping = self._owner_mappings.get(effect_ref)
        definition = self._closed_effects.get(effect_ref)
        expected = {
            "effect:state_dispel": (
                "gameplay.survival.state_dispelled",
                "SurvivalAuthority.build_state_dispel_fragment",
                "schema:survival-state-dispel:v1",
            ),
            "effect:state_transform_recovery": (
                "gameplay.survival.state_transformed",
                "SurvivalAuthority.build_state_transform_fragment",
                "schema:survival-state-transform-recovery:v1",
            ),
        }.get(effect_ref)
        if (
            mapping is None
            or definition is None
            or expected is None
            or mapping.owner_ref != "actor_gameplay.survival_domain"
            or mapping.stream_pattern != "gameplay:survival:{actor_ref}"
            or mapping.event_type != expected[0]
            or mapping.fragment_builder_ref != expected[1]
            or mapping.projection_scope != "project"
            or mapping.revision != "1"
            or definition.effect_ref != effect_ref
            or definition.input_schema_ref != expected[2]
            or definition.stack_policy != "one_shot"
            or definition.revision != mapping.revision
        ):
            raise SemanticRegistryError("semantic_survival_state_action_route_unknown")
        return RegisteredSurvivalStateActionRoute(
            effect_ref=effect_ref,
            owner_ref="actor_gameplay.survival_domain",
            source_state_refs=("state:cold", "state:overheated", "state:dehydrated", "state:fatigued"),
            stream_pattern="gameplay:survival:{actor_ref}",
            event_type=expected[0],
            adapter_ref="SemanticSettlementAuthority.settle_registered_survival_state_action",
            projection_scope="project",
            revision="1",
        )

    def registered_construction_maintenance_state_action_route(
        self, *, effect_ref: str
    ) -> RegisteredConstructionMaintenanceStateActionRoute:
        mapping = self._owner_mappings.get(effect_ref)
        definition = self._closed_effects.get(effect_ref)
        if (
            mapping is None
            or definition is None
            or effect_ref != "effect:maintenance_state_dispel"
            or mapping.owner_ref != "actor_gameplay.construction_production_domain"
            or mapping.stream_pattern != "gameplay:construction_production:{facility_ref}"
            or mapping.event_type != "gameplay.construction_production.maintenance_state_dispelled"
            or mapping.fragment_builder_ref != "ConstructionProductionAuthority.build_maintenance_state_dispel_fragment"
            or mapping.projection_scope != "project"
            or mapping.revision != "1"
            or definition.effect_ref != effect_ref
            or definition.input_schema_ref != "schema:construction-maintenance-state-dispel:v1"
            or definition.stack_policy != "one_shot"
            or definition.revision != mapping.revision
        ):
            raise SemanticRegistryError("semantic_construction_maintenance_state_action_route_unknown")
        lifecycle = self.require_closed_lifecycle_owner_contract(
            effect_ref="effect:maintenance_required",
            state_ref="state:maintenance_due",
        )
        if effect_ref not in lifecycle.action_effect_refs:
            raise SemanticRegistryError("semantic_construction_maintenance_state_action_route_unknown")
        return RegisteredConstructionMaintenanceStateActionRoute(
            effect_ref="effect:maintenance_state_dispel",
            owner_ref="actor_gameplay.construction_production_domain",
            state_ref="state:maintenance_due",
            stream_pattern="gameplay:construction_production:{facility_ref}",
            event_type="gameplay.construction_production.maintenance_state_dispelled",
            adapter_ref="SemanticSettlementAuthority.settle_registered_construction_maintenance_state_action",
            projection_scope="project",
            revision="1",
        )

    def scheduled_state_owner_rows(self) -> tuple[StateLifecyclePolicy, ...]:
        return tuple(
            policy
            for _state_ref, policy in sorted(self._state_lifecycles.items())
            if policy.lifecycle == "scheduled" and policy.effect_ref is not None
        )

    def registered_state_owner_route(self, *, state_ref: str, effect_ref: str) -> RegisteredStateOwnerRoute:
        row = self.registered_state_owner_row(state_ref=state_ref, effect_ref=effect_ref)
        lifecycle = self.require_closed_lifecycle_owner_contract(effect_ref=effect_ref, state_ref=state_ref)
        adapter = self.require_closed_state_lifecycle_adapter(
            effect_ref=effect_ref,
            state_ref=state_ref,
            operation="apply",
        )
        if (
            lifecycle.owner_ref != row.owner_ref
            or lifecycle.stream_pattern != row.stream_pattern
            or lifecycle.projection_scope != row.projection_scope
            or row.event_type not in lifecycle.event_types
            or adapter.owner_ref != row.owner_ref
            or adapter.revision != row.revision
        ):
            raise SemanticRegistryError("semantic_state_effect_mapping_unregistered")
        if row.owner_ref == "actor_gameplay.construction_production_domain":
            if adapter.adapter_ref != "SemanticSettlementAuthority.settle_closed_construction_maintenance_state":
                raise SemanticRegistryError("semantic_registered_state_route_unknown")
            return RegisteredStateOwnerRoute(
                state_ref=state_ref,
                effect_ref=effect_ref,
                owner_ref=row.owner_ref,
                stream_pattern=row.stream_pattern,
                adapter_ref="SemanticSettlementAuthority.settle_closed_construction_maintenance_state",
                projection_scope=row.projection_scope,
                revision=row.revision,
            )
        if row.owner_ref == "authority:ecology":
            if adapter.adapter_ref not in {
                "SemanticSettlementAuthority.settle_closed_ecology_frost",
                "SemanticSettlementAuthority.settle_closed_ecology_drought",
            }:
                raise SemanticRegistryError("semantic_registered_state_route_unknown")
            return RegisteredStateOwnerRoute(
                state_ref=state_ref,
                effect_ref=effect_ref,
                owner_ref=row.owner_ref,
                stream_pattern=row.stream_pattern,
                adapter_ref=adapter.adapter_ref,
                projection_scope=row.projection_scope,
                revision=row.revision,
            )
        if row.owner_ref != "actor_gameplay.survival_domain":
            raise SemanticRegistryError("semantic_registered_state_route_unknown")
        if adapter.adapter_ref != "SemanticSettlementAuthority.settle_closed_survival_state":
            raise SemanticRegistryError("semantic_registered_state_route_unknown")
        return RegisteredStateOwnerRoute(
            state_ref=state_ref,
            effect_ref=effect_ref,
            owner_ref=row.owner_ref,
            stream_pattern=row.stream_pattern,
            adapter_ref="SemanticSettlementAuthority.settle_closed_survival_state",
            projection_scope=row.projection_scope,
            revision=row.revision,
        )

    def construction_maintenance_owner_row(self, *, state_ref: str, effect_ref: str) -> StateOwnerRow:
        row = StateOwnerRow(
            state_ref="state:maintenance_due",
            effect_ref="effect:maintenance_required",
            owner_ref="actor_gameplay.construction_production_domain",
            stream_pattern="gameplay:construction_production:{facility_ref}",
            event_type="gameplay.construction_production.maintenance_state_applied",
            projection_scope="project",
            definition=StateDefinition(
                state_ref="state:maintenance_due",
                stack_policy="replace",
                stack_limit=1,
                expiry_policy="none",
            ),
            revision="1",
        )
        if row.state_ref != state_ref or row.effect_ref != effect_ref:
            raise SemanticRegistryError("semantic_state_effect_mapping_unregistered")
        return row

    def require_closed_semantic_source_vector(self, snapshot: SemanticSnapshot) -> None:
        if snapshot.source_revision_vector != {"semantic": 1}:
            raise SemanticRegistryError("semantic_closed_registry_revision_mismatch")

    @staticmethod
    def _is_registered_scheduled_lifecycle(policy: StateLifecyclePolicy) -> bool:
        return (
            (policy.state_ref, policy.effect_ref) in {
                ("state:cold", "effect:cold_exposure"),
                ("state:overheated", "effect:heat_exposure"),
                ("state:dehydrated", "effect:dehydration_exposure"),
                ("state:fatigued", "effect:fatigue_exposure"),
            }
            and policy.revision == "1"
            and policy.owner_ref == "actor_gameplay.survival_domain"
            and policy.stream_pattern == "gameplay:survival:{actor_ref}"
            and policy.opened_event_type == "gameplay.survival.obligation_opened"
            and policy.settled_event_type == "gameplay.survival.obligation_settled"
            and policy.cancelled_event_type == "gameplay.survival.obligation_cancelled"
            and policy.fragment_builder_ref == "SurvivalAuthority.build_state_expiry_fragment"
            and policy.projection_scope == "project"
        )

    def resolve_closed_effect(
        self, *, effect_ref: str, magnitude: int, resistance_basis_points: int
    ) -> ClosedEffectResolution:
        if effect_ref not in self._closed_effects or effect_ref not in self._owner_mappings:
            raise SemanticRegistryError("semantic_owner_mapping_unknown")
        if magnitude < 0 or not 0 <= resistance_basis_points <= 10_000:
            raise SemanticRegistryError("semantic_closed_effect_input_invalid")
        return ClosedEffectResolution(
            effect_ref=effect_ref,
            effective_magnitude=magnitude * (10_000 - resistance_basis_points) // 10_000,
        )

    def register_rule_set(self, rule_set: RuleSetRevision) -> None:
        existing = self._rule_sets.get(rule_set.rule_set_ref)
        if existing is not None:
            if existing == rule_set:
                raise SemanticRegistryError("semantic_closed_rule_set_duplicate")
            raise SemanticRegistryError("semantic_closed_rule_set_conflict")
        for rule in rule_set.rules:
            if rule.effect_ref not in self._closed_effects or rule.owner_mapping_ref != rule.effect_ref:
                raise SemanticRegistryError("semantic_closed_rule_owner_mapping_unknown")
        self._rule_sets[rule_set.rule_set_ref] = rule_set

    def rule_set(self, rule_set_ref: str) -> RuleSetRevision:
        try:
            return self._rule_sets[rule_set_ref]
        except KeyError as exc:
            raise SemanticRegistryError("semantic_closed_rule_set_unknown") from exc

    def evaluate_closed_rule_set(
        self, *, rule_set_ref: str, effect_ref: str, target_ref: str, semantic_snapshot_digest: str
    ) -> ClosedRuleEvaluation:
        rule_set = self.rule_set(rule_set_ref)
        mapping = self.owner_mapping(effect_ref)
        candidates = tuple(
            sorted(
                (rule for rule in rule_set.rules if rule.effect_ref == effect_ref),
                key=lambda rule: (rule.phase, -rule.priority, -rule.specificity, rule.rule_ref),
            )
        )
        rules = self._resolve_closed_conflicts(candidates)
        if not rules:
            raise SemanticRegistryError("semantic_closed_rule_suppressed")
        payload = {
            "rule_set_ref": rule_set.rule_set_ref,
            "rule_set_revision": rule_set.revision,
            "rule_refs": [rule.rule_ref for rule in rules],
            "effect_ref": effect_ref,
            "target_ref": target_ref,
            "semantic_snapshot_digest": semantic_snapshot_digest,
            "owner_mapping": mapping.model_dump(mode="json"),
        }
        return ClosedRuleEvaluation(
            rule_set_ref=rule_set.rule_set_ref,
            rule_set_revision=rule_set.revision,
            rule_refs=tuple(rule.rule_ref for rule in rules),
            effect_ref=effect_ref,
            owner_mapping=mapping,
            trace_digest=_stable_digest(payload),
        )

    @staticmethod
    def _resolve_closed_conflicts(rules: tuple[ClosedRuleDefinition, ...]) -> tuple[ClosedRuleDefinition, ...]:
        if not rules:
            return ()
        lead = rules[0]
        if lead.conflict_policy == "reject":
            raise SemanticRegistryError("semantic_closed_rule_conflict_rejected")
        if lead.conflict_policy == "suppress":
            return ()
        if lead.conflict_policy == "additive":
            return tuple(rule for rule in rules if rule.conflict_policy == "additive")
        return (lead,)

    @staticmethod
    def project_closed_trace(
        evaluation: ClosedRuleEvaluation, *, scope: Literal["public", "actor", "creator", "authority"]
    ) -> dict[str, object]:
        """Trace views never alter the frozen evaluation or expose owner metadata."""
        if scope == "authority":
            return {
                "rule_set_ref": evaluation.rule_set_ref,
                "rule_set_revision": evaluation.rule_set_revision,
                "rule_refs": evaluation.rule_refs,
                "effect_ref": evaluation.effect_ref,
                "trace_digest": evaluation.trace_digest,
            }
        return {
            "rule_set_ref": evaluation.rule_set_ref,
            "rule_set_revision": evaluation.rule_set_revision,
            "rule_refs": (),
            "effect_ref": evaluation.effect_ref,
            "trace_digest": evaluation.trace_digest,
        }

    def register_tag(self, definition: TagDefinition) -> None:
        existing = self._tags.get(definition.tag_ref)
        if existing is not None:
            if existing != definition:
                raise SemanticRegistryError("semantic_tag_definition_conflict")
            raise SemanticRegistryError("semantic_tag_definition_duplicate")
        if definition.tag_ref in definition.parent_refs:
            raise SemanticRegistryError("semantic_tag_parent_cycle")
        for parent_ref in definition.parent_refs:
            if parent_ref in self._tags and self._would_create_tag_cycle(definition.tag_ref, parent_ref):
                raise SemanticRegistryError("semantic_tag_parent_cycle")
        self._tags[definition.tag_ref] = definition
        try:
            self._validate_tag_graph()
        except SemanticRegistryError:
            self._tags.pop(definition.tag_ref, None)
            raise

    def assign_tag(self, assignment: TagAssignment) -> None:
        self._require_tag(assignment.tag_ref)
        definition = self._tags[assignment.tag_ref]
        unknown = set(assignment.parameter_values) - set(definition.parameter_schema)
        if unknown:
            raise SemanticRegistryError("semantic_tag_parameter_unknown")
        assignments = self._assignments.setdefault(assignment.entity_ref, [])
        if any(existing == assignment for existing in assignments):
            raise SemanticRegistryError("semantic_tag_assignment_duplicate")
        if any(
            existing.tag_ref == assignment.tag_ref
            and existing.component_ref == assignment.component_ref
            and existing.parameter_values != assignment.parameter_values
            for existing in assignments
        ):
            raise SemanticRegistryError("semantic_tag_assignment_conflict")
        assignments.append(assignment)
        assignments.sort(key=lambda item: (item.component_ref or "", item.tag_ref, item.source_ref, item.revision))

    def build_snapshot(
        self,
        entity_ref: str,
        *,
        component_refs: Iterable[str] = (),
        statuses: Iterable[str] = (),
        relation_refs: Iterable[str] = (),
        policy_context_ref: str = "policy:default",
        source_revision_vector: dict[str, int] | None = None,
    ) -> SemanticSnapshot:
        assignments = tuple(self._assignments.get(entity_ref, ()))
        resolved_tags: set[str] = set()
        parameters: dict[str, object] = {}
        parameter_specificities: dict[str, int] = {}
        components = set(component_refs)
        for assignment in assignments:
            if assignment.component_ref is not None:
                components.add(assignment.component_ref)
            for tag_ref in self._expanded_tags(assignment.tag_ref):
                resolved_tags.add(tag_ref)
            self._merge_parameters(parameters, parameter_specificities, assignment)
        payload = {
            "entity_ref": entity_ref,
            "component_refs": sorted(components),
            "resolved_tags": sorted(resolved_tags),
            "resolved_parameters": parameters,
            "statuses": sorted(set(statuses)),
            "relation_refs": sorted(set(relation_refs)),
            "policy_context_ref": policy_context_ref,
            "source_revision_vector": dict(sorted((source_revision_vector or {}).items())),
        }
        return SemanticSnapshot(**payload, digest=_stable_digest(payload))

    def select(self, snapshots: Iterable[SemanticSnapshot], selector: SemanticSelector) -> tuple[SemanticSnapshot, ...]:
        selected = [snapshot for snapshot in snapshots if self._selector_matches_snapshot(snapshot, selector)]
        return tuple(sorted(selected, key=lambda item: item.entity_ref))

    def _require_tag(self, tag_ref: str) -> TagDefinition:
        try:
            return self._tags[tag_ref]
        except KeyError as exc:
            raise SemanticRegistryError("semantic_tag_unknown") from exc

    def _expanded_tags(self, tag_ref: str) -> tuple[str, ...]:
        visited: set[str] = set()
        ordered: list[str] = []

        def visit(current: str) -> None:
            if current in visited:
                return
            definition = self._require_tag(current)
            for parent in sorted(definition.parent_refs):
                visit(parent)
            visited.add(current)
            ordered.append(current)

        visit(tag_ref)
        return tuple(ordered)

    def _merge_parameters(self, target: dict[str, object], specificities: dict[str, int], assignment: TagAssignment) -> None:
        definition = self._tags[assignment.tag_ref]
        for key, value in assignment.parameter_values.items():
            if key not in target:
                target[key] = value
                specificities[key] = definition.specificity
                continue
            policy = definition.merge_policy
            previous = target[key]
            if policy == "replace_by_specificity":
                if definition.specificity == specificities[key] and previous != value:
                    raise SemanticRegistryError("semantic_parameter_conflict")
                if definition.specificity >= specificities[key]:
                    target[key] = value
                    specificities[key] = definition.specificity
            elif policy == "additive":
                if not isinstance(previous, (int, float)) or not isinstance(value, (int, float)):
                    raise SemanticRegistryError("semantic_parameter_conflict")
                target[key] = previous + value
            elif policy == "minimum":
                target[key] = min(previous, value)
            elif policy == "maximum":
                target[key] = max(previous, value)
            elif policy == "exclusive":
                if previous != value:
                    raise SemanticRegistryError("semantic_parameter_conflict")
            elif policy == "compose":
                existing = previous if isinstance(previous, list) else [previous]
                target[key] = [*existing, value]

    def _selector_matches_snapshot(self, snapshot: SemanticSnapshot, selector: SemanticSelector) -> bool:
        tags = set(snapshot.resolved_tags)
        inferred_kind = snapshot.entity_ref.split(":", 1)[0]
        if selector.entity_kind is not None and selector.entity_kind != inferred_kind:
            return False
        if selector.require_all_tags and not set(selector.require_all_tags).issubset(tags):
            return False
        if selector.require_any_tags and not tags.intersection(selector.require_any_tags):
            return False
        if set(selector.exclude_tags).intersection(tags):
            return False
        if selector.component_scope and selector.component_scope not in snapshot.component_refs:
            return False
        if selector.status_predicates and not set(selector.status_predicates).issubset(snapshot.statuses):
            return False
        if selector.relation_predicates and not set(selector.relation_predicates).issubset(snapshot.relation_refs):
            return False
        return all(self._parameter_matches(snapshot.resolved_parameters.get(key), predicate) for key, predicate in selector.parameter_predicates.items())

    @staticmethod
    def _parameter_matches(actual: object, predicate: object) -> bool:
        if isinstance(predicate, dict):
            for operator, expected in predicate.items():
                if operator == "eq" and actual != expected:
                    return False
                if operator == "gte" and not (actual is not None and actual >= expected):
                    return False
                if operator == "lte" and not (actual is not None and actual <= expected):
                    return False
                if operator == "in" and actual not in expected:
                    return False
            return True
        return actual == predicate

    def _would_create_tag_cycle(self, tag_ref: str, parent_ref: str) -> bool:
        def reaches_target(current: str, visited: set[str]) -> bool:
            if current == tag_ref:
                return True
            if current in visited or current not in self._tags:
                return False
            visited.add(current)
            return any(reaches_target(parent, visited) for parent in self._tags[current].parent_refs)

        return reaches_target(parent_ref, set())

    def _validate_tag_graph(self) -> None:
        for definition in self._tags.values():
            for parent in definition.parent_refs:
                if parent not in self._tags:
                    continue
                if self._would_create_tag_cycle(definition.tag_ref, parent):
                    raise SemanticRegistryError("semantic_tag_parent_cycle")

    def register(self, definition: SemanticDefinition) -> None:
        existing = self._definitions.get(definition.semantic_id)
        if existing is not None:
            if existing.namespace != definition.namespace:
                raise SemanticRegistryError("semantic_namespace_collision")
            if existing != definition:
                raise SemanticRegistryError("semantic_definition_conflict")
            raise SemanticRegistryError("semantic_definition_duplicate")
        self._definitions[definition.semantic_id] = definition

    def register_meta_rule(self, definition: MetaRuleDefinition) -> None:
        existing = self._rules.get(definition.rule_ref)
        if existing is not None:
            if existing != definition:
                raise SemanticRegistryError("semantic_meta_rule_conflict")
            raise SemanticRegistryError("semantic_meta_rule_duplicate")
        self._rules[definition.rule_ref] = definition

    def get(self, semantic_id: str) -> SemanticDefinition:
        try:
            return self._definitions[semantic_id]
        except KeyError as exc:
            raise SemanticRegistryError("semantic_definition_unknown") from exc

    def get_meta_rule(self, rule_ref: str) -> MetaRuleDefinition:
        try:
            return self._rules[rule_ref]
        except KeyError as exc:
            raise SemanticRegistryError("semantic_meta_rule_unknown") from exc

    def evaluate(self, evaluation: RuleEvaluationInput) -> RuleEvaluationTrace:
        input_digest = _stable_digest(evaluation.model_dump(mode="json"))
        if evaluation.chain_depth >= evaluation.chain_budget:
            raise SemanticRegistryError("semantic_chain_budget_exhausted")
        self._ensure_snapshot_semantics_known(evaluation.semantic_snapshot)
        matched_rules = self._matched_rules(evaluation)
        self._ensure_no_ambiguous_priority(matched_rules)
        budget_usage = {
            "registered_rules": len(self._rules),
            "matched_rules": len(matched_rules),
            "proposal_count": sum(len(rule.proposal_templates) for rule in matched_rules),
        }
        total_budget = sum(rule.evaluation_budget for rule in matched_rules)
        if budget_usage["proposal_count"] > total_budget:
            raise SemanticRegistryError("semantic_evaluation_budget_exhausted")
        guard_results = {
            rule.rule_ref: self._evaluate_guard(rule.guard_expression, evaluation.semantic_snapshot)
            for rule in matched_rules
        }
        conflict_decisions = {
            rule.rule_ref: (
                "rejected_by_guard"
                if not guard_results[rule.rule_ref]
                else "proposal_only" if rule.proposal_templates else "no_proposal"
            )
            for rule in matched_rules
        }
        matched_selectors = tuple(
            selector
            for rule in matched_rules
            for selector in rule.trigger_selectors
            if self._selector_matches(selector, evaluation)
        )
        proposal_digests = tuple(
            _stable_digest(proposal.model_dump(mode="json"))
            for rule in matched_rules
            if guard_results[rule.rule_ref]
            for proposal in rule.proposal_templates
        )
        explanation_visibility = self._explanation_visibility(matched_rules, evaluation.requested_trace_scope)
        output_payload = {
            "rule_refs": [rule.rule_ref for rule in matched_rules],
            "matched_selectors": list(matched_selectors),
            "guard_results": guard_results,
            "conflict_decisions": conflict_decisions,
            "budget_usage": budget_usage,
            "proposal_digests": list(proposal_digests),
            "explanation_visibility": explanation_visibility,
            "input_digest": input_digest,
            "causal_chain_id": evaluation.causal_chain_id,
            "chain_depth": evaluation.chain_depth,
        }
        output_digest = _stable_digest(output_payload)
        return RuleEvaluationTrace(
            evaluation_id=_stable_digest({"input_digest": input_digest, "output_digest": output_digest}),
            rule_refs=tuple(rule.rule_ref for rule in matched_rules),
            matched_selectors=matched_selectors,
            guard_results=guard_results,
            conflict_decisions=conflict_decisions,
            budget_usage=budget_usage,
            proposal_digests=proposal_digests,
            explanation_visibility=explanation_visibility,
            input_digest=input_digest,
            output_digest=output_digest,
            causal_chain_id=evaluation.causal_chain_id,
            chain_depth=evaluation.chain_depth,
        )

    def export_snapshot(self) -> dict[str, Any]:
        return {
            "registry_schema_version": 1,
            "definitions": [
                definition.model_dump(mode="json")
                for definition in sorted(
                    self._definitions.values(),
                    key=lambda item: (item.namespace, item.semantic_id, item.semantic_version),
                )
            ],
            "meta_rules": [
                definition.model_dump(mode="json")
                for definition in sorted(
                    self._rules.values(),
                    key=lambda item: (item.phase, -item.priority, item.rule_ref, item.rule_version),
                )
            ],
        }

    @classmethod
    def from_snapshot(cls, snapshot: object) -> "SemanticRegistry":
        if not isinstance(snapshot, dict) or snapshot.get("registry_schema_version") != 1:
            raise SemanticRegistryError("semantic_registry_snapshot_unsupported")
        definitions = snapshot.get("definitions")
        meta_rules = snapshot.get("meta_rules")
        if not isinstance(definitions, list) or not isinstance(meta_rules, list):
            raise SemanticRegistryError("semantic_registry_snapshot_invalid")
        registry = cls()
        try:
            for value in definitions:
                registry.register(SemanticDefinition.model_validate(value))
            for value in meta_rules:
                registry.register_meta_rule(MetaRuleDefinition.model_validate(value))
        except (TypeError, ValueError, SemanticRegistryError) as exc:
            if isinstance(exc, SemanticRegistryError):
                raise SemanticRegistryError("semantic_registry_snapshot_invalid") from exc
            raise SemanticRegistryError("semantic_registry_snapshot_invalid") from exc
        return registry

    def _ensure_snapshot_semantics_known(self, snapshot: SemanticSnapshot) -> None:
        if not self._definitions:
            return
        unknown = [semantic_id for semantic_id in snapshot.resolved_tags if semantic_id not in self._definitions]
        if unknown:
            raise SemanticRegistryError("semantic_definition_unknown")

    def _matched_rules(self, evaluation: RuleEvaluationInput) -> list[MetaRuleDefinition]:
        return sorted(
            [
                rule
                for rule in self._rules.values()
                if any(self._selector_matches(selector, evaluation) for selector in rule.trigger_selectors)
            ],
            key=lambda rule: (rule.phase, -rule.priority, rule.rule_ref, rule.rule_version),
        )

    def _ensure_no_ambiguous_priority(self, rules: list[MetaRuleDefinition]) -> None:
        seen: set[tuple[str, int]] = set()
        for rule in rules:
            key = (rule.phase, rule.priority)
            if key in seen:
                raise SemanticRegistryError("semantic_priority_ambiguous")
            seen.add(key)

    @staticmethod
    def _is_closed_guard(guard_expression: str) -> bool:
        normalized = guard_expression.strip().lower()
        if normalized.startswith(("all(", "any(")):
            terms = SemanticRegistry._closed_guard_terms(normalized)
            return terms is not None and all(SemanticRegistry._is_atomic_closed_guard(term) for term in terms)
        return SemanticRegistry._is_atomic_closed_guard(normalized)

    @staticmethod
    def _closed_guard_terms(guard_expression: str) -> tuple[str, ...] | None:
        prefix, separator, tail = guard_expression.partition("(")
        if prefix not in {"all", "any"} or not separator or not tail.endswith(")"):
            return None
        body = tail[:-1]
        if not body or "(" in body or ")" in body:
            return None
        terms = tuple(term.strip() for term in body.split(","))
        if not terms or any(not term for term in terms):
            return None
        return terms

    @staticmethod
    def _is_atomic_closed_guard(guard_expression: str) -> bool:
        normalized = guard_expression.strip().lower()
        if normalized in {"true", "always", "1", "false", "never", "0"}:
            return True
        prefix, separator, operand = normalized.partition(":")
        if prefix in {"tag", "status"}:
            return bool(separator and operand)
        if prefix in {"parameter_gte", "parameter_lte", "parameter_eq"}:
            key, equals, value = operand.partition("=")
            if not key or not equals:
                return False
            try:
                int(value)
            except ValueError:
                return False
            return True
        return False

    @classmethod
    def _evaluate_guard(cls, guard_expression: str, snapshot: SemanticSnapshot) -> bool:
        normalized = guard_expression.strip().lower()
        if normalized.startswith(("all(", "any(")):
            terms = cls._closed_guard_terms(normalized)
            if terms is None or not all(cls._is_atomic_closed_guard(term) for term in terms):
                raise SemanticRegistryError("semantic_guard_expression_unsupported")
            values = tuple(cls._evaluate_atomic_guard(term, snapshot) for term in terms)
            return all(values) if normalized.startswith("all(") else any(values)
        return cls._evaluate_atomic_guard(normalized, snapshot)

    @staticmethod
    def _evaluate_atomic_guard(guard_expression: str, snapshot: SemanticSnapshot) -> bool:
        normalized = guard_expression.strip().lower()
        if normalized in {"true", "always", "1"}:
            return True
        if normalized in {"false", "never", "0"}:
            return False
        prefix, _separator, operand = normalized.partition(":")
        if prefix == "tag":
            return operand in snapshot.resolved_tags
        if prefix == "status":
            return operand in snapshot.statuses
        if prefix in {"parameter_gte", "parameter_lte", "parameter_eq"}:
            key, _equals, raw_value = operand.partition("=")
            actual = snapshot.resolved_parameters.get(key)
            expected = int(raw_value)
            if isinstance(actual, bool) or not isinstance(actual, (int, float)):
                return False
            if prefix == "parameter_gte":
                return actual >= expected
            if prefix == "parameter_lte":
                return actual <= expected
            return actual == expected
        raise SemanticRegistryError("semantic_guard_expression_unsupported")

    @staticmethod
    def _selector_matches(selector: str, evaluation: RuleEvaluationInput) -> bool:
        candidates = {
            evaluation.trigger_ref,
            evaluation.action_intent.action_ref if evaluation.action_intent is not None else None,
        }
        normalized_selector = selector.strip()
        if normalized_selector in candidates:
            return True
        if normalized_selector.endswith(".*"):
            prefix = normalized_selector[:-2]
            return any(isinstance(candidate, str) and candidate.startswith(prefix) for candidate in candidates if candidate is not None)
        return False

    @staticmethod
    def _explanation_visibility(rules: list[MetaRuleDefinition], requested_scope: str) -> str:
        if requested_scope != "authority" and any(rule.trace_policy == "authority_only" for rule in rules):
            return "summary"
        if any(rule.trace_policy == "full" for rule in rules):
            return "full"
        if any(rule.trace_policy for rule in rules):
            return "summary"
        return "none"


__all__ = [
    "ClosedEffectDefinition",
    "ClosedRuleDefinition",
    "ClosedRuleEvaluation",
    "ClosedEffectResolution",
    "LifecycleOwnerContract",
    "StateLifecycleAdapterContract",
    "EntityDossier",
    "MetaRuleDefinition",
    "OwnerMapping",
    "RuleEvaluationInput",
    "RuleEvaluationTrace",
    "SemanticSelector",
    "SemanticDefinition",
    "SemanticRegistry",
    "SemanticRegistryError",
    "SemanticSnapshot",
    "RuleSetRevision",
    "RegisteredStateOwnerRoute",
    "RegisteredEffectOwnerRoute",
    "RegisteredSurvivalStateActionRoute",
    "StateOwnerRow",
    "StateLifecyclePolicy",
    "TagAssignment",
    "TagDefinition",
]
