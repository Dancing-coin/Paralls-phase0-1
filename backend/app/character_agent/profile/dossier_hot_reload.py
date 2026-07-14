from __future__ import annotations

from copy import deepcopy

from pydantic import BaseModel, ConfigDict, Field

from app.character_agent.profile.dossier_models import CharacterDossier


_DOES_NOT_MUTATE = [
    "need_tension_state",
    "dynamic_state",
    "body_runtime_state",
    "current_goal_state",
    "memory_store",
    "relationship_graph",
    "character_skill_state",
]

_INVALIDATIONS_BY_LAYER = {
    "identity_profile": ["identity_projection", "effective_profile_projection"],
    "embodiment_profile": [
        "embodiment_projection",
        "physical_feasibility_projection",
        "skill_affordance_projection",
    ],
    "authority_profile": ["authority_projection", "planning_constraint_projection"],
    "private_truth_profile": ["private_truth_projection", "visibility_projection"],
    "relationship_seed_profile": [
        "relationship_seed_projection",
        "relationship_context_projection",
    ],
    "capability_seed_profile": [
        "capability_seed_projection",
        "skill_affordance_projection",
    ],
}


class DossierHotReloadResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    layer_id: str
    previous_layer_version: int = Field(ge=1)
    next_layer_version: int = Field(ge=1)
    invalidates: list[str]
    does_not_mutate: list[str]
    dossier: CharacterDossier


def replace_dossier_layer(
    dossier: CharacterDossier,
    *,
    layer_id: str,
    layer_payload: dict[str, object],
) -> DossierHotReloadResult:
    if layer_id not in _INVALIDATIONS_BY_LAYER:
        raise ValueError(f"Unsupported dossier layer for hot reload: {layer_id}")

    payload = deepcopy(dossier.model_dump())
    metadata = payload.setdefault("dossier_metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
        payload["dossier_metadata"] = metadata
    layer_versions = metadata.setdefault("layer_versions", {})
    if not isinstance(layer_versions, dict):
        layer_versions = {}
        metadata["layer_versions"] = layer_versions

    previous_layer_version = int(layer_versions.get(layer_id, 1))
    next_layer_version = previous_layer_version + 1
    payload[layer_id] = deepcopy(layer_payload)
    layer_versions[layer_id] = next_layer_version

    next_dossier = CharacterDossier.model_validate(payload)
    return DossierHotReloadResult(
        actor_id=dossier.actor_id,
        layer_id=layer_id,
        previous_layer_version=previous_layer_version,
        next_layer_version=next_layer_version,
        invalidates=list(_INVALIDATIONS_BY_LAYER[layer_id]),
        does_not_mutate=list(_DOES_NOT_MUTATE),
        dossier=next_dossier,
    )


__all__ = ["DossierHotReloadResult", "replace_dossier_layer"]
