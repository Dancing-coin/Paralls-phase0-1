"""Strict immutable Inventory package content for Manifest v3/platform 2.0."""
from __future__ import annotations

import re
from typing import Literal
from pydantic import ConfigDict, Field, model_validator
from app.gameplay.models import StrictGameplayModel


_AUTHORITY_KEYS = {"owner", "owner_ref", "stream", "event", "event_ref", "receipt", "router", "registry", "writer", "authority", "authority_coordinate", "arbitrary_code", "script", "caller_proof"}
_REF = r"^[a-z][a-z0-9_-]*:[^@]+@[^@]+$"


class InventoryContentModel(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def reject_authority_fields(cls, value: object) -> object:
        if isinstance(value, dict) and any(key in _AUTHORITY_KEYS for key in value):
            raise ValueError("platform_authority_shaped_payload")
        return value


def _ordered(values: tuple[object, ...]) -> None:
    if len(set(values)) != len(values) or values != tuple(sorted(values)):
        raise ValueError("platform_array_not_canonical")


class ItemDefinitionContent(InventoryContentModel):
    item_definition_ref: str = Field(pattern=_REF)
    item_namespace_ref: str = Field(pattern=_REF)
    stack_policy_ref: str = Field(pattern=_REF)
    quality_policy_ref: str = Field(pattern=_REF)
    durability_policy_ref: str | None = Field(default=None, pattern=_REF)
    expiry_policy_ref: str | None = Field(default=None, pattern=_REF)
    stackable: bool = True
    unit_weight: int = Field(default=0, ge=0)
    unit_volume: int = Field(default=0, ge=0)


class LotPolicyContent(InventoryContentModel):
    lot_policy_ref: str = Field(pattern=_REF)
    lot_namespace_ref: str = Field(pattern=_REF)
    owner_family_ref: str = Field(pattern=_REF)
    split_policy_ref: str | None = Field(default=None, pattern=_REF)
    merge_policy_ref: str | None = Field(default=None, pattern=_REF)
    provenance_policy_ref: str | None = Field(default=None, pattern=_REF)


class ContainerDefinitionContent(InventoryContentModel):
    container_definition_ref: str = Field(pattern=_REF)
    container_namespace_ref: str = Field(pattern=_REF)
    capacity_policy_ref: str = Field(pattern=_REF)
    custody_policy_ref: str = Field(pattern=_REF)
    reservation_policy_ref: str = Field(pattern=_REF)
    transport_policy_ref: str = Field(pattern=_REF)
    quality_policy_ref: str = Field(pattern=_REF)
    parent_container_definition_ref: str | None = Field(default=None, pattern=_REF)


class CustodyPolicyContent(InventoryContentModel):
    custody_policy_ref: str = Field(pattern=_REF)
    custody_namespace_ref: str = Field(pattern=_REF)
    owner_family_ref: str = Field(pattern=_REF)
    stream_ref: str = Field(pattern=_REF)
    allowed_states: tuple[str, ...] = ("consumed", "destroyed", "held", "in_transit", "stored")

    @model_validator(mode="after")
    def canonical(self) -> "CustodyPolicyContent":
        _ordered(self.allowed_states)
        return self


class ReservationPolicyContent(InventoryContentModel):
    reservation_policy_ref: str = Field(pattern=_REF)
    reservation_namespace_ref: str = Field(pattern=_REF)
    stream_ref: str = Field(pattern=_REF)
    allowed_kinds: tuple[Literal["quantity", "capacity", "custody"], ...] = ("capacity", "custody", "quantity")

    @model_validator(mode="after")
    def canonical(self) -> "ReservationPolicyContent":
        _ordered(self.allowed_kinds)
        return self


class TransportPolicyContent(InventoryContentModel):
    transport_policy_ref: str = Field(pattern=_REF)
    transport_namespace_ref: str = Field(pattern=_REF)
    stream_ref: str = Field(pattern=_REF)
    delivery_window_policy_ref: str | None = Field(default=None, pattern=_REF)
    loss_policy_ref: str | None = Field(default=None, pattern=_REF)


class QualityPolicyContent(InventoryContentModel):
    quality_policy_ref: str = Field(pattern=_REF)
    quality_namespace_ref: str = Field(pattern=_REF)
    stream_ref: str = Field(pattern=_REF)
    quality_band_refs: tuple[str, ...] = ()
    decay_policy_ref: str | None = Field(default=None, pattern=_REF)
    repair_policy_ref: str | None = Field(default=None, pattern=_REF)

    @model_validator(mode="after")
    def canonical(self) -> "QualityPolicyContent":
        _ordered(self.quality_band_refs)
        return self


class InventoryConsumerEdgeContent(InventoryContentModel):
    consumer_edge_ref: str = Field(pattern=_REF)
    consumer_namespace_ref: str = Field(pattern=_REF)
    source_item_definition_ref: str = Field(pattern=_REF)
    target_container_definition_ref: str = Field(pattern=_REF)
    policy_ref: str = Field(pattern=_REF)


class InventoryPackageContent(InventoryContentModel):
    package_ref: str = Field(pattern=_REF)
    package_revision_ref: str = Field(pattern=_REF)
    item_definitions: tuple[ItemDefinitionContent, ...] = ()
    lot_policies: tuple[LotPolicyContent, ...] = ()
    container_definitions: tuple[ContainerDefinitionContent, ...] = ()
    custody_policies: tuple[CustodyPolicyContent, ...] = ()
    reservation_policies: tuple[ReservationPolicyContent, ...] = ()
    transport_policies: tuple[TransportPolicyContent, ...] = ()
    quality_policies: tuple[QualityPolicyContent, ...] = ()
    consumer_edges: tuple[InventoryConsumerEdgeContent, ...] = ()

    @model_validator(mode="after")
    def canonical_arrays(self) -> "InventoryPackageContent":
        for values, attr in (
            (self.item_definitions, "item_definition_ref"),
            (self.lot_policies, "lot_policy_ref"),
            (self.container_definitions, "container_definition_ref"),
            (self.custody_policies, "custody_policy_ref"),
            (self.reservation_policies, "reservation_policy_ref"),
            (self.transport_policies, "transport_policy_ref"),
            (self.quality_policies, "quality_policy_ref"),
            (self.consumer_edges, "consumer_edge_ref"),
        ):
            _ordered(tuple(getattr(item, attr) for item in values))
        if self.package_ref != self.package_revision_ref.rsplit("@", 1)[0] + "@" + self.package_revision_ref.rsplit("@", 1)[1]:
            raise ValueError("inventory_package_identity_mismatch")
        containers = {item.container_definition_ref: item for item in self.container_definitions}
        for container in containers.values():
            seen = {container.container_definition_ref}
            parent = container.parent_container_definition_ref
            while parent is not None:
                if parent in seen:
                    raise ValueError("inventory_container_definition_cycle")
                if parent not in containers:
                    raise ValueError("inventory_container_definition_parent_missing")
                seen.add(parent)
                parent = containers[parent].parent_container_definition_ref
        return self


__all__ = [name for name, value in globals().items() if isinstance(value, type) and issubclass(value, InventoryContentModel)]
