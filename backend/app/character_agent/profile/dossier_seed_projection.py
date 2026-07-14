from __future__ import annotations

from copy import deepcopy

from app.character_agent.profile.dossier_models import CharacterDossier


def relationship_seed_candidates(dossier: CharacterDossier) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for relationship in dossier.relationship_seed_profile.relationships:
        candidates.append(
            {
                "candidate_type": "relationship_seed",
                "actor_id": dossier.actor_id,
                "target_actor_id": relationship.target_actor_id,
                "relation_tags": list(relationship.relation_tags),
                "initial_trust": relationship.initial_trust,
                "initial_affinity": relationship.initial_affinity,
                "initial_obligation": relationship.initial_obligation,
                "initial_tension": relationship.initial_tension,
                "evidence_seeds": [
                    seed.model_dump() for seed in relationship.evidence_seeds
                ],
                "candidate_only": True,
                "source_ref": (
                    f"{dossier.dossier_id}:relationship_seed_profile:"
                    f"{relationship.target_actor_id}"
                ),
            }
        )
    return candidates


def capability_seed_candidates(dossier: CharacterDossier) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for seed in dossier.capability_seed_profile.skill_seeds:
        candidates.append(
            {
                "candidate_type": "capability_seed",
                "actor_id": dossier.actor_id,
                "skill_id": seed.skill_id,
                "source": seed.source,
                "rank": seed.rank,
                "proficiency": seed.proficiency,
                "confidence": seed.confidence,
                "supports": [support.model_dump() for support in seed.supports],
                "requires": [requirement.model_dump() for requirement in seed.requires],
                "blocked_by": list(seed.blocked_by),
                "candidate_only": True,
                "source_ref": f"{dossier.dossier_id}:capability_seed_profile:{seed.skill_id}",
            }
        )
    return candidates


def build_dossier_seed_initialization_bundle(
    dossier: CharacterDossier,
) -> dict[str, object]:
    return {
        "actor_id": dossier.actor_id,
        "relationship_seed_candidates": deepcopy(relationship_seed_candidates(dossier)),
        "capability_seed_candidates": deepcopy(capability_seed_candidates(dossier)),
        "candidate_only": True,
        "does_not_persist": True,
        "source_refs": [dossier.dossier_id],
    }


__all__ = [
    "build_dossier_seed_initialization_bundle",
    "capability_seed_candidates",
    "relationship_seed_candidates",
]
