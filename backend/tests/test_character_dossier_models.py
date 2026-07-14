import pytest
from pydantic import ValidationError

from app.character_agent.profile import CharacterDossier, CharacterProfile


def _minimal_character_profile_payload() -> dict[str, object]:
    return {
        "identity_core": {
            "character_id": "char_test",
            "canonical_name": "Test Character",
            "aliases": ["Tester"],
            "occupation_role": "archive attendant",
        },
        "origin_seed": {
            "homeland": "test quarter",
            "formative_context": "trained in archives",
            "current_scene_function": "test anchor",
        },
        "life_memory_backbone": {
            "defining_memories": ["kept a record safe"],
            "unresolved_knots": ["fears procedural failure"],
        },
        "virtue_value_layer": {
            "value_priorities": ["care", "order"],
            "red_lines": ["casually expose private records"],
            "forbidden_behaviors": ["fabricate authority"],
        },
        "trait_vector_layer": {
            "courage": 0.6,
            "scheming": 0.2,
            "empathy": 0.8,
            "rationality": 0.7,
            "sociability": 0.5,
        },
        "capability_constraint_layer": {
            "skills": ["mediation"],
            "knowledge_domains": ["archive routine"],
            "physical_constraints": ["low sprint stamina"],
            "psychological_constraints": ["avoids escalation"],
            "social_constraints": ["cannot authorize sealed access alone"],
        },
        "style_expression_bias_layer": {
            "speech_style": "measured",
            "silence_pattern": "pauses before sensitive answers",
            "gesture_bias": "contained",
            "posture_bias": "upright",
        },
        "conversation_personality_layer": {
            "social_openness": 0.5,
            "privacy_sensitivity": 0.7,
            "talk_initiative": 0.4,
            "deception_control": 0.9,
            "trust_threshold_for_private_talk": 0.7,
        },
        "need_hierarchy_layer": {
            "base_weights": {
                "physiological": 0.2,
                "safety": 0.7,
                "belonging": 0.8,
                "esteem": 0.5,
                "self_actualization": 0.4,
            },
            "deprivation_sensitivity": {
                "physiological": 0.3,
                "safety": 0.8,
                "belonging": 0.8,
                "esteem": 0.5,
                "self_actualization": 0.4,
            },
            "satisfaction_sensitivity": {
                "physiological": 0.3,
                "safety": 0.7,
                "belonging": 0.8,
                "esteem": 0.6,
                "self_actualization": 0.5,
            },
            "dominant_drives": ["preserve trust"],
        },
        "temperament_response_layer": {
            "baseline_temperament": {
                "caution": 0.7,
                "dominance": 0.3,
                "attachment": 0.7,
                "emotional_reactivity": 0.4,
                "recovery_speed": 0.6,
                "impulse_control": 0.8,
            },
            "conflict_style": {
                "confrontation_tendency": 0.2,
                "avoidance_tendency": 0.4,
                "mediation_tendency": 0.8,
                "escalation_threshold": 0.7,
            },
            "defense_patterns": {
                "under_pressure": ["procedural control"],
                "under_shame": ["withdrawal"],
                "under_threat": ["vigilance"],
                "under_loss": ["private grief"],
            },
            "trust_dynamics": {
                "initial_trust_bias": 0.5,
                "betrayal_memory_weight": 0.7,
                "forgiveness_threshold": 0.6,
                "loyalty_lock_in": 0.8,
            },
            "expression_bias": {
                "outward_warmth": 0.6,
                "emotional_transparency": 0.5,
                "facial_control": 0.7,
                "verbal_indirection": 0.6,
            },
        },
    }


