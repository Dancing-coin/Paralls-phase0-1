"""Strict loader for the first executable adventure-basic package baseline."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

from app.gameplay.ability_runtime import AbilityDefinitionRegistry, AbilityPathDefinition, AbilitySkillDefinition
from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.equipment_runtime import EquipmentAuthorityService, EquipmentDefinitionRegistry, EquipmentProfile, EquipmentSlotDefinition
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.fixed_offer_purchase import FixedOfferAuthorityService, PurchaseRuntimeError
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry, ItemDefinition
from app.gameplay.modifier_runtime import ModifierDefinitionRegistry, ModifierTemplate
from app.gameplay.ownership_runtime import OwnershipAuthorityService
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRuntimeError
from app.gameplay.resource_body_runtime import BodyRuntimeProjection, FunctionalCapacity


ADVENTURE_BASIC_PATCH_ID = "adventure-basic"
ADVENTURE_BASIC_PROFILE = "adventure-basic"


def load_adventure_basic_manifest(path: Path) -> GameplayPatchManifest:
    """Load a trusted reference manifest without activating a patch or writing truth."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GameplayPatchRuntimeError("adventure_basic_manifest_unreadable") from exc
    if not isinstance(payload, dict):
        raise GameplayPatchRuntimeError("adventure_basic_manifest_invalid")
    try:
        manifest = GameplayPatchManifest.model_validate(payload)
    except ValueError as exc:
        raise GameplayPatchRuntimeError("adventure_basic_manifest_invalid") from exc
    if manifest.patch_id != ADVENTURE_BASIC_PATCH_ID:
        raise GameplayPatchRuntimeError("adventure_basic_patch_id_invalid")
    if ADVENTURE_BASIC_PROFILE not in manifest.verification_profiles:
        raise GameplayPatchRuntimeError("adventure_basic_profile_missing")
    if manifest.content_digest != manifest.expected_content_digest():
        raise GameplayPatchRuntimeError("adventure_basic_manifest_digest_invalid")
    return manifest


class AdventureBasicScenarioError(ValueError):
    """Stable scenario failure surface while retaining authority error codes."""


