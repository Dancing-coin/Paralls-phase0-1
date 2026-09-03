"""Read-only admission for precompiled Inventory cross-owner recipes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Sequence
from pydantic import ConfigDict, Field
from app.gameplay.models import StrictGameplayModel


class InventoryConsumerError(ValueError):
    pass


class InventoryConsumerRecipe(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    recipe_ref: str = Field(min_length=1)
    target_owner_ref: str = Field(min_length=1)
    capability_ref: str = Field(min_length=1)
    target_event_type: str = Field(min_length=1)
    target_stream_pattern: str = Field(min_length=1)
    privacy_scope: Literal["project", "authority_only"]
    source_event_type: str = Field(min_length=1)
    policy_revision_ref: str = Field(min_length=1)


RECIPES: tuple[InventoryConsumerRecipe, ...] = (
    InventoryConsumerRecipe(recipe_ref="recipe:inventory:production-consume@1", target_owner_ref="actor_gameplay.construction_production_domain", capability_ref="capability:inventory-production-consume@1", target_event_type="gameplay.construction_production.run_started", target_stream_pattern="gameplay:construction_production:{facility_ref}", privacy_scope="project", source_event_type="gameplay.inventory.reservation_opened@1", policy_revision_ref="policy:inventory:production-consume@1"),
    InventoryConsumerRecipe(recipe_ref="recipe:inventory:commerce-delivery@1", target_owner_ref="actor_gameplay.economy_domain", capability_ref="capability:inventory-commerce-delivery@1", target_event_type="gameplay.economy.delivery_settlement_recorded@1", target_stream_pattern="gameplay:economy:{settlement_ref}", privacy_scope="authority_only", source_event_type="gameplay.inventory.transport_delivered@1", policy_revision_ref="policy:inventory:commerce-delivery@1"),
    InventoryConsumerRecipe(recipe_ref="recipe:inventory:ownership-handoff@1", target_owner_ref="actor_gameplay.ownership_domain", capability_ref="capability:inventory-ownership-handoff@1", target_event_type="gameplay.ownership.right_transferred", target_stream_pattern="gameplay:ownership", privacy_scope="authority_only", source_event_type="gameplay.inventory.custody_transferred@1", policy_revision_ref="policy:inventory:ownership-handoff@1"),
    InventoryConsumerRecipe(recipe_ref="recipe:inventory:survival-consume@1", target_owner_ref="actor_gameplay.survival_domain", capability_ref="capability:inventory-survival-consume@1", target_event_type="gameplay.survival.consumption_recorded@1", target_stream_pattern="gameplay:survival:{actor_ref}", privacy_scope="project", source_event_type="gameplay.inventory.custody_consumed@1", policy_revision_ref="policy:inventory:survival-consume@1"),
    InventoryConsumerRecipe(recipe_ref="recipe:inventory:equipment-activate@1", target_owner_ref="actor_gameplay.equipment_domain", capability_ref="capability:inventory-equipment-activate@1", target_event_type="gameplay.equipment.activation_recorded@1", target_stream_pattern="gameplay:equipment:{actor_ref}", privacy_scope="project", source_event_type="gameplay.inventory.custody_recorded@1", policy_revision_ref="policy:inventory:equipment-activate@1"),
    InventoryConsumerRecipe(recipe_ref="recipe:inventory:ecology-harvest@1", target_owner_ref="authority:ecology", capability_ref="capability:inventory-ecology-harvest@1", target_event_type="gameplay.ecology.inventory_harvest_accepted@1", target_stream_pattern="gameplay:ecology:platform:{region_ref}", privacy_scope="project", source_event_type="gameplay.inventory.custody_recorded@1", policy_revision_ref="policy:inventory:ecology-harvest@1"),
    InventoryConsumerRecipe(recipe_ref="recipe:inventory:organization-storage@1", target_owner_ref="actor_gameplay.organization_domain", capability_ref="capability:inventory-organization-storage@1", target_event_type="gameplay.organization.storage_accepted@1", target_stream_pattern="gameplay:organization:{organization_ref}", privacy_scope="project", source_event_type="gameplay.inventory.transport_delivered@1", policy_revision_ref="policy:inventory:organization-storage@1"),
    InventoryConsumerRecipe(recipe_ref="recipe:inventory:government-seizure@1", target_owner_ref="actor_gameplay.government_domain", capability_ref="capability:inventory-government-seizure@1", target_event_type="gameplay.government.inventory_seized@1", target_stream_pattern="gameplay:government:{jurisdiction_ref}", privacy_scope="authority_only", source_event_type="gameplay.inventory.custody_recorded@1", policy_revision_ref="policy:inventory:government-seizure@1"),
)


def inventory_consumer_recipes() -> tuple[InventoryConsumerRecipe, ...]:
    return RECIPES


def require_inventory_recipe(recipe_ref: str) -> InventoryConsumerRecipe:
    matches = tuple(recipe for recipe in RECIPES if recipe.recipe_ref == recipe_ref)
    if not matches:
        raise InventoryConsumerError("inventory_recipe_unknown")
    if len(matches) != 1:
        raise InventoryConsumerError("inventory_recipe_ambiguous")
    return matches[0]


@dataclass(frozen=True)
class InventoryBindingAdmission:
    accepted: bool
    recipe_ref: str
    error_code: str | None = None
    source_revision: int | None = None
    target_revision: int | None = None


def admit_inventory_recipe(*, recipe_ref: str, source_event_type: str, target_event_type: str, privacy_scope: str, source_revision: int, target_revision: int, source_private: bool = False) -> InventoryBindingAdmission:
    try:
        recipe = require_inventory_recipe(recipe_ref)
    except InventoryConsumerError as exc:
        return InventoryBindingAdmission(False, recipe_ref, str(exc))
    if source_private or recipe.privacy_scope != privacy_scope or recipe.source_event_type != source_event_type or recipe.target_event_type != target_event_type:
        return InventoryBindingAdmission(False, recipe_ref, "inventory_recipe_binding_mismatch")
    if source_revision < 0 or target_revision < 0:
        return InventoryBindingAdmission(False, recipe_ref, "inventory_recipe_revision_conflict")
    return InventoryBindingAdmission(True, recipe_ref, source_revision=source_revision, target_revision=target_revision)


__all__ = ["InventoryBindingAdmission", "InventoryConsumerError", "InventoryConsumerRecipe", "admit_inventory_recipe", "inventory_consumer_recipes", "require_inventory_recipe"]
