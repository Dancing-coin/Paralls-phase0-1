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
    OwnerDeclaration("daily_rhythm_runtime", "daily_rhythm_runtime"),
    OwnerDeclaration("economy", "actor_gameplay.econ1_economy_domain"),
    OwnerDeclaration("government", "actor_gameplay.government_domain"),
    OwnerDeclaration("organization", "actor_gameplay.organization_domain"),
    OwnerDeclaration("survival", "actor_gameplay.survival_domain"),
    OwnerDeclaration("construction_production", "actor_gameplay.construction_production_domain"),
    OwnerDeclaration("profile_activation", "world_runtime.activation_authority"),
    OwnerDeclaration("activation_survival_expiry", "world_runtime.activation_survival_expiry"),
))

__all__ = ["OWNER_REGISTRY", "OwnerDeclaration", "OwnerRegistry"]
