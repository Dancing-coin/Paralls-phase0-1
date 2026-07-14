from __future__ import annotations

from copy import deepcopy
from typing import Literal

from app.character_agent.profile.dossier_models import CharacterDossier


Audience = Literal["author", "self", "player", "l2", "l3", "l4"]
_AUDIENCES = {"author", "self", "player", "l2", "l3", "l4"}


def build_dossier_projection(
    dossier: CharacterDossier,
    *,
    audience: Audience,
) -> dict[str, object]:
    if audience not in _AUDIENCES:
        raise ValueError(f"Unsupported dossier projection audience: {audience}")

    return {
        "actor_id": dossier.actor_id,
        "identity": _identity_projection(dossier, audience),
        "embodiment": _embodiment_projection(dossier, audience),
        "authority": _authority_projection(dossier, audience),
        "private_truth": _private_truth_projection(dossier, audience),
        "relationship_seeds": _relationship_seed_projection(dossier, audience),
        "capability_seeds": _capability_seed_projection(dossier, audience),
        "source_refs": _source_refs(dossier),
    }


def _identity_projection(dossier: CharacterDossier, audience: str) -> dict[str, object]:
    identity = dossier.identity_profile
    if audience == "l4":
        return {"actor_id": dossier.actor_id}
    payload: dict[str, object] = {
        "actor_id": identity.actor_id or dossier.actor_id,
        "canonical_name": identity.canonical_name,
        "aliases": list(identity.aliases),
        "role_identities": identity.role_identities.model_dump(exclude_none=True),
        "self_concept": list(identity.self_concept),
    }
    if audience in {"author", "self", "l2"}:
        payload["demographic_identity"] = identity.demographic_identity.model_dump(
            exclude_none=True
        )
        payload["social_identities"] = identity.social_identities.model_dump(exclude_none=True)
        payload["perceived_identities"] = deepcopy(identity.perceived_identities)
    return payload


def _embodiment_projection(dossier: CharacterDossier, audience: str) -> dict[str, object]:
    embodiment = dossier.embodiment_profile
    payload: dict[str, object] = {
        "body_schema": embodiment.body_schema.model_dump(exclude_none=True),
        "motor_baseline": embodiment.motor_baseline.model_dump(exclude_none=True),
        "voice_baseline": embodiment.voice_baseline.model_dump(exclude_none=True),
        "default_posture": embodiment.default_posture,
        "realization_hints": deepcopy(embodiment.realization_hints),
    }
    if audience != "l4":
        payload["sensory_baseline"] = embodiment.sensory_baseline.model_dump(exclude_none=True)
        payload["visual_markers"] = list(embodiment.visual_markers)
        payload["chronic_conditions"] = list(embodiment.chronic_conditions)
    return {key: value for key, value in payload.items() if value not in (None, {}, [])}


def _authority_projection(dossier: CharacterDossier, audience: str) -> dict[str, object]:
    authority = dossier.authority_profile
    payload: dict[str, object] = {
        "responsibilities": list(authority.responsibilities),
        "allowed_actions": list(authority.allowed_actions),
        "forbidden_actions": list(authority.forbidden_actions),
        "escalation_targets": list(authority.escalation_targets),
    }
    if audience == "l4":
        return {
            "forbidden_actions": payload["forbidden_actions"],
            "allowed_actions": payload["allowed_actions"],
            "escalation_targets": payload["escalation_targets"],
        }
    return payload


def _private_truth_projection(dossier: CharacterDossier, audience: str) -> dict[str, object]:
    secrets = dossier.private_truth_profile.secrets
    if audience == "author":
        return {
            "secret_count": len(secrets),
            "truths": [
                {
                    "truth_id": secret.truth_id,
                    "content": secret.content,
                    "known_by": list(secret.known_by),
                    "unknown_to": list(secret.unknown_to),
                }
                for secret in secrets
            ],
        }
    if audience == "l2":
        visible = [
            secret
            for secret in secrets
            if _is_self_known(secret.known_by, dossier.actor_id)
            and secret.allowed_projection.get("l2", "summarized") != "hidden"
        ]
        return {
            "self_known_secret_count": len(visible),
            "visible_truth_ids": [secret.truth_id for secret in visible],
            "projection_mode": "summarized",
        }
    if audience == "l3":
        constrained = [
            secret
            for secret in secrets
            if _is_self_known(secret.known_by, dossier.actor_id)
            and secret.allowed_projection.get("l3") == "constraint_only"
        ]
        return {
            "constraint_secret_count": len(constrained),
            "constraint_truth_ids": [secret.truth_id for secret in constrained],
            "projection_mode": "constraint_only",
        }
    if audience == "player":
        visible = [
            secret
            for secret in secrets
            if secret.allowed_projection.get("player", "hidden") != "hidden"
        ]
        return {
            "visible_secret_count": len(visible),
            "visible_truth_ids": [secret.truth_id for secret in visible],
            "projection_mode": "player_filtered",
        }
    if audience == "self":
        visible = [secret for secret in secrets if _is_self_known(secret.known_by, dossier.actor_id)]
        return {
            "self_known_secret_count": len(visible),
            "visible_truth_ids": [secret.truth_id for secret in visible],
            "projection_mode": "self_belief_seed",
        }
    return {"hidden": True}


def _relationship_seed_projection(dossier: CharacterDossier, audience: str) -> dict[str, object]:
    relationships = dossier.relationship_seed_profile.relationships
    if audience == "l4":
        return {"candidate_only": True, "relationship_seed_count": len(relationships)}
    return {
        "candidate_only": True,
        "relationship_seed_count": len(relationships),
        "targets": [relationship.target_actor_id for relationship in relationships],
        "evidence_seed_count": sum(
            len(relationship.evidence_seeds) for relationship in relationships
        ),
    }


def _capability_seed_projection(dossier: CharacterDossier, audience: str) -> dict[str, object]:
    profile = dossier.capability_seed_profile
    skill_ids = [seed.skill_id for seed in profile.skill_seeds]
    payload: dict[str, object] = {
        "candidate_only": True,
        "skill_seed_count": len(profile.skill_seeds),
        "skill_ids": skill_ids,
        "knowledge_domains": list(profile.knowledge_domains),
        "constraint_count": sum(len(values) for values in profile.constraints.values()),
    }
    if audience == "l4":
        return {
            "candidate_only": True,
            "skill_seed_count": payload["skill_seed_count"],
            "constraint_count": payload["constraint_count"],
        }
    return payload


def _source_refs(dossier: CharacterDossier) -> list[str]:
    layer_versions = dossier.dossier_metadata.layer_versions
    refs = [dossier.dossier_id]
    for layer_id in (
        "identity_profile",
        "embodiment_profile",
        "authority_profile",
        "private_truth_profile",
        "relationship_seed_profile",
        "capability_seed_profile",
    ):
        version = layer_versions.get(layer_id, 1)
        refs.append(f"dossier_layer:{layer_id}:{version}")
    return refs


def _is_self_known(known_by: list[str], actor_id: str) -> bool:
    return actor_id in known_by or "self" in known_by


__all__ = ["Audience", "build_dossier_projection"]
