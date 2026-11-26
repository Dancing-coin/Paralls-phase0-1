from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OwnerDeclaration:
    owner_ref: str
    principal_ref: str


class OwnerRegistry:
    def __init__(self, declarations: tuple[OwnerDeclaration, ...]) -> None:
        self._declarations = {item.owner_ref: item for item in declarations}
        if len(self._declarations) != len(declarations):
            raise ValueError("owner_declaration_duplicate")

    def get(self, owner_ref: str) -> OwnerDeclaration:
        try:
            return self._declarations[owner_ref]
        except KeyError as exc:
            raise ValueError(f"owner_declaration_unknown:{owner_ref}") from exc


OWNER_REGISTRY = OwnerRegistry((
    OwnerDeclaration("world", "world_runtime.world_domain"),
    OwnerDeclaration("visual", "world_runtime.visual_domain"),
    OwnerDeclaration("esm_world", "world_runtime.esm_domain"),
    OwnerDeclaration("character", "character_agent.character_domain"),
    OwnerDeclaration("conversation", "character_agent.conversation_domain"),
    OwnerDeclaration("population", "population.population_domain"),
    OwnerDeclaration("daily_rhythm_runtime", "daily_rhythm_runtime"),
    OwnerDeclaration("econ1_economy", "actor_gameplay.econ1_economy_domain"),
    OwnerDeclaration("economy", "actor_gameplay.econ1_economy_domain"),
    OwnerDeclaration("government", "actor_gameplay.government_domain"),
    OwnerDeclaration("organization", "actor_gameplay.organization_domain"),
    OwnerDeclaration("survival", "actor_gameplay.survival_domain"),
    OwnerDeclaration("construction_production", "actor_gameplay.construction_production_domain"),
    OwnerDeclaration("profile_activation", "world_runtime.activation_authority"),
    OwnerDeclaration("activation_survival_expiry", "world_runtime.activation_survival_expiry"),
    OwnerDeclaration("inventory", "actor_gameplay.inventory_domain"),
    OwnerDeclaration("body", "actor_gameplay.body_domain"),
    OwnerDeclaration("equipment", "actor_gameplay.equipment_domain"),
    OwnerDeclaration("lifestate", "authority:character:life-state"),
    OwnerDeclaration("life_state", "authority:character:life-state"),
    OwnerDeclaration("presence", "population.presence_authority"),
    OwnerDeclaration("ownership", "actor_gameplay.ownership_domain"),
    OwnerDeclaration("resource_scene", "actor_gameplay.resource_scene_domain"),
    OwnerDeclaration("resource_body", "actor_gameplay.resource_body_domain"),
    OwnerDeclaration("ability", "actor_gameplay.skill_domain"),
    OwnerDeclaration("action_consequence", "actor_gameplay.action_consequence_domain"),
    OwnerDeclaration("action_window", "actor_gameplay.action_window_domain"),
    OwnerDeclaration("adventure_basic_mirror", "actor_gameplay.adventure_basic_mirror_domain"),
    OwnerDeclaration("bakery_reference", "actor_gameplay.bakery_reference_domain"),
    OwnerDeclaration("civilization_capability", "authority:civilization_capability"),
    OwnerDeclaration("contract", "actor_gameplay.contract_domain"),
    OwnerDeclaration("credential", "actor_gameplay.credential_domain"),
    OwnerDeclaration("debt", "actor_gameplay.debt_domain"),
    OwnerDeclaration("ecology_platform", "actor_gameplay.ecology_platform_domain"),
    OwnerDeclaration("ecology", "authority:ecology"),
    OwnerDeclaration("frost_farm", "actor_gameplay.frost_farm_domain"),
    OwnerDeclaration("gift", "actor_gameplay.gift_domain"),
    OwnerDeclaration("government_treasury", "actor_gameplay.government_treasury_domain"),
    OwnerDeclaration("inventory_platform", "actor_gameplay.inventory_platform_domain"),
    OwnerDeclaration("land_right", "actor_gameplay.land_right_transfer_domain"),
    OwnerDeclaration("modifier", "actor_gameplay.modifier_domain"),
    OwnerDeclaration("economy_platform", "actor_gameplay.economy_platform_domain"),
    OwnerDeclaration("economy_runtime", "actor_gameplay.economy_domain"),
    OwnerDeclaration("organization_government", "actor_gameplay.organization_government_domain"),
    OwnerDeclaration("organization_government_social_platform", "actor_gameplay.organization_government_social_platform_domain"),
    OwnerDeclaration("patch", "actor_gameplay.patch_domain"),
    OwnerDeclaration("reference_data", "actor_gameplay.reference_data_domain"),
    OwnerDeclaration("soul_effect", "actor_gameplay.soul_effect_domain"),
    OwnerDeclaration("soul_fact", "actor_gameplay.soul_fact_domain"),
    OwnerDeclaration("soul", "actor_gameplay.soul_domain"),
))

__all__ = ["OWNER_REGISTRY", "OwnerDeclaration", "OwnerRegistry"]
