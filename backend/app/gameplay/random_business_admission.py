"""Admission boundary for Economy-owned random business demands.

This module does not publish loot tables, choose candidates, generate seeds, or
append Economy events.  It only validates a caller-provided, versioned source
record and freezes the inputs that a future Economy owner command must
revalidate before committing a random result receipt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import ConfigDict, Field, StrictInt, model_validator

from app.gameplay.models import StrictGameplayModel


class RandomBusinessAdmissionError(ValueError):
    """Raised when a random business source or request cannot be admitted."""


RandomBusinessKind = Literal["lottery", "loot", "event_choice"]


class RandomBusinessSource(StrictGameplayModel):
    """Published candidate/policy source owned outside the Economy runtime."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    demand_ref: str = Field(min_length=1)
    demand_revision: str = Field(min_length=1)
    kind: RandomBusinessKind
    issuer_ref: str = Field(min_length=1)
    fact_owner_ref: str = Field(min_length=1)
    actor_scope: tuple[str, ...] = Field(min_length=1)
    world_scope: tuple[str, ...] = Field(min_length=1)
    timeline_scope: tuple[str, ...] = Field(min_length=1)
    valid_from_world_tick: StrictInt = Field(ge=0)
    valid_until_world_tick: StrictInt | None = Field(default=None, ge=0)
    candidate_registry_ref: str = Field(min_length=1)
    candidate_registry_revision: str = Field(min_length=1)
    algorithm_revision: str = Field(min_length=1)
    seed_policy_revision: str = Field(min_length=1)
    source_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    read_principals: tuple[str, ...] = Field(min_length=1)
    receipt_lookup_ref: str = Field(min_length=1)
    revocation_owner_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validity(self) -> "RandomBusinessSource":
        if self.valid_until_world_tick is not None and self.valid_until_world_tick < self.valid_from_world_tick:
            raise ValueError("random_business_validity_invalid")
        return self


class RandomBusinessRequest(StrictGameplayModel):
    """Frozen caller inputs required for a deterministic Economy draw."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_ref: str = Field(min_length=1)
    effect_ref: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    draw_index: StrictInt = Field(ge=0)
    # Randomness is generated only by Economy; admission has no seed input.
    seed: str | None = None
    source_digest: str = Field(min_length=1)


@dataclass(frozen=True)
class FrozenRandomBusinessDemand:
    source: RandomBusinessSource
    request: RandomBusinessRequest
    actor_ref: str
    world_ref: str
    timeline_ref: str
    admitted_at_world_tick: int
    caller_principal: str


class RandomBusinessAdmission:
    """Read-only source admission and pre-commit revalidation."""

    def admit(
        self,
        source: RandomBusinessSource | None,
        request: RandomBusinessRequest,
        *,
        actor_ref: str,
        world_ref: str,
        timeline_ref: str,
        now_world_tick: int,
        caller_principal: str,
    ) -> FrozenRandomBusinessDemand:
        if source is None:
            raise RandomBusinessAdmissionError("random_business_source_missing")
        self._check(source, request, actor_ref=actor_ref, world_ref=world_ref,
                    timeline_ref=timeline_ref, now_world_tick=now_world_tick,
                    caller_principal=caller_principal)
        return FrozenRandomBusinessDemand(source, request, actor_ref, world_ref,
                                          timeline_ref, now_world_tick,
                                          caller_principal)

    def revalidate(
        self,
        frozen: FrozenRandomBusinessDemand,
        current: RandomBusinessSource | None,
        *,
        now_world_tick: int,
    ) -> RandomBusinessSource:
        if current is None:
            raise RandomBusinessAdmissionError("random_business_source_missing")
        if current != frozen.source:
            raise RandomBusinessAdmissionError("random_business_source_changed")
        self._check(current, frozen.request, actor_ref=frozen.actor_ref,
                    world_ref=frozen.world_ref, timeline_ref=frozen.timeline_ref,
                    now_world_tick=now_world_tick,
                    caller_principal=frozen.caller_principal)
        return current

    @staticmethod
    def _check(
        source: RandomBusinessSource,
        request: RandomBusinessRequest,
        *,
        actor_ref: str,
        world_ref: str,
        timeline_ref: str,
        now_world_tick: int,
        caller_principal: str,
    ) -> None:
        if type(now_world_tick) is not int or now_world_tick < 0:
            raise RandomBusinessAdmissionError("random_business_world_tick_invalid")
        if actor_ref not in source.actor_scope or world_ref not in source.world_scope or timeline_ref not in source.timeline_scope:
            raise RandomBusinessAdmissionError("random_business_scope_denied")
        if request.target_ref != actor_ref:
            raise RandomBusinessAdmissionError("random_business_target_conflict")
        if now_world_tick < source.valid_from_world_tick or (
            source.valid_until_world_tick is not None and now_world_tick > source.valid_until_world_tick
        ):
            raise RandomBusinessAdmissionError("random_business_expired")
        if caller_principal not in source.read_principals:
            raise RandomBusinessAdmissionError("random_business_read_denied")
        if request.source_digest != source.source_digest:
            raise RandomBusinessAdmissionError("random_business_source_digest_conflict")


__all__ = [
    "FrozenRandomBusinessDemand",
    "RandomBusinessAdmission",
    "RandomBusinessAdmissionError",
    "RandomBusinessKind",
    "RandomBusinessRequest",
    "RandomBusinessSource",
]