class AdventureBasicScenario1:
    """Scenario 1 reference composition that reuses the existing authority services."""

    player_ref = "character:char_player"
    merchant_ref = "character:merchant_iron"
    player_account_id = "account:char_player:copper"
    merchant_account_id = "account:merchant_iron:copper"
    player_backpack_id = "container:char_player:backpack"
    merchant_stock_id = "container:merchant_iron:stock"
    sword_item_id = "item:iron_sword:001"
    sword_definition_id = "item:iron_sword"
    sword_asset_ref = "asset:iron_sword:001"
    sword_right_id = "right:iron_sword:001"
    sword_offer_id = "offer:iron_sword:001"
    currency_ref = "copper"
    sword_price = 80

    def __init__(self, store, inventory_registry, ability_registry, modifier_registry, purchase_authority, equipment_authority) -> None:
        self.store = store
        self.inventory_registry = inventory_registry
        self.ability_registry = ability_registry
        self.modifier_registry = modifier_registry
        self._purchase_authority = purchase_authority
        self._equipment_authority = equipment_authority

    @classmethod
    def create(cls, *, player_copper: int = 120) -> "AdventureBasicScenario1":
        """Create explicit reference seeds without activating a Patch or writing Godot state."""
        store = GameplayEventStore()
        inventory_registry = InventoryDefinitionRegistry()
        inventory_registry.register_item(ItemDefinition(cls.sword_definition_id, "v1", 3, 2))
        inventory = InventoryAuthorityService(store=store, registry=inventory_registry)
        correlation_id = "adventure-basic:scenario-1"

        cls._committed(inventory.create_container(command_id="adventure-basic:seed:merchant-stock", actor_ref=cls.merchant_ref, spec=ContainerSpec(cls.merchant_stock_id, 100, 100, 16), idempotency_key="adventure-basic:seed:merchant-stock", causation_id="adventure-basic:seed", correlation_id=correlation_id))
        cls._committed(inventory.create_container(command_id="adventure-basic:seed:player-backpack", actor_ref=cls.player_ref, spec=ContainerSpec(cls.player_backpack_id, 20, 30, 8), idempotency_key="adventure-basic:seed:player-backpack", causation_id="adventure-basic:seed", correlation_id=correlation_id))
        cls._committed(inventory.instantiate(command_id="adventure-basic:seed:iron-sword", actor_ref=cls.merchant_ref, item_id=cls.sword_item_id, definition_id=cls.sword_definition_id, quantity=1, container_id=cls.merchant_stock_id, idempotency_key="adventure-basic:seed:iron-sword", causation_id="adventure-basic:seed", correlation_id=correlation_id))

        ownership = OwnershipAuthorityService(store=store)
        cls._committed(ownership.grant_initial_title(command_id="adventure-basic:seed:iron-sword-title", asset_ref=cls.sword_asset_ref, holder_ref=cls.merchant_ref, right_id=cls.sword_right_id, idempotency_key="adventure-basic:seed:iron-sword-title", causation_id="adventure-basic:seed", correlation_id=correlation_id))
        economy = EconomyAuthorityService(store=store)
        cls._committed(economy.open_account(command_id="adventure-basic:seed:player-copper", account_id=cls.player_account_id, owner_ref=cls.player_ref, currency_ref=cls.currency_ref, initial_balance=player_copper, idempotency_key="adventure-basic:seed:player-copper", causation_id="adventure-basic:seed", correlation_id=correlation_id))
        cls._committed(economy.open_account(command_id="adventure-basic:seed:merchant-copper", account_id=cls.merchant_account_id, owner_ref=cls.merchant_ref, currency_ref=cls.currency_ref, initial_balance=0, idempotency_key="adventure-basic:seed:merchant-copper", causation_id="adventure-basic:seed", correlation_id=correlation_id))

        purchase_authority = FixedOfferAuthorityService(store=store, inventory_registry=inventory_registry)
        cls._committed(purchase_authority.publish_offer(command_id="adventure-basic:seed:iron-sword-offer", offer_id=cls.sword_offer_id, seller_ref=cls.merchant_ref, asset_ref=cls.sword_asset_ref, right_id=cls.sword_right_id, item_id=cls.sword_item_id, source_container_id=cls.merchant_stock_id, price_amount=cls.sword_price, currency_ref=cls.currency_ref, idempotency_key="adventure-basic:seed:iron-sword-offer", causation_id="adventure-basic:seed", correlation_id=correlation_id))

        ability_registry = AbilityDefinitionRegistry()
        ability_registry.register_skill(AbilitySkillDefinition("skill:swordsmanship.basic", "v1"))
        ability_registry.register_path(AbilityPathDefinition("path:swordsmanship.basic.swing", "skill:swordsmanship.basic", "action:sword.swing"))
        modifier_registry = ModifierDefinitionRegistry()
        modifier_registry.register_template(ModifierTemplate("modifier-template:iron-sword-control", "sword_control", "additive", Decimal("1"), "adventure-basic:iron-sword"))
        equipment_registry = EquipmentDefinitionRegistry()
        equipment_registry.register_profile(cls.sword_definition_id, EquipmentProfile("profile:iron-sword", ("right_hand",), (), ("path:swordsmanship.basic.swing",), ("modifier-template:iron-sword-control",)))
        equipment_authority = EquipmentAuthorityService(store=store, inventory_registry=inventory_registry, equipment_registry=equipment_registry, ability_registry=ability_registry, modifier_registry=modifier_registry, slots=(EquipmentSlotDefinition("right_hand", ("grip.right",)),))
        return cls(store, inventory_registry, ability_registry, modifier_registry, purchase_authority, equipment_authority)

    def purchase_sword(self):
        offer = self._purchase_authority.offer_projection().offers[self.sword_offer_id]
        try:
            return self._purchase_authority.purchase(command_id="adventure-basic:purchase-sword", offer_id=self.sword_offer_id, expected_offer_revision=offer.offer_revision, buyer_ref=self.player_ref, buyer_account_id=self.player_account_id, seller_account_id=self.merchant_account_id, destination_container_id=self.player_backpack_id, accepted_amount=self.sword_price, accepted_currency_ref=self.currency_ref, idempotency_key="adventure-basic:purchase-sword", causation_id="adventure-basic:scenario-1", correlation_id="adventure-basic:scenario-1")
        except PurchaseRuntimeError as exc:
            raise AdventureBasicScenarioError(str(exc)) from exc

    def equip_sword(self):
        body = BodyRuntimeProjection(self.player_ref, MappingProxyType({}), MappingProxyType({"grip.right": FunctionalCapacity("grip.right", 100, "available", ())}), MappingProxyType({}), "adventure-basic:body:healthy")
        try:
            return self._equipment_authority.equip(command_id="adventure-basic:equip-sword", actor_ref=self.player_ref, item_id=self.sword_item_id, source_container_id=self.player_backpack_id, slot_key="right_hand", body=body, idempotency_key="adventure-basic:equip-sword", causation_id="adventure-basic:scenario-1", correlation_id="adventure-basic:scenario-1")
        except ValueError as exc:
            raise AdventureBasicScenarioError(str(exc)) from exc

    @staticmethod
    def _committed(result: object) -> None:
        if not bool(getattr(result, "committed", False)):
            raise AdventureBasicScenarioError("adventure_basic_seed_not_committed")


__all__ = ["ADVENTURE_BASIC_PATCH_ID", "ADVENTURE_BASIC_PROFILE", "AdventureBasicScenario1", "AdventureBasicScenarioError", "load_adventure_basic_manifest"]
