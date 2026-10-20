"""Typed admission for character resource templates.

This module is a boundary contract for a future character-template content
source.  It deliberately does not provide a registry, defaults, persistence,
clock, or resource mutation path.  A caller must supply a published source
record and revalidate that same record immediately before an owner write.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import ConfigDict, Field, StrictInt, model_validator

from app.gameplay.models import StrictGameplayModel


class ResourceTemplateAdmissionError(ValueError):
    """Raised when a template source cannot be admitted or revalidated."""


ResourceId = Literal["core.stamina", "core.mana", "core.action_points"]
ResourceRelationKind = Literal["independent", "coupled", "fused"]


class ResourceTemplateEntry(StrictGameplayModel):
    """One explicit integer resource policy published by a character template."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    resource_id: ResourceId
    maximum: StrictInt = Field(ge=0)
    capacity: StrictInt = Field(ge=0)
    base_capacity: StrictInt = Field(ge=0)
    initial: StrictInt = Field(ge=0)
    recovery_amount: StrictInt = Field(ge=0)
    recovery_period_world_ticks: StrictInt = Field(gt=0)
    debt_policy: Literal["forbidden"] = "forbidden"
    lock_issuer_ref: str = Field(min_length=1)
    lock_lifecycle_revision: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_bounds(self) -> "ResourceTemplateEntry":
        if self.maximum > self.capacity:
            raise ValueError("resource_template_capacity_below_maximum")
        if self.initial > self.maximum or self.initial > self.capacity or self.base_capacity > self.capacity:
            raise ValueError("resource_template_initial_exceeds_maximum")
        return self


class ResourceTemplateSource(StrictGameplayModel):
    """Published, read-authorized source record for a character template."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    template_ref: str = Field(min_length=1)
    template_revision: str = Field(min_length=1)
    issuer_ref: str = Field(min_length=1)
    fact_owner_ref: str = Field(min_length=1)
    actor_scope: tuple[str, ...] = Field(min_length=1)
    world_scope: tuple[str, ...] = Field(min_length=1)
    timeline_scope: tuple[str, ...] = Field(min_length=1)
    valid_from_world_tick: StrictInt = Field(ge=0)
    valid_until_world_tick: StrictInt | None = Field(default=None, ge=0)
    source_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    binding_revision: str = Field(min_length=1)
    read_principals: tuple[str, ...] = Field(min_length=1)
    receipt_kind: str = Field(min_length=1)
    receipt_key: str = Field(min_length=1)
    revocation_owner_ref: str = Field(min_length=1)
    relation_policy_ref: str = "resource-relation:independent@1"
    relation_kind: ResourceRelationKind = "independent"
    resources: tuple[ResourceTemplateEntry, ...] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def _validate_source(self) -> "ResourceTemplateSource":
        if self.valid_until_world_tick is not None and self.valid_until_world_tick < self.valid_from_world_tick:
            raise ValueError("resource_template_validity_invalid")
        ids = tuple(entry.resource_id for entry in self.resources)
        if set(ids) != {"core.stamina", "core.mana", "core.action_points"}:
            raise ValueError("resource_template_core_set_incomplete")
        if len(ids) != len(set(ids)):
            raise ValueError("resource_template_duplicate_resource")
        if self.relation_kind != "independent" or self.relation_policy_ref != "resource-relation:independent@1":
            raise ValueError("resource_template_relation_policy_invalid")
        return self


@dataclass(frozen=True)
class FrozenResourceTemplate:
    """Caller snapshot that can be carried into an owner command."""

    source: ResourceTemplateSource
    actor_ref: str
    world_ref: str
    timeline_ref: str
    admitted_at_world_tick: int
    caller_principal: str


class ResourceTemplateAdmission:
    """Read-only admission and revalidation boundary for template consumers."""

    def admit(
        self,
        source: ResourceTemplateSource | None,
        *,
        actor_ref: str,
        world_ref: str,
        timeline_ref: str,
        now_world_tick: int,
        caller_principal: str,
        binding_revision: str,
    ) -> FrozenResourceTemplate:
        if source is None:
            raise ResourceTemplateAdmissionError("resource_template_source_missing")
        self._check(source, actor_ref=actor_ref, world_ref=world_ref, timeline_ref=timeline_ref,
                    now_world_tick=now_world_tick, caller_principal=caller_principal,
                    binding_revision=binding_revision)
        return FrozenResourceTemplate(source, actor_ref, world_ref, timeline_ref,
                                      now_world_tick, caller_principal)

    def revalidate(
        self,
        frozen: FrozenResourceTemplate,
        current: ResourceTemplateSource | None,
        *,
        now_world_tick: int,
        binding_revision: str,
    ) -> ResourceTemplateSource:
        if current is None:
            raise ResourceTemplateAdmissionError("resource_template_source_missing")
        if current != frozen.source:
            raise ResourceTemplateAdmissionError("resource_template_source_changed")
        self._check(current, actor_ref=frozen.actor_ref, world_ref=frozen.world_ref,
                    timeline_ref=frozen.timeline_ref, now_world_tick=now_world_tick,
                    caller_principal=frozen.caller_principal, binding_revision=binding_revision)
        return current

    @staticmethod
    def _check(source: ResourceTemplateSource, *, actor_ref: str, world_ref: str,
               timeline_ref: str, now_world_tick: int, caller_principal: str,
               binding_revision: str) -> None:
        if type(now_world_tick) is not int or now_world_tick < 0:
            raise ResourceTemplateAdmissionError("resource_template_world_tick_invalid")
        if actor_ref not in source.actor_scope or world_ref not in source.world_scope or timeline_ref not in source.timeline_scope:
            raise ResourceTemplateAdmissionError("resource_template_scope_denied")
        if now_world_tick < source.valid_from_world_tick or (
            source.valid_until_world_tick is not None and now_world_tick > source.valid_until_world_tick
        ):
            raise ResourceTemplateAdmissionError("resource_template_expired")
        if caller_principal not in source.read_principals:
            raise ResourceTemplateAdmissionError("resource_template_read_denied")
        if binding_revision != source.binding_revision:
            raise ResourceTemplateAdmissionError("resource_template_binding_revision_conflict")
