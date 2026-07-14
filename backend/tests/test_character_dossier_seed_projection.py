from __future__ import annotations

from app.character_agent.profile import (
    CharacterDossier,
    build_dossier_seed_initialization_bundle,
    capability_seed_candidates,
    relationship_seed_candidates,
)
from test_character_dossier_models import _minimal_dossier_payload


def _dossier() -> CharacterDossier:
    return CharacterDossier.model_validate(_minimal_dossier_payload())


def test_relationship_seed_candidates_are_explicit_social_memory_candidates() -> None:
    candidates = relationship_seed_candidates(_dossier())

    assert candidates == [
        {
            "candidate_type": "relationship_seed",
            "actor_id": "char_test",
            "target_actor_id": "char_b",
            "relation_tags": ["trusted_colleague"],
            "initial_trust": 0.68,
            "initial_affinity": 0.56,
            "initial_obligation": 0.34,
            "initial_tension": 0.18,
            "evidence_seeds": [
                {
                    "event_id": "rel_seed:char_test:char_b:kept_confidence",
                    "summary": "char_b kept a sensitive archive matter private",
                    "effect": {"trust": 0.18},
                }
            ],
            "candidate_only": True,
            "source_ref": "dossier:char_test:relationship_seed_profile:char_b",
        }
    ]


def test_capability_seed_candidates_are_explicit_skill_state_candidates() -> None:
    candidates = capability_seed_candidates(_dossier())

    assert candidates == [
        {
            "candidate_type": "capability_seed",
            "actor_id": "char_test",
            "skill_id": "social.mediation",
            "source": "authored",
            "rank": "trained",
            "proficiency": 0.74,
            "confidence": 0.81,
            "supports": [{"action_family": "social_deescalation"}],
            "requires": [{"condition": "has_speaking_turn"}],
            "blocked_by": ["public_humiliation"],
            "candidate_only": True,
            "source_ref": "dossier:char_test:capability_seed_profile:social.mediation",
        }
    ]


def test_dossier_seed_initialization_bundle_is_stable_candidate_envelope() -> None:
    bundle = build_dossier_seed_initialization_bundle(_dossier())

    assert bundle["actor_id"] == "char_test"
    assert len(bundle["relationship_seed_candidates"]) == 1
    assert len(bundle["capability_seed_candidates"]) == 1
    assert bundle["candidate_only"] is True
    assert bundle["does_not_persist"] is True
    assert bundle["source_refs"] == ["dossier:char_test"]


def test_seed_projection_helpers_do_not_mutate_dossier() -> None:
    dossier = _dossier()
    before = dossier.model_dump()

    relationship_seed_candidates(dossier)[0]["relation_tags"].append("mutated")
    capability_seed_candidates(dossier)[0]["supports"][0]["action_family"] = "mutated"
    build_dossier_seed_initialization_bundle(dossier)

    assert dossier.model_dump() == before
