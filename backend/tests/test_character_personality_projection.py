from __future__ import annotations

from app.character_agent.profile.personality_projection import (
    PERSONALITY_PROJECTION_KEYS,
    PersonalityProjectionResolver,
    resolve_personality_projection,
)


def _profile_payload() -> dict[str, object]:
    return {
        "personality_layer": {
            "big_five": {
                "openness": 0.62,
                "conscientiousness": 0.81,
                "extraversion": 0.46,
                "agreeableness": 0.78,
                "neuroticism": 0.34,
            },
            "facets": {
                "openness": {
                    "curiosity": 0.58,
                    "imagination": 0.44,
                    "ambiguity_tolerance": 0.61,
                    "novelty_seeking": 0.36,
                },
                "conscientiousness": {
                    "orderliness": 0.86,
                    "dutifulness": 0.82,
                    "deliberation": 0.79,
                    "persistence": 0.68,
                },
                "extraversion": {
                    "social_energy": 0.43,
                    "assertiveness": 0.35,
                    "warmth": 0.62,
                    "activity_level": 0.48,
                },
                "agreeableness": {
                    "compassion": 0.84,
                    "trust": 0.56,
                    "cooperativeness": 0.78,
                    "conflict_softening": 0.82,
                },
                "neuroticism": {
                    "anxiety": 0.36,
                    "shame_sensitivity": 0.42,
                    "volatility": 0.24,
                    "vulnerability": 0.38,
                },
            },
        },
        "trait_vector_layer": {
            "courage": 0.64,
            "scheming": 0.31,
            "empathy": 0.82,
            "rationality": 0.74,
            "sociability": 0.58,
        },
        "virtue_value_layer": {
            "value_priorities": ["care", "order", "trustworthiness", "privacy"],
            "red_lines": ["expose another person's private record casually"],
        },
        "conversation_personality_layer": {
            "social_openness": 0.57,
            "privacy_sensitivity": 0.63,
            "talk_initiative": 0.48,
            "deception_control": 0.87,
            "trust_threshold_for_private_talk": 0.66,
        },
        "temperament_response_layer": {
            "baseline_temperament": {
                "caution": 0.71,
                "dominance": 0.29,
                "attachment": 0.76,
                "emotional_reactivity": 0.44,
                "recovery_speed": 0.58,
                "impulse_control": 0.83,
            },
            "conflict_style": {
                "confrontation_tendency": 0.24,
                "avoidance_tendency": 0.46,
                "mediation_tendency": 0.88,
                "escalation_threshold": 0.74,
            },
            "trust_dynamics": {
                "initial_trust_bias": 0.56,
                "betrayal_memory_weight": 0.72,
                "forgiveness_threshold": 0.59,
                "loyalty_lock_in": 0.81,
            },
            "expression_bias": {
                "outward_warmth": 0.62,
                "emotional_transparency": 0.49,
                "facial_control": 0.71,
                "verbal_indirection": 0.64,
            },
        },
        "capability_constraint_layer": {
            "skills": ["observation", "mediation", "procedural recall"],
        },
    }


def test_resolver_emits_all_required_projection_keys() -> None:
    projection = resolve_personality_projection(_profile_payload())

    assert set(projection) == set(PERSONALITY_PROJECTION_KEYS)


def test_resolver_applies_documented_projection_formulas() -> None:
    projection = resolve_personality_projection(_profile_payload())

    assert projection["empathic_attunement"] == 0.7915
    assert projection["social_approach_bias"] == 0.525
    assert projection["analytical_control"] == 0.767
    assert projection["courage_bias"] == 0.5875
    assert projection["strategic_planning"] == 0.7484
    assert projection["manipulative_tendency"] == 0.201
    assert projection["conflict_deescalation_bias"] == 0.827
    assert projection["procedural_discipline"] == 0.812
    assert projection["stress_vulnerability"] == 0.387
    assert projection["public_assertion_bias"] == 0.3865
    assert projection["avoidance_bias"] == 0.4495
    assert projection["trust_repair_bias"] == 0.70315
    assert projection["privacy_guard_bias"] == 0.7135


def test_resolver_clamps_projection_values_to_unit_interval() -> None:
    profile = _profile_payload()
    profile["conversation_personality_layer"] = {
        "social_openness": 3.0,
        "privacy_sensitivity": 4.0,
        "deception_control": -2.0,
    }

    projection = resolve_personality_projection(profile)

    assert all(0.0 <= value <= 1.0 for value in projection.values())
    assert projection["privacy_guard_bias"] <= 1.0
    assert projection["manipulative_tendency"] >= 0.0


def test_legacy_flat_traits_are_used_as_fallback_inputs() -> None:
    projection = resolve_personality_projection(
        {
            "trait_vector_layer": {
                "courage": 0.9,
                "scheming": 0.8,
                "empathy": 0.7,
                "rationality": 0.6,
                "sociability": 0.4,
            }
        }
    )

    assert projection["courage_bias"] > 0.5
    assert projection["strategic_planning"] > projection["manipulative_tendency"]
    assert projection["empathic_attunement"] > 0.5
    assert projection["social_approach_bias"] < 0.5
    assert projection["analytical_control"] > 0.5


def test_scheming_is_split_into_strategy_and_manipulation_not_copied() -> None:
    low_scheming = resolve_personality_projection({"trait_vector_layer": {"scheming": 0.2}})
    high_scheming = resolve_personality_projection({"trait_vector_layer": {"scheming": 0.9}})

    assert high_scheming["strategic_planning"] > low_scheming["strategic_planning"]
    assert high_scheming["manipulative_tendency"] > low_scheming["manipulative_tendency"]
    assert high_scheming["strategic_planning"] != 0.9
    assert high_scheming["manipulative_tendency"] != 0.9


def test_projection_surface_does_not_emit_overlapping_raw_behavior_fields() -> None:
    projection = resolve_personality_projection(_profile_payload())

    assert "agreeableness" not in projection
    assert "empathy" not in projection
    assert "mediation_tendency" not in projection
    assert "scheming" not in projection


def test_missing_optional_layers_use_neutral_defaults_without_crashing() -> None:
    projection = PersonalityProjectionResolver().resolve({})

    assert set(projection) == set(PERSONALITY_PROJECTION_KEYS)
    assert all(0.0 <= value <= 1.0 for value in projection.values())
    assert projection["social_approach_bias"] == 0.5
    assert projection["stress_vulnerability"] == 0.5
