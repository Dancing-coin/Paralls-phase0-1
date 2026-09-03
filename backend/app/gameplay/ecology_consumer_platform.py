"""Read-only ecology consumer platform registry and admission helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Literal, Mapping, Sequence

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import (
    GovernedAuthorityContractCatalog,
    GovernedAuthorityContractError,
)
from app.gameplay.models import StrictGameplayModel


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class ConsumerEdgePlatformError(ValueError):
    pass


class ConsumerEdgeDefinition(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    edge_ref: str = Field(min_length=1)
    contract_ref: str = Field(min_length=1)
    contract_kind: Literal["ecology_consumer", "contract_admission"]
    target_owner_ref: str = Field(min_length=1)
    target_stream_pattern: str = Field(min_length=1)
    target_event_types: tuple[str, ...] = Field(min_length=1)
    projection_scope: Literal["project"] = "project"
    source_owner_ref: Literal["authority:ecology"] = "authority:ecology"
    source_event_type: str = Field(min_length=1)
    source_stream_pattern: str = Field(min_length=1)
    source_policy_ref: str = Field(min_length=1)
    source_revision_ref: str = Field(min_length=1)
    source_visibility_policy: Literal["project"] = "project"
    precompiled_recipe_ref: str = Field(min_length=1)
    receipt_reader_ref: str = Field(min_length=1)
    replay_reader_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_definition(self) -> "ConsumerEdgeDefinition":
        if not self.contract_ref.startswith("inf:") or "@" not in self.contract_ref:
            raise ValueError("consumer_edge_definition_invalid")
        if not self.edge_ref or "@" not in self.edge_ref:
            raise ValueError("consumer_edge_definition_invalid")
        if not self.source_policy_ref.startswith("policy:") or "@" not in self.source_policy_ref:
            raise ValueError("consumer_edge_definition_invalid")
        if not self.source_revision_ref.startswith("revision:") or "@" not in self.source_revision_ref:
            raise ValueError("consumer_edge_definition_invalid")
        if not self.target_stream_pattern.startswith("gameplay:") or not self.source_stream_pattern.startswith("gameplay:"):
            raise ValueError("consumer_edge_definition_invalid")
        if len(set(self.target_event_types)) != len(self.target_event_types):
            raise ValueError("consumer_edge_definition_invalid")
        if any(not event_type or not event_type.startswith("gameplay.") for event_type in self.target_event_types):
            raise ValueError("consumer_edge_definition_invalid")
        return self


class ConsumerEdgeProjectionEvidence(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    binding_ref: str = Field(min_length=1)
    edge_ref: str = Field(min_length=1)
    contract_ref: str = Field(min_length=1)
    target_owner_ref: str = Field(min_length=1)
    target_stream_ids: tuple[str, ...] = Field(min_length=1)
    target_event_types: tuple[str, ...] = Field(min_length=1)
    projection_scope: Literal["project"] = "project"
    source_event_id: str = Field(min_length=1)
    source_event_type: str = Field(min_length=1)
    source_stream_id: str = Field(min_length=1)
    source_revision: int = Field(ge=0, strict=True)
    source_policy_ref: str = Field(min_length=1)
    source_revision_ref: str = Field(min_length=1)
    source_visibility_policy: Literal["project"] = "project"
    receipt_reader_ref: str = Field(min_length=1)
    replay_reader_ref: str = Field(min_length=1)
    precompiled_recipe_ref: str = Field(min_length=1)
    request_digest: str = Field(min_length=1)


class ConsumerEdgeReplayEvidence(ConsumerEdgeProjectionEvidence):
    source_revision_vector: dict[str, int] = Field(default_factory=dict)
    target_expected_revisions: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_replay_evidence(self) -> "ConsumerEdgeReplayEvidence":
        if any(isinstance(revision, bool) or revision < 0 for revision in self.source_revision_vector.values()):
            raise ValueError("consumer_edge_replay_invalid")
        if any(isinstance(revision, bool) or revision < 0 for revision in self.target_expected_revisions.values()):
            raise ValueError("consumer_edge_replay_invalid")
        return self


class ConsumerEdgeAdmission(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    edge_ref: str = Field(min_length=1)
    contract_ref: str = Field(min_length=1)
    binding_ref: str = Field(min_length=1)
    request_digest: str | None = None
    receipt_reader_ref: str | None = None
    replay_reader_ref: str | None = None
    projection_evidence: ConsumerEdgeProjectionEvidence | None = None
    replay_evidence: ConsumerEdgeReplayEvidence | None = None
    error_code: str | None = None

    @model_validator(mode="after")
    def _validate_admission(self) -> "ConsumerEdgeAdmission":
        if self.accepted:
            if self.error_code is not None or self.request_digest is None:
                raise ValueError("consumer_edge_admission_invalid")
            if self.projection_evidence is None or self.replay_evidence is None:
                raise ValueError("consumer_edge_admission_invalid")
        return self


_EDGE_ROWS: tuple[dict[str, object], ...] = (
    {
        "edge_ref": "weather-front:survival:hydration@1",
        "contract_ref": "inf:weather-front-survival-hydration@1",
        "contract_kind": "ecology_consumer",
        "target_owner_ref": "actor_gameplay.survival_domain",
        "target_stream_pattern": "gameplay:survival:{profile_ref}",
        "target_event_types": ("gameplay.survival.state_applied", "gameplay.survival.obligation_opened"),
        "source_event_type": "gameplay.ecology.weather_front.propagated",
        "source_stream_pattern": "gameplay:ecology:{region_ref}",
        "source_policy_ref": "policy:weather-front-survival-hydration@1",
        "source_revision_ref": "revision:weather-front-survival-hydration-source@1",
        "precompiled_recipe_ref": "recipe:ecology-consumer:weather-front-survival-hydration@1",
        "receipt_reader_ref": "GameplayEventStore.append_batch",
        "replay_reader_ref": "SurvivalProjector",
    },
    {
        "edge_ref": "weather-front:construction:maintenance@1",
        "contract_ref": "inf:weather-front-construction-maintenance@1",
        "contract_kind": "ecology_consumer",
        "target_owner_ref": "actor_gameplay.construction_production_domain",
        "target_stream_pattern": "gameplay:construction_production:{facility_ref}",
        "target_event_types": ("gameplay.construction_production.maintenance_obligation_created",),
        "source_event_type": "gameplay.ecology.weather_front.propagated",
        "source_stream_pattern": "gameplay:ecology:{region_ref}",
        "source_policy_ref": "policy:weather-front-construction-maintenance@1",
        "source_revision_ref": "revision:weather-front-construction-maintenance-source@1",
        "precompiled_recipe_ref": "recipe:ecology-consumer:weather-front-construction-maintenance@1",
        "receipt_reader_ref": "GameplayEventStore.append_batch",
        "replay_reader_ref": "GameplayProjectionReplay",
    },
    {
        "edge_ref": "inventory:grain-harvest-custody@1",
        "contract_ref": "inf:inventory-grain-harvest-custody@1",
        "contract_kind": "contract_admission",
        "target_owner_ref": "actor_gameplay.inventory_domain",
        "target_stream_pattern": "gameplay:inventory:{actor_ref}",
        "target_event_types": ("gameplay.inventory.grain_harvest_received@1",),
        "source_event_type": "gameplay.ecology.grain_harvested",
        "source_stream_pattern": "gameplay:ecology:{region_ref}",
        "source_policy_ref": "policy:ecology-grain-harvest@1",
        "source_revision_ref": "revision:ecology-grain-harvest-source@1",
        "precompiled_recipe_ref": "recipe:ecology-consumer:inventory-grain-harvest-custody@1",
        "receipt_reader_ref": "GameplayEventStore.append_batch",
        "replay_reader_ref": "InventoryProjector.rebuild",
    },
    {
        "edge_ref": "weather-front:economy:quote@1",
        "contract_ref": "inf:weather-front-economy-quote@1",
        "contract_kind": "ecology_consumer",
        "target_owner_ref": "actor_gameplay.economy_domain",
        "target_stream_pattern": "gameplay:economy",
        "target_event_types": ("gameplay.economy.dynamic_quote_published",),
        "source_event_type": "gameplay.ecology.weather_front.propagated",
        "source_stream_pattern": "gameplay:ecology:{region_ref}",
        "source_policy_ref": "policy:weather-front-economy-quote@1",
        "source_revision_ref": "revision:weather-front-economy-quote-source@1",
        "precompiled_recipe_ref": "recipe:ecology-consumer:weather-front-economy-quote@1",
        "receipt_reader_ref": "GameplayEventStore.append_batch",
        "replay_reader_ref": "EconomyProjector",
    },
    {
        "edge_ref": "weather-front:organization:supply@1",
        "contract_ref": "inf:weather-front-organization-supply@1",
        "contract_kind": "ecology_consumer",
        "target_owner_ref": "actor_gameplay.organization_domain",
        "target_stream_pattern": "gameplay:organization:{organization_ref}",
        "target_event_types": ("gameplay.organization.commerce_commitment_accepted",),
        "source_event_type": "gameplay.ecology.weather_front.propagated",
        "source_stream_pattern": "gameplay:ecology:{region_ref}",
        "source_policy_ref": "policy:weather-front-organization-supply@1",
        "source_revision_ref": "revision:weather-front-organization-supply-source@1",
        "precompiled_recipe_ref": "recipe:ecology-consumer:weather-front-organization-supply@1",
        "receipt_reader_ref": "GameplayEventStore.append_batch",
        "replay_reader_ref": "OrganizationAuthority.commerce_commitment_projection",
    },
    {
        "edge_ref": "government:jurisdiction:drought-advisory@1",
        "contract_ref": "inf:weather-front-government-drought-advisory@1",
        "contract_kind": "ecology_consumer",
        "target_owner_ref": "actor_gameplay.government_domain",
        "target_stream_pattern": "gameplay:government:advisory:{jurisdiction_ref}",
        "target_event_types": ("gameplay.government.drought_advisory_issued",),
        "source_event_type": "gameplay.ecology.weather_front.propagated",
        "source_stream_pattern": "gameplay:ecology:{region_ref}",
        "source_policy_ref": "policy:weather-front-government-drought-advisory@1",
        "source_revision_ref": "revision:weather-front-government-drought-advisory-source@1",
        "precompiled_recipe_ref": "recipe:ecology-consumer:weather-front-government-drought-advisory@1",
        "receipt_reader_ref": "GameplayEventStore.append_batch",
        "replay_reader_ref": "GovernmentAuthority.drought_advisory_view_for",
    },
)


def consumer_edge_definitions() -> tuple[ConsumerEdgeDefinition, ...]:
    return tuple(ConsumerEdgeDefinition.model_validate(row) for row in _EDGE_ROWS)


def consumer_edge_definition_for(
    contract_ref: str,
    *,
    definitions: Sequence[ConsumerEdgeDefinition] | None = None,
) -> ConsumerEdgeDefinition:
    matches = tuple(
        definition
        for definition in (definitions if definitions is not None else consumer_edge_definitions())
        if definition.contract_ref == contract_ref
    )
    if not matches:
        raise ConsumerEdgePlatformError("consumer_edge_definition_unknown")
    if len(matches) != 1:
        raise ConsumerEdgePlatformError("consumer_edge_definition_ambiguous")
    return matches[0]


def admit_consumer_edge(
    *,
    store: GameplayEventStore,
    contract_ref: object,
    target_owner_ref: object,
    target_stream_ids: object,
    target_event_types: object,
    projection_scope: object,
    source_event_id: object,
    source_stream_id: object,
    source_revision: object,
    target_expected_revisions: object,
    idempotency_key: object,
    definitions: Sequence[ConsumerEdgeDefinition] | None = None,
) -> ConsumerEdgeAdmission:
    if (
        not isinstance(contract_ref, str)
        or not isinstance(target_owner_ref, str)
        or not isinstance(target_stream_ids, tuple)
        or not target_stream_ids
        or any(not isinstance(value, str) or not value for value in target_stream_ids)
        or not isinstance(target_event_types, tuple)
        or not target_event_types
        or any(not isinstance(value, str) or not value for value in target_event_types)
        or not isinstance(projection_scope, str)
        or not isinstance(source_event_id, str)
        or not isinstance(source_stream_id, str)
        or isinstance(source_revision, bool)
        or not isinstance(source_revision, int)
        or source_revision < 0
        or not isinstance(target_expected_revisions, Mapping)
        or set(target_expected_revisions) != set(target_stream_ids)
        or any(
            isinstance(revision, bool) or not isinstance(revision, int) or revision < 0
            for revision in target_expected_revisions.values()
        )
        or not isinstance(idempotency_key, str)
        or not idempotency_key
    ):
        raise ConsumerEdgePlatformError("consumer_edge_contract_invalid")

    try:
        definition = consumer_edge_definition_for(contract_ref, definitions=definitions)
    except ConsumerEdgePlatformError as exc:
        return ConsumerEdgeAdmission(
            accepted=False,
            edge_ref=str(contract_ref),
            contract_ref=str(contract_ref),
            binding_ref=f"binding:{contract_ref}",
            error_code=str(exc),
        )
    binding_ref = f"binding:{definition.edge_ref}"

    try:
        GovernedAuthorityContractCatalog.require_operation(
            contract_ref=definition.contract_ref,
            contract_kind=definition.contract_kind,
            owner_ref=target_owner_ref,
            stream_ids=target_stream_ids,
            event_types=target_event_types,
            projection_scope=projection_scope,
        )
    except GovernedAuthorityContractError as exc:
        return ConsumerEdgeAdmission(
            accepted=False,
            edge_ref=definition.edge_ref,
            contract_ref=definition.contract_ref,
            binding_ref=binding_ref,
            error_code="consumer_edge_unadmitted",
        )

    try:
        source_event = store.get_event(source_event_id)
    except KeyError:
        return ConsumerEdgeAdmission(
            accepted=False,
            edge_ref=definition.edge_ref,
            contract_ref=definition.contract_ref,
            binding_ref=binding_ref,
            error_code="consumer_edge_source_missing",
        )

    if source_event.event_type != definition.source_event_type:
        return ConsumerEdgeAdmission(
            accepted=False,
            edge_ref=definition.edge_ref,
            contract_ref=definition.contract_ref,
            binding_ref=binding_ref,
            error_code="consumer_edge_source_event_conflict",
        )
    if source_event.stream_id != source_stream_id:
        return ConsumerEdgeAdmission(
            accepted=False,
            edge_ref=definition.edge_ref,
            contract_ref=definition.contract_ref,
            binding_ref=binding_ref,
            error_code="consumer_edge_source_stream_conflict",
        )
    if source_event.visibility_policy != definition.source_visibility_policy:
        return ConsumerEdgeAdmission(
            accepted=False,
            edge_ref=definition.edge_ref,
            contract_ref=definition.contract_ref,
            binding_ref=binding_ref,
            error_code="consumer_edge_source_private",
        )
    if source_event.stream_revision != source_revision or store.get_stream_head(source_stream_id) != source_revision:
        return ConsumerEdgeAdmission(
            accepted=False,
            edge_ref=definition.edge_ref,
            contract_ref=definition.contract_ref,
            binding_ref=binding_ref,
            error_code="consumer_edge_source_revision_conflict",
        )
    policy_revision = source_event.payload.get("policy_revision")
    if policy_revision != definition.source_policy_ref:
        return ConsumerEdgeAdmission(
            accepted=False,
            edge_ref=definition.edge_ref,
            contract_ref=definition.contract_ref,
            binding_ref=binding_ref,
            error_code="consumer_edge_source_policy_conflict",
        )
    if any(store.get_stream_head(stream_id) != target_expected_revisions[stream_id] for stream_id in target_stream_ids):
        return ConsumerEdgeAdmission(
            accepted=False,
            edge_ref=definition.edge_ref,
            contract_ref=definition.contract_ref,
            binding_ref=binding_ref,
            error_code="consumer_edge_target_revision_conflict",
        )

    request_digest = _digest(
        {
            "binding_ref": binding_ref,
            "contract_ref": definition.contract_ref,
            "edge_ref": definition.edge_ref,
            "target_owner_ref": target_owner_ref,
            "target_stream_ids": target_stream_ids,
            "target_event_types": target_event_types,
            "projection_scope": projection_scope,
            "source_event_id": source_event_id,
            "source_stream_id": source_stream_id,
            "source_revision": source_revision,
            "target_expected_revisions": dict(sorted(target_expected_revisions.items())),
            "idempotency_key": idempotency_key,
            "source_policy_ref": definition.source_policy_ref,
            "source_revision_ref": definition.source_revision_ref,
            "source_visibility_policy": definition.source_visibility_policy,
            "precompiled_recipe_ref": definition.precompiled_recipe_ref,
        }
    )
    projection_evidence = ConsumerEdgeProjectionEvidence(
        binding_ref=binding_ref,
        edge_ref=definition.edge_ref,
        contract_ref=definition.contract_ref,
        target_owner_ref=target_owner_ref,
        target_stream_ids=target_stream_ids,
        target_event_types=target_event_types,
        projection_scope="project",
        source_event_id=source_event_id,
        source_event_type=source_event.event_type,
        source_stream_id=source_stream_id,
        source_revision=source_revision,
        source_policy_ref=definition.source_policy_ref,
        source_revision_ref=definition.source_revision_ref,
        source_visibility_policy=definition.source_visibility_policy,
        receipt_reader_ref=definition.receipt_reader_ref,
        replay_reader_ref=definition.replay_reader_ref,
        precompiled_recipe_ref=definition.precompiled_recipe_ref,
        request_digest=request_digest,
    )
    replay_evidence = ConsumerEdgeReplayEvidence(
        **projection_evidence.model_dump(mode="python"),
        source_revision_vector={source_stream_id: source_revision, **dict(sorted(target_expected_revisions.items()))},
        target_expected_revisions=dict(sorted(target_expected_revisions.items())),
    )
    return ConsumerEdgeAdmission(
        accepted=True,
        edge_ref=definition.edge_ref,
        contract_ref=definition.contract_ref,
        binding_ref=binding_ref,
        request_digest=request_digest,
        receipt_reader_ref=definition.receipt_reader_ref,
        replay_reader_ref=definition.replay_reader_ref,
        projection_evidence=projection_evidence,
        replay_evidence=replay_evidence,
    )


__all__ = [
    "ConsumerEdgeAdmission",
    "ConsumerEdgeDefinition",
    "ConsumerEdgePlatformError",
    "ConsumerEdgeProjectionEvidence",
    "ConsumerEdgeReplayEvidence",
    "admit_consumer_edge",
    "consumer_edge_definition_for",
    "consumer_edge_definitions",
]
