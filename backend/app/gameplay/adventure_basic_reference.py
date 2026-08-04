"""Strict loader for the first executable adventure-basic package baseline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

from app.gameplay.ability_runtime import (
    AbilityAffordanceResolver,
    AbilityDefinitionRegistry,
    AbilityPathDefinition,
    AbilitySkillDefinition,
    AbilityStateProjector,
)
from app.gameplay.economy_runtime import EconomyAuthorityService
from app.gameplay.contract_runtime import (
    ContractAuthorityService,
    ContractProjector,
    ContractRuntimeError,
    ContractTermsDefinition,
    ContractTermsRegistry,
)
from app.gameplay.credential_runtime import CredentialAuthorityService, CredentialRuntimeError
from app.gameplay.debt_runtime import DebtAuthorityService, DebtProjector, DebtRuntimeError
from app.gameplay.equipment_runtime import (
    EquipmentAuthorityService,
    EquipmentContainerAccessAuthority,
    EquipmentDefinitionRegistry,
    EquipmentProfile,
    EquipmentProjector,
    EquipmentSlotDefinition,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.fixed_offer_purchase import FixedOfferAuthorityService, PurchaseRuntimeError
from app.gameplay.inventory_runtime import (
    ContainerSpec,
    EncumbranceProjection,
    InventoryAuthorityService,
    InventoryDefinitionRegistry,
    InventoryRuntimeError,
    InventoryProjector,
    ItemDefinition,
)
from app.gameplay.land_right_runtime import (
    LandRightRuntimeError,
    LandRightTransferAuthority,
    LandRightTransferPolicy,
)
from app.gameplay.gift_runtime import GiftAuthorityService, GiftRuntimeError
from app.gameplay.modifier_runtime import ModifierDefinitionRegistry, ModifierTemplate
from app.gameplay.ownership_runtime import OwnershipAuthorityService, OwnershipProjector
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRuntimeError
from app.gameplay.resource_body_runtime import (
    BodyRuntimeProjection,
    FunctionalCapacity,
    GameplayActionRequirement,
    GameplayActionSettlementCommand,
    ResourceBodyActionSettlementService,
    ResourceBodyRuntimeProjector,
)


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


@dataclass(frozen=True)
class StorageRingAccess:
    active: bool
    activation_id: str = ""
    container_id: str = ""


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
    def create(
        cls,
        *,
        player_copper: int = 120,
        store: GameplayEventStore | None = None,
    ) -> "AdventureBasicScenario1":
        """Create explicit reference seeds without activating a Patch or writing Godot state."""
        if store is None:
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
        ability_registry.register_path(
            AbilityPathDefinition(
                "path:swordsmanship.basic.swing",
                "skill:swordsmanship.basic",
                "action:sword.swing",
                stamina_resource_id="core.stamina",
                stamina_cost=12,
                required_function_id="grip.right",
            )
        )
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


class AdventureBasicScenario2:
    """Scenario 2 composition over the registered body, resource, and ability services."""

    stamina_resource_id = "core.stamina"
    stamina_cost = 12
    sword_action_ref = "action:sword.swing"
    right_arm_injury_id = "injury:adventure-basic:right-arm"
    _fixture_principal = "adventure_basic_scenario2_fixture"

    def __init__(self, base: AdventureBasicScenario1) -> None:
        self._base = base
        self.store = base.store
        self.inventory_registry = base.inventory_registry
        self.ability_registry = base.ability_registry
        self._projector = ResourceBodyRuntimeProjector()
        self._affordance_resolver = AbilityAffordanceResolver(self.ability_registry)
        self._action_settlement = ResourceBodyActionSettlementService(store=self.store)

    @classmethod
    def create(
        cls,
        *,
        stamina: int = 24,
        store: GameplayEventStore | None = None,
    ) -> "AdventureBasicScenario2":
        if stamina < 0 or stamina > 24:
            raise AdventureBasicScenarioError("adventure_basic_stamina_seed_invalid")
        scenario = cls(AdventureBasicScenario1.create(store=store))
        scenario._append_fixture_event(
            command_id="adventure-basic:scenario-2:seed-stamina",
            stream_id=f"gameplay:resources:{scenario.player_ref}",
            event_type="gameplay.resource.materialized",
            payload={
                "actor_ref": scenario.player_ref,
                "resource_id": scenario.stamina_resource_id,
                "minimum": 0,
                "maximum": 24,
                "current": stamina,
                "definition_version": "adventure-basic:1",
            },
        )
        return scenario

    @property
    def player_ref(self) -> str:
        return self._base.player_ref

    def purchase_sword(self):
        return self._base.purchase_sword()

    def equip_sword(self):
        return self._base.equip_sword()

    def resources(self):
        return self._projector.rebuild_resources(self.player_ref, self.store.read_events())

    def body(self):
        return self._projector.rebuild_body(self.player_ref, self.store.read_events())

    def abilities(self):
        return AbilityStateProjector(self.ability_registry).rebuild(self.player_ref, self.store.read_events())

    def affordance(self):
        return self._affordance_resolver.resolve(
            actor_ref=self.player_ref,
            action_ref=self.sword_action_ref,
            abilities=self.abilities(),
            resources=self.resources(),
            body=self.body(),
        )

    def apply_right_arm_injury(self):
        return self._append_fixture_event(
            command_id="adventure-basic:scenario-2:injure-right-arm",
            stream_id=f"gameplay:body:{self.player_ref}",
            event_type="gameplay.body.injury_applied",
            payload={
                "actor_ref": self.player_ref,
                "injury_id": self.right_arm_injury_id,
                "function_id": "grip.right",
                "capacity_ratio": 0,
            },
        )

    def recover_right_arm(self):
        return self._append_fixture_event(
            command_id="adventure-basic:scenario-2:recover-right-arm",
            stream_id=f"gameplay:body:{self.player_ref}",
            event_type="gameplay.body.injury_recovered",
            payload={
                "actor_ref": self.player_ref,
                "injury_id": self.right_arm_injury_id,
            },
        )

    def swing_sword(self):
        return self._action_settlement.settle(
            GameplayActionSettlementCommand(
                command_id="adventure-basic:scenario-2:sword-swing",
                actor_ref=self.player_ref,
                authority_principal="resource_body_action_authority",
                idempotency_key="adventure-basic:scenario-2:sword-swing",
                payload_digest="sha256:adventure-basic-scenario-2-sword-swing",
                causation_id="adventure-basic:scenario-2",
                correlation_id="adventure-basic:scenario-2",
                requirement=GameplayActionRequirement(
                    action_ref=self.sword_action_ref,
                    stamina_resource_id=self.stamina_resource_id,
                    stamina_cost=self.stamina_cost,
                    required_function_id="grip.right",
                ),
            ),
            resources=self.resources(),
            body=self.body(),
            enabled_group_ids=("core.resources", "core.body_runtime"),
        )

    def _append_fixture_event(
        self,
        *,
        command_id: str,
        stream_id: str,
        event_type: str,
        payload: dict[str, object],
    ):
        transaction_id = f"tx:{command_id}"
        digest_payload = {
            "command_id": command_id,
            "event_type": event_type,
            "payload": payload,
            "stream_id": stream_id,
        }
        digest = sha256(
            json.dumps(digest_payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        result = self.store.append_batch(
            {
                "transaction_id": transaction_id,
                "command_id": command_id,
                "expected_stream_revisions": {stream_id: self.store.get_stream_head(stream_id)},
                "pinned_revisions": {"adventure_basic_scenario_2": self.store.get_stream_head(stream_id)},
                "events": [
                    {
                        "event_id": f"evt:{command_id}:1",
                        "event_type": event_type,
                        "schema_version": 1,
                        "stream_id": stream_id,
                        "stream_revision": 0,
                        "global_sequence": 0,
                        "transaction_id": transaction_id,
                        "command_id": command_id,
                        "causation_id": "adventure-basic:scenario-2",
                        "correlation_id": "adventure-basic:scenario-2",
                        "visibility_policy": "authority_only",
                        "payload": payload,
                    }
                ],
                "idempotency_record": {
                    "principal_ref": self._fixture_principal,
                    "idempotency_key": command_id,
                    "payload_digest": f"sha256:{digest}",
                },
                "outbox_entries": [],
                "result_digest": f"sha256:{digest}",
                "projection_refresh_hints": [],
            }
        )
        if not result.committed:
            raise AdventureBasicScenarioError(
                result.failure.error_code if result.failure is not None else "adventure_basic_fixture_not_committed"
            )
        return result


class AdventureBasicScenario3:
    """Scenario 3 composition for equipment-gated internal storage and encumbrance."""

    storage_ring_item_id = "item:adventure-basic:storage-ring"
    storage_ring_definition_id = "item:adventure-basic:storage-ring"
    storage_ring_container_id = "container:adventure-basic:storage-ring-interior"
    storage_ring_weight = 1
    cargo_item_id = "item:adventure-basic:cargo"
    cargo_definition_id = "item:adventure-basic:cargo"
    cargo_weight = 12
    living_cargo_item_id = "item:adventure-basic:living-cargo"
    overflow_cargo_item_id = "item:adventure-basic:overflow-cargo"
    staging_container_id = "container:adventure-basic:staging"

    def __init__(
        self,
        *,
        base: AdventureBasicScenario1,
        inventory: InventoryAuthorityService,
        equipment: EquipmentAuthorityService,
        container_access: EquipmentContainerAccessAuthority,
    ) -> None:
        self._base = base
        self.store = base.store
        self.inventory_registry = base.inventory_registry
        self._inventory = inventory
        self._equipment = equipment
        self._container_access = container_access
        self._inventory_projector = InventoryProjector(base.inventory_registry)
        self._equipment_projector = EquipmentProjector()

    @classmethod
    def create(cls, *, store: GameplayEventStore | None = None) -> "AdventureBasicScenario3":
        base = AdventureBasicScenario1.create(store=store)
        inventory = InventoryAuthorityService(store=base.store, registry=base.inventory_registry)
        correlation_id = "adventure-basic:scenario-3"
        base.inventory_registry.register_item(ItemDefinition(cls.storage_ring_definition_id, "v1", cls.storage_ring_weight, 1))
        base.inventory_registry.register_item(ItemDefinition(cls.cargo_definition_id, "v1", cls.cargo_weight, 6))
        base.inventory_registry.register_item(ItemDefinition("item:adventure-basic:living-cargo", "v1", 1, 1, is_living=True))
        base.inventory_registry.register_item(ItemDefinition("item:adventure-basic:overflow-cargo", "v1", 21, 1))
        cls._require_committed(
            inventory.create_container(
                command_id="adventure-basic:scenario-3:seed-ring-interior",
                actor_ref=base.player_ref,
                spec=ContainerSpec(
                    cls.storage_ring_container_id,
                    20,
                    20,
                    4,
                    carrier_item_id=cls.storage_ring_item_id,
                    content_weight_propagation="exclude_contents",
                    allows_living_items=False,
                ),
                idempotency_key="adventure-basic:scenario-3:seed-ring-interior",
                causation_id="adventure-basic:scenario-3:seed",
                correlation_id=correlation_id,
            )
        )
        cls._require_committed(
            inventory.create_container(
                command_id="adventure-basic:scenario-3:seed-staging",
                actor_ref=base.player_ref,
                spec=ContainerSpec(cls.staging_container_id, 100, 100, 8),
                idempotency_key="adventure-basic:scenario-3:seed-staging",
                causation_id="adventure-basic:scenario-3:seed",
                correlation_id=correlation_id,
            )
        )
        for item_id, definition_id, container_id in (
            (cls.storage_ring_item_id, cls.storage_ring_definition_id, base.player_backpack_id),
            (cls.cargo_item_id, cls.cargo_definition_id, base.player_backpack_id),
            (cls.living_cargo_item_id, cls.living_cargo_item_id, cls.staging_container_id),
            (cls.overflow_cargo_item_id, cls.overflow_cargo_item_id, cls.staging_container_id),
        ):
            cls._require_committed(
                inventory.instantiate(
                    command_id=f"adventure-basic:scenario-3:seed:{item_id}",
                    actor_ref=base.player_ref,
                    item_id=item_id,
                    definition_id=definition_id,
                    quantity=1,
                    container_id=container_id,
                    idempotency_key=f"adventure-basic:scenario-3:seed:{item_id}",
                    causation_id="adventure-basic:scenario-3:seed",
                    correlation_id=correlation_id,
                )
            )
        equipment_registry = EquipmentDefinitionRegistry()
        equipment_registry.register_profile(
            cls.storage_ring_definition_id,
            EquipmentProfile(
                "profile:adventure-basic:storage-ring",
                ("finger",),
                container_access_container_ids=(cls.storage_ring_container_id,),
            ),
        )
        equipment = EquipmentAuthorityService(
            store=base.store,
            inventory_registry=base.inventory_registry,
            equipment_registry=equipment_registry,
            ability_registry=base.ability_registry,
            modifier_registry=base.modifier_registry,
            slots=(EquipmentSlotDefinition("finger"),),
        )
        return cls(
            base=base,
            inventory=inventory,
            equipment=equipment,
            container_access=EquipmentContainerAccessAuthority(
                store=base.store,
                inventory_registry=base.inventory_registry,
            ),
        )

    @property
    def player_ref(self) -> str:
        return self._base.player_ref

    @property
    def player_backpack_id(self) -> str:
        return self._base.player_backpack_id

    def equip_storage_ring(self):
        try:
            return self._equipment.equip(
                command_id="adventure-basic:scenario-3:equip-storage-ring",
                actor_ref=self.player_ref,
                item_id=self.storage_ring_item_id,
                source_container_id=self.player_backpack_id,
                slot_key="finger",
                body=self._body(),
                idempotency_key="adventure-basic:scenario-3:equip-storage-ring",
                causation_id="adventure-basic:scenario-3",
                correlation_id="adventure-basic:scenario-3",
            )
        except ValueError as exc:
            raise AdventureBasicScenarioError(str(exc)) from exc

    def unequip_storage_ring(self):
        access = self.storage_ring_access()
        if not access.active:
            raise AdventureBasicScenarioError("equipment_container_access_denied")
        try:
            return self._equipment.unequip(
                command_id="adventure-basic:scenario-3:unequip-storage-ring",
                actor_ref=self.player_ref,
                activation_id=access.activation_id,
                destination_container_id=self.player_backpack_id,
                body=self._body(),
                idempotency_key="adventure-basic:scenario-3:unequip-storage-ring",
                causation_id="adventure-basic:scenario-3",
                correlation_id="adventure-basic:scenario-3",
            )
        except ValueError as exc:
            raise AdventureBasicScenarioError(str(exc)) from exc

    def move_to_storage_ring(self, item_id: str):
        return self._move_with_storage_ring(
            command_suffix=f"to-ring:{item_id}",
            item_id=item_id,
            from_container_id=self._location_for(item_id),
            to_container_id=self.storage_ring_container_id,
        )

    def move_from_storage_ring(self, item_id: str):
        return self._move_with_storage_ring(
            command_suffix=f"from-ring:{item_id}",
            item_id=item_id,
            from_container_id=self.storage_ring_container_id,
            to_container_id=self.player_backpack_id,
        )

    def inventory(self):
        return self._inventory_projector.rebuild(self.player_ref, self.store.read_events())

    def encumbrance(self) -> EncumbranceProjection:
        access = self.storage_ring_access()
        carried_item_ids = (self.storage_ring_item_id,) if access.active else ()
        return self._inventory_projector.rebuild_encumbrance(
            self.inventory(),
            carrier_ref=self.player_ref,
            carried_container_ids=(self.player_backpack_id,),
            carried_item_ids=carried_item_ids,
        )

    def storage_ring_access(self) -> StorageRingAccess:
        equipment = self._equipment_projector.rebuild(self.player_ref, self.store.read_events())
        for activation in equipment.activations.values():
            if (
                activation.item_id == self.storage_ring_item_id
                and self.storage_ring_container_id in activation.container_access_container_ids
            ):
                return StorageRingAccess(True, activation.activation_id, self.storage_ring_container_id)
        return StorageRingAccess(False)

    def _move_with_storage_ring(
        self,
        *,
        command_suffix: str,
        item_id: str,
        from_container_id: str,
        to_container_id: str,
    ):
        access = self.storage_ring_access()
        if not access.active:
            raise AdventureBasicScenarioError("equipment_container_access_denied")
        command_id = f"adventure-basic:scenario-3:{command_suffix}"
        try:
            result = self._container_access.move(
                command_id=command_id,
                actor_ref=self.player_ref,
                activation_id=access.activation_id,
                item_id=item_id,
                from_container_id=from_container_id,
                to_container_id=to_container_id,
                idempotency_key=command_id,
                causation_id="adventure-basic:scenario-3",
                correlation_id="adventure-basic:scenario-3",
            )
        except ValueError as exc:
            raise AdventureBasicScenarioError(str(exc)) from exc
        if not result.committed:
            raise AdventureBasicScenarioError(
                result.failure.error_code if result.failure is not None else "adventure_basic_storage_ring_not_committed"
            )
        return result

    def _location_for(self, item_id: str) -> str:
        location = self.inventory().locations.get(item_id)
        if not location:
            raise AdventureBasicScenarioError("equipment_container_move_source_invalid")
        return location

    def _body(self) -> BodyRuntimeProjection:
        return BodyRuntimeProjection(
            self.player_ref,
            MappingProxyType({}),
            MappingProxyType({}),
            MappingProxyType({}),
            "adventure-basic:scenario-3:body",
        )

    @staticmethod
    def _require_committed(result: object) -> None:
        if not bool(getattr(result, "committed", False)):
            raise AdventureBasicScenarioError("adventure_basic_seed_not_committed")


class AdventureBasicScenario4:
    """Scenario 4 keeps deed location distinct from authority-owned land title."""

    land_deed_item_id = "item:adventure-basic:archive-plot-deed"
    land_deed_definition_id = "item:adventure-basic:archive-plot-deed"
    land_asset_ref = "asset:adventure-basic:archive-plot"
    land_right_id = "right:adventure-basic:archive-plot"
    land_offer_id = "offer:adventure-basic:archive-plot"
    land_deed_credential_id = "credential:adventure-basic:archive-plot-deed"
    world_deed_container_id = "container:world:archive-plot-deed"
    recipient_ref = "character:archive-steward"
    land_price = 100

    def __init__(
        self,
        *,
        base: AdventureBasicScenario1,
        inventory: InventoryAuthorityService,
        purchase_authority: FixedOfferAuthorityService,
        credential_authority: CredentialAuthorityService,
        land_right_authority: LandRightTransferAuthority,
    ) -> None:
        self._base = base
        self.store = base.store
        self.inventory_registry = base.inventory_registry
        self._inventory = inventory
        self._purchase_authority = purchase_authority
        self._credential_authority = credential_authority
        self._land_right_authority = land_right_authority
        self._inventory_projector = InventoryProjector(base.inventory_registry)
        self._ownership_projector = OwnershipProjector()
        self._transfer_expected_ownership_revision: int | None = None

    @classmethod
    def create(cls, *, store: GameplayEventStore | None = None) -> "AdventureBasicScenario4":
        base = AdventureBasicScenario1.create(player_copper=cls.land_price, store=store)
        inventory = InventoryAuthorityService(store=base.store, registry=base.inventory_registry)
        correlation_id = "adventure-basic:scenario-4"
        base.inventory_registry.register_item(
            ItemDefinition(cls.land_deed_definition_id, "v1", 1, 1)
        )
        cls._require_committed(
            inventory.create_container(
                command_id="adventure-basic:scenario-4:seed-world-deed-container",
                actor_ref=base.player_ref,
                spec=ContainerSpec(cls.world_deed_container_id, 4, 4, 1),
                idempotency_key="adventure-basic:scenario-4:seed-world-deed-container",
                causation_id="adventure-basic:scenario-4:seed",
                correlation_id=correlation_id,
            )
        )
        cls._require_committed(
            inventory.instantiate(
                command_id="adventure-basic:scenario-4:seed-land-deed",
                actor_ref=base.merchant_ref,
                item_id=cls.land_deed_item_id,
                definition_id=cls.land_deed_definition_id,
                quantity=1,
                container_id=base.merchant_stock_id,
                idempotency_key="adventure-basic:scenario-4:seed-land-deed",
                causation_id="adventure-basic:scenario-4:seed",
                correlation_id=correlation_id,
            )
        )
        ownership = OwnershipAuthorityService(store=base.store)
        cls._require_committed(
            ownership.grant_initial_title(
                command_id="adventure-basic:scenario-4:seed-land-title",
                asset_ref=cls.land_asset_ref,
                holder_ref=base.merchant_ref,
                right_id=cls.land_right_id,
                idempotency_key="adventure-basic:scenario-4:seed-land-title",
                causation_id="adventure-basic:scenario-4:seed",
                correlation_id=correlation_id,
            )
        )
        purchase_authority = FixedOfferAuthorityService(
            store=base.store,
            inventory_registry=base.inventory_registry,
        )
        cls._require_committed(
            purchase_authority.publish_offer(
                command_id="adventure-basic:scenario-4:seed-land-offer",
                offer_id=cls.land_offer_id,
                seller_ref=base.merchant_ref,
                asset_ref=cls.land_asset_ref,
                right_id=cls.land_right_id,
                item_id=cls.land_deed_item_id,
                source_container_id=base.merchant_stock_id,
                price_amount=cls.land_price,
                currency_ref=base.currency_ref,
                idempotency_key="adventure-basic:scenario-4:seed-land-offer",
                causation_id="adventure-basic:scenario-4:seed",
                correlation_id=correlation_id,
            )
        )
        return cls(
            base=base,
            inventory=inventory,
            purchase_authority=purchase_authority,
            credential_authority=CredentialAuthorityService(
                store=base.store,
                inventory_registry=base.inventory_registry,
            ),
            land_right_authority=LandRightTransferAuthority(
                store=base.store,
                inventory_registry=base.inventory_registry,
                policies=(
                    LandRightTransferPolicy(
                        asset_ref=cls.land_asset_ref,
                        credential_presence_container_ids=(base.player_backpack_id,),
                    ),
                ),
            ),
        )

    @property
    def player_ref(self) -> str:
        return self._base.player_ref

    @property
    def player_backpack_id(self) -> str:
        return self._base.player_backpack_id

    def purchase_land(self):
        offer = self._purchase_authority.offer_projection().offers[self.land_offer_id]
        try:
            return self._purchase_authority.purchase(
                command_id="adventure-basic:scenario-4:purchase-land",
                offer_id=self.land_offer_id,
                expected_offer_revision=offer.offer_revision,
                buyer_ref=self.player_ref,
                buyer_account_id=self._base.player_account_id,
                seller_account_id=self._base.merchant_account_id,
                destination_container_id=self.player_backpack_id,
                accepted_amount=self.land_price,
                accepted_currency_ref=self._base.currency_ref,
                idempotency_key="adventure-basic:scenario-4:purchase-land",
                causation_id="adventure-basic:scenario-4",
                correlation_id="adventure-basic:scenario-4",
            )
        except PurchaseRuntimeError as exc:
            raise AdventureBasicScenarioError(str(exc)) from exc

    def issue_deed_credential(self):
        try:
            return self._credential_authority.issue_credential(
                command_id="adventure-basic:scenario-4:issue-deed-credential",
                credential_id=self.land_deed_credential_id,
                credential_item_ref=self.land_deed_item_id,
                credential_holder_ref=self.player_ref,
                right_id=self.land_right_id,
                credential_kind="deed",
                proves="evidence_only",
                issuer_ref="authority:adventure-basic:land-registry",
                idempotency_key="adventure-basic:scenario-4:issue-deed-credential",
                causation_id="adventure-basic:scenario-4",
                correlation_id="adventure-basic:scenario-4",
            )
        except CredentialRuntimeError as exc:
            raise AdventureBasicScenarioError(str(exc)) from exc

    def drop_land_deed(self):
        return self._move_deed(
            command_id="adventure-basic:scenario-4:drop-land-deed",
            from_container_id=self.player_backpack_id,
            to_container_id=self.world_deed_container_id,
        )

    def retrieve_land_deed(self):
        return self._move_deed(
            command_id="adventure-basic:scenario-4:retrieve-land-deed",
            from_container_id=self.world_deed_container_id,
            to_container_id=self.player_backpack_id,
        )

    def transfer_land_right(self, *, expected_ownership_revision: int | None = None):
        if expected_ownership_revision is None:
            if self._transfer_expected_ownership_revision is None:
                self._transfer_expected_ownership_revision = self.store.get_stream_head(
                    "gameplay:ownership"
                )
            expected_ownership_revision = self._transfer_expected_ownership_revision
        try:
            return self._land_right_authority.transfer(
                command_id="adventure-basic:scenario-4:transfer-land-right",
                asset_ref=self.land_asset_ref,
                right_id=self.land_right_id,
                from_holder_ref=self.player_ref,
                to_holder_ref=self.recipient_ref,
                credential_id=self.land_deed_credential_id,
                expected_ownership_revision=expected_ownership_revision,
                idempotency_key="adventure-basic:scenario-4:transfer-land-right",
                causation_id="adventure-basic:scenario-4",
                correlation_id="adventure-basic:scenario-4",
            )
        except LandRightRuntimeError as exc:
            raise AdventureBasicScenarioError(str(exc)) from exc

    def inventory(self):
        return self._inventory_projector.rebuild(self.player_ref, self.store.read_events())

    def ownership(self):
        return self._ownership_projector.rebuild(self.store.read_events())

    def _move_deed(self, *, command_id: str, from_container_id: str, to_container_id: str):
        try:
            return self._inventory.move(
                command_id=command_id,
                actor_ref=self.player_ref,
                item_id=self.land_deed_item_id,
                from_container_id=from_container_id,
                to_container_id=to_container_id,
                idempotency_key=command_id,
                causation_id="adventure-basic:scenario-4",
                correlation_id="adventure-basic:scenario-4",
            )
        except InventoryRuntimeError as exc:
            raise AdventureBasicScenarioError(str(exc)) from exc

    @staticmethod
    def _require_committed(result: object) -> None:
        if not bool(getattr(result, "committed", False)):
            raise AdventureBasicScenarioError("adventure_basic_seed_not_committed")


class AdventureBasicScenario5:
    """Scenario 5 composes existing gift, debt, and typed-contract authorities."""

    recipient_ref = "character:archive-beneficiary"
    recipient_backpack_id = "container:archive-beneficiary:backpack"
    discarded_document_container_id = "container:adventure-basic:discarded-contract-documents"
    gift_item_id = "item:adventure-basic:archive-relic"
    gift_definition_id = "item:adventure-basic:archive-relic"
    gift_asset_ref = "asset:adventure-basic:archive-relic"
    gift_right_id = "right:adventure-basic:archive-relic"
    recipient_filler_item_id = "item:adventure-basic:recipient-filler"
    contract_document_item_id = "item:adventure-basic:archive-service-contract-document"
    contract_document_definition_id = "item:adventure-basic:archive-service-contract-document"
    debt_contract_id = "contract:adventure-basic:archive-credit"
    debt_id = "debt:adventure-basic:archive-credit"
    debt_principal = 30
    service_contract_id = "contract:adventure-basic:archive-service"
    service_terms_ref = "terms:adventure-basic:archive-service:v1"
    service_evidence_kind = "archive_service_completion"
    service_evidence_ref = "evidence:adventure-basic:archive-service:completed"
    _service_policy_authority = "authority:adventure-basic:archive-service"

    def __init__(
        self,
        *,
        base: AdventureBasicScenario1,
        inventory: InventoryAuthorityService,
        gift_authority: GiftAuthorityService,
        debt_authority: DebtAuthorityService,
        contract_authority: ContractAuthorityService,
    ) -> None:
        self._base = base
        self.store = base.store
        self.inventory_registry = base.inventory_registry
        self._inventory = inventory
        self._gift_authority = gift_authority
        self._debt_authority = debt_authority
        self._contract_authority = contract_authority
        self._inventory_projector = InventoryProjector(base.inventory_registry)
        self._ownership_projector = OwnershipProjector()
        self._debt_projector = DebtProjector()
        self._contract_projector = ContractProjector()

    @classmethod
    def create(cls, *, store: GameplayEventStore | None = None) -> "AdventureBasicScenario5":
        base = AdventureBasicScenario1.create(player_copper=100, store=store)
        inventory = InventoryAuthorityService(store=base.store, registry=base.inventory_registry)
        correlation_id = "adventure-basic:scenario-5"
        for definition in (
            ItemDefinition(cls.gift_definition_id, "v1", 1, 1),
            ItemDefinition(cls.contract_document_definition_id, "v1", 1, 1),
        ):
            base.inventory_registry.register_item(definition)
        cls._require_committed(
            inventory.create_container(
                command_id="adventure-basic:scenario-5:seed-recipient-backpack",
                actor_ref=cls.recipient_ref,
                spec=ContainerSpec(cls.recipient_backpack_id, 10, 10, 1),
                idempotency_key="adventure-basic:scenario-5:seed-recipient-backpack",
                causation_id="adventure-basic:scenario-5:seed",
                correlation_id=correlation_id,
            )
        )
        cls._require_committed(
            inventory.create_container(
                command_id="adventure-basic:scenario-5:seed-discarded-documents",
                actor_ref=base.player_ref,
                spec=ContainerSpec(cls.discarded_document_container_id, 4, 4, 2),
                idempotency_key="adventure-basic:scenario-5:seed-discarded-documents",
                causation_id="adventure-basic:scenario-5:seed",
                correlation_id=correlation_id,
            )
        )
        for item_id, definition_id in (
            (cls.gift_item_id, cls.gift_definition_id),
            (cls.contract_document_item_id, cls.contract_document_definition_id),
        ):
            cls._require_committed(
                inventory.instantiate(
                    command_id=f"adventure-basic:scenario-5:seed:{item_id}",
                    actor_ref=base.player_ref,
                    item_id=item_id,
                    definition_id=definition_id,
                    quantity=1,
                    container_id=base.player_backpack_id,
                    idempotency_key=f"adventure-basic:scenario-5:seed:{item_id}",
                    causation_id="adventure-basic:scenario-5:seed",
                    correlation_id=correlation_id,
                )
            )
        ownership = OwnershipAuthorityService(store=base.store)
        cls._require_committed(
            ownership.grant_initial_title(
                command_id="adventure-basic:scenario-5:seed-gift-title",
                asset_ref=cls.gift_asset_ref,
                holder_ref=base.player_ref,
                right_id=cls.gift_right_id,
                idempotency_key="adventure-basic:scenario-5:seed-gift-title",
                causation_id="adventure-basic:scenario-5:seed",
                correlation_id=correlation_id,
            )
        )
        terms_registry = ContractTermsRegistry()
        terms_registry.register(
            ContractTermsDefinition(
                cls.service_terms_ref,
                "simple_service",
                2,
                completion_evidence_kind=cls.service_evidence_kind,
            )
        )
        return cls(
            base=base,
            inventory=inventory,
            gift_authority=GiftAuthorityService(
                store=base.store,
                inventory_registry=base.inventory_registry,
            ),
            debt_authority=DebtAuthorityService(store=base.store),
            contract_authority=ContractAuthorityService(
                store=base.store,
                terms_registry=terms_registry,
                policy_authorities={cls._service_policy_authority},
            ),
        )

    @property
    def player_ref(self) -> str:
        return self._base.player_ref

    @property
    def player_backpack_id(self) -> str:
        return self._base.player_backpack_id

    def gift_archive_relic(self):
        try:
            return self._gift_authority.gift_asset(
                command_id="adventure-basic:scenario-5:gift-archive-relic",
                donor_ref=self.player_ref,
                recipient_ref=self.recipient_ref,
                asset_ref=self.gift_asset_ref,
                right_id=self.gift_right_id,
                item_id=self.gift_item_id,
                source_container_id=self.player_backpack_id,
                destination_container_id=self.recipient_backpack_id,
                idempotency_key="adventure-basic:scenario-5:gift-archive-relic",
                causation_id="adventure-basic:scenario-5",
                correlation_id="adventure-basic:scenario-5",
            )
        except GiftRuntimeError as exc:
            raise AdventureBasicScenarioError(str(exc)) from exc

    def fill_recipient_backpack(self):
        try:
            return self._inventory.instantiate(
                command_id="adventure-basic:scenario-5:fill-recipient-backpack",
                actor_ref=self.recipient_ref,
                item_id=self.recipient_filler_item_id,
                definition_id=self.gift_definition_id,
                quantity=1,
                container_id=self.recipient_backpack_id,
                idempotency_key="adventure-basic:scenario-5:fill-recipient-backpack",
                causation_id="adventure-basic:scenario-5",
                correlation_id="adventure-basic:scenario-5",
            )
        except InventoryRuntimeError as exc:
            raise AdventureBasicScenarioError(str(exc)) from exc

    def issue_archive_debt(self):
        try:
            return self._debt_authority.issue_simple_debt(
                command_id="adventure-basic:scenario-5:issue-archive-debt",
                contract_id=self.debt_contract_id,
                debt_id=self.debt_id,
                creditor_ref=self.player_ref,
                debtor_ref=self._base.merchant_ref,
                creditor_account_id=self._base.player_account_id,
                debtor_account_id=self._base.merchant_account_id,
                currency_ref=self._base.currency_ref,
                principal_amount=self.debt_principal,
                idempotency_key="adventure-basic:scenario-5:issue-archive-debt",
                causation_id="adventure-basic:scenario-5",
                correlation_id="adventure-basic:scenario-5",
            )
        except DebtRuntimeError as exc:
            raise AdventureBasicScenarioError(str(exc)) from exc

    def repay_archive_debt(self, amount: int):
        try:
            return self._debt_authority.pay_debt(
                command_id="adventure-basic:scenario-5:repay-archive-debt",
                debt_id=self.debt_id,
                debtor_account_id=self._base.merchant_account_id,
                creditor_account_id=self._base.player_account_id,
                amount=amount,
                idempotency_key="adventure-basic:scenario-5:repay-archive-debt",
                causation_id="adventure-basic:scenario-5",
                correlation_id="adventure-basic:scenario-5",
            )
        except DebtRuntimeError as exc:
            raise AdventureBasicScenarioError(str(exc)) from exc

    def create_service_contract(self):
        try:
            return self._contract_authority.create_contract(
                command_id="adventure-basic:scenario-5:create-service-contract",
                contract_id=self.service_contract_id,
                contract_type="simple_service",
                terms_ref=self.service_terms_ref,
                party_refs=(self.player_ref, self.recipient_ref),
                idempotency_key="adventure-basic:scenario-5:create-service-contract",
                causation_id="adventure-basic:scenario-5",
                correlation_id="adventure-basic:scenario-5",
            )
        except ContractRuntimeError as exc:
            raise AdventureBasicScenarioError(str(exc)) from exc

    def discard_contract_document(self):
        try:
            return self._inventory.move(
                command_id="adventure-basic:scenario-5:discard-contract-document",
                actor_ref=self.player_ref,
                item_id=self.contract_document_item_id,
                from_container_id=self.player_backpack_id,
                to_container_id=self.discarded_document_container_id,
                idempotency_key="adventure-basic:scenario-5:discard-contract-document",
                causation_id="adventure-basic:scenario-5",
                correlation_id="adventure-basic:scenario-5",
            )
        except InventoryRuntimeError as exc:
            raise AdventureBasicScenarioError(str(exc)) from exc

    def complete_service_contract(self, *, completion_evidence_kind: str | None = None):
        try:
            return self._contract_authority.complete_simple_service_by_policy(
                command_id="adventure-basic:scenario-5:complete-service-contract",
                contract_id=self.service_contract_id,
                authority_ref=self._service_policy_authority,
                completion_evidence_kind=(
                    self.service_evidence_kind
                    if completion_evidence_kind is None
                    else completion_evidence_kind
                ),
                completion_evidence_ref=self.service_evidence_ref,
                idempotency_key="adventure-basic:scenario-5:complete-service-contract",
                causation_id="adventure-basic:scenario-5",
                correlation_id="adventure-basic:scenario-5",
            )
        except ContractRuntimeError as exc:
            raise AdventureBasicScenarioError(str(exc)) from exc

    def inventory(self):
        return self._inventory_projector.rebuild(self.player_ref, self.store.read_events())

    def recipient_inventory(self):
        return self._inventory_projector.rebuild(self.recipient_ref, self.store.read_events())

    def ownership(self):
        return self._ownership_projector.rebuild(self.store.read_events())

    def debt(self):
        return self._debt_projector.rebuild(self.store.read_events())

    def contracts(self):
        return self._contract_projector.rebuild(self.store.read_events())

    @staticmethod
    def _require_committed(result: object) -> None:
        if not bool(getattr(result, "committed", False)):
            raise AdventureBasicScenarioError("adventure_basic_seed_not_committed")


__all__ = [
    "ADVENTURE_BASIC_PATCH_ID",
    "ADVENTURE_BASIC_PROFILE",
    "AdventureBasicScenario1",
    "AdventureBasicScenario2",
    "AdventureBasicScenario3",
    "AdventureBasicScenario4",
    "AdventureBasicScenario5",
    "AdventureBasicScenarioError",
    "StorageRingAccess",
    "load_adventure_basic_manifest",
]