def _minimal_dossier_payload() -> dict[str, object]:
    return {
        "dossier_id": "dossier:char_test",
        "actor_id": "char_test",
        "schema_version": "character_dossier.v1",
        "identity_profile": {
            "actor_id": "char_test",
            "canonical_name": "Test Character",
            "aliases": ["Tester"],
            "demographic_identity": {
                "age_band": "young_adult",
                "gender_identity": "female",
            },
            "role_identities": {
                "occupational_role": "archive_attendant",
                "scene_role": "test_anchor",
                "authority_role": "archive_procedure_keeper",
            },
        },
        "embodiment_profile": {
            "body_schema": {
                "body_type": "slight",
                "height_band": "average",
                "dominant_hand": "right",
            },
            "sensory_baseline": {"vision": "normal", "hearing": "attentive"},
            "motor_baseline": {
                "sprint_capacity": "low",
                "fine_motor_control": "high",
                "load_bearing": "low",
            },
            "voice_baseline": {"volume": "low", "tone": "soft"},
        },
        "authority_profile": {
            "responsibilities": ["maintain_archive_order"],
            "allowed_actions": ["explain_public_procedure"],
            "forbidden_actions": ["grant_sealed_access_alone"],
            "escalation_targets": ["senior_archivist"],
        },
        "private_truth_profile": {
            "secrets": [
                {
                    "truth_id": "secret:char_test:omission_fear",
                    "content": "fears one omission could damage trust",
                    "known_by": ["author", "char_test"],
                    "unknown_to": ["public"],
                    "allowed_projection": {
                        "l2": "summarized",
                        "l3": "constraint_only",
                        "player": "hidden",
                    },
                }
            ]
        },
        "relationship_seed_profile": {
            "relationships": [
                {
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
                }
            ]
        },
        "capability_seed_profile": {
            "skill_seeds": [
                {
                    "skill_id": "social.mediation",
                    "source": "authored",
                    "rank": "trained",
                    "proficiency": 0.74,
                    "confidence": 0.81,
                    "supports": [{"action_family": "social_deescalation"}],
                    "requires": [{"condition": "has_speaking_turn"}],
                    "blocked_by": ["public_humiliation"],
                }
            ],
            "knowledge_domains": ["archive_routine"],
            "constraints": {
                "physical": ["low_sprint_stamina"],
                "social": ["cannot_authorize_sealed_access_alone"],
            },
        },
        "character_profile": _minimal_character_profile_payload(),
    }


def test_character_dossier_wraps_existing_character_profile() -> None:
    dossier = CharacterDossier.model_validate(_minimal_dossier_payload())

    assert dossier.actor_id == "char_test"
    assert isinstance(dossier.character_profile, CharacterProfile)
    assert dossier.character_profile.identity_core.character_id == "char_test"
    assert dossier.identity_profile.role_identities.occupational_role == "archive_attendant"


def test_character_dossier_rejects_actor_mismatch() -> None:
    payload = _minimal_dossier_payload()
    character_profile = payload["character_profile"]
    assert isinstance(character_profile, dict)
    identity_core = character_profile["identity_core"]
    assert isinstance(identity_core, dict)
    identity_core["character_id"] = "other_actor"

    with pytest.raises(ValidationError, match="actor_id"):
        CharacterDossier.model_validate(payload)


def test_character_dossier_rejects_invalid_scalar_skill_seed() -> None:
    payload = _minimal_dossier_payload()
    capability_seed_profile = payload["capability_seed_profile"]
    assert isinstance(capability_seed_profile, dict)
    skill_seeds = capability_seed_profile["skill_seeds"]
    assert isinstance(skill_seeds, list)
    skill_seeds[0]["proficiency"] = 1.5

    with pytest.raises(ValidationError):
        CharacterDossier.model_validate(payload)


def test_private_truth_projection_policy_rejects_unknown_value() -> None:
    payload = _minimal_dossier_payload()
    private_truth_profile = payload["private_truth_profile"]
    assert isinstance(private_truth_profile, dict)
    secrets = private_truth_profile["secrets"]
    assert isinstance(secrets, list)
    secrets[0]["allowed_projection"]["l2"] = "omniscient"

    with pytest.raises(ValidationError):
        CharacterDossier.model_validate(payload)
