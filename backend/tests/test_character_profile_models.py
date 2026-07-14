from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.character_agent.profile import CharacterProfile


PROFILE_DIR = Path(__file__).resolve().parents[1].parent / "assets" / "characters" / "profiles"


def _load_profile(name: str) -> dict[str, object]:
    with (PROFILE_DIR / name).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _make_minimal_stage2_payload() -> dict[str, object]:
    return {
        "identity_core": {
            "character_id": "char_test",
            "canonical_name": "Character Test",
            "aliases": ["Test"],
            "occupation_role": "court_figure",
        },
        "origin_seed": {},
        "life_memory_backbone": {},
        "virtue_value_layer": {
            "value_priorities": ["authority", "stability"],
            "red_lines": ["betray sworn trust"],
            "forbidden_behaviors": ["fabricate evidence"],
        },
        "trait_vector_layer": {
            "courage": 0.62,
            "scheming": 0.58,
            "empathy": 0.7,
            "rationality": 0.71,
            "sociability": 0.44,
        },
        "capability_constraint_layer": {
            "skills": ["observation", "rhetoric"],
            "knowledge_domains": ["court", "ritual"],
            "physical_constraints": ["limited endurance"],
            "psychological_constraints": ["hesitates under chaos"],
            "social_constraints": ["cannot break rank casually"],
        },
        "style_expression_bias_layer": {
            "speech_style": "formal",
            "silence_pattern": "strategic",
            "gesture_bias": "minimal gesture",
            "posture_bias": "still and balanced",
        },
        "conversation_personality_layer": {
            "social_openness": 0.31,
            "privacy_sensitivity": 0.77,
            "talk_initiative": 0.46,
            "deception_control": 0.69,
            "trust_threshold_for_private_talk": 0.82,
        },
        "need_hierarchy_layer": {
            "base_weights": {
                "physiological": 0.28,
                "safety": 0.79,
                "belonging": 0.64,
                "esteem": 0.57,
                "self_actualization": 0.43,
            },
            "deprivation_sensitivity": {
                "physiological": 0.35,
                "safety": 0.84,
                "belonging": 0.68,
                "esteem": 0.59,
                "self_actualization": 0.39,
            },
            "satisfaction_sensitivity": {
                "physiological": 0.32,
                "safety": 0.77,
                "belonging": 0.73,
                "esteem": 0.61,
                "self_actualization": 0.52,
            },
            "dominant_drives": ["preserve_order", "protect_trust"],
            "satisfaction_channels": {
                "physiological": ["steady rest"],
                "safety": ["clear protocol"],
                "belonging": ["trusted company"],
                "esteem": ["competent recognition"],
                "self_actualization": ["meaningful duty"],
            },
            "frustration_channels": {
                "physiological": ["exhaustion"],
                "safety": ["ambiguous threat"],
                "belonging": ["social exclusion"],
                "esteem": ["public dismissal"],
                "self_actualization": ["stalled contribution"],
            },
        },
        "temperament_response_layer": {
            "baseline_temperament": {
                "caution": 0.66,
                "dominance": 0.41,
                "attachment": 0.62,
                "emotional_reactivity": 0.48,
                "recovery_speed": 0.57,
                "impulse_control": 0.81,
            },
            "conflict_style": {
                "confrontation_tendency": 0.29,
                "avoidance_tendency": 0.43,
                "mediation_tendency": 0.74,
                "escalation_threshold": 0.71,
            },
            "defense_patterns": {
                "under_pressure": ["procedural control"],
                "under_shame": ["silence"],
                "under_threat": ["vigilance"],
                "under_loss": ["withdrawal"],
            },
            "trust_dynamics": {
                "initial_trust_bias": 0.44,
                "betrayal_memory_weight": 0.73,
                "forgiveness_threshold": 0.51,
                "loyalty_lock_in": 0.68,
            },
            "expression_bias": {
                "outward_warmth": 0.47,
                "emotional_transparency": 0.34,
                "facial_control": 0.76,
                "verbal_indirection": 0.63,
            },
        },
    }


def test_character_profile_requires_stage2_identity_and_runtime_layers() -> None:
    payload = _make_minimal_stage2_payload()
    del payload["need_hierarchy_layer"]
    del payload["temperament_response_layer"]

    with pytest.raises(ValidationError) as exc_info:
        CharacterProfile.model_validate(payload)

    message = str(exc_info.value)
    assert "need_hierarchy_layer" in message
    assert "temperament_response_layer" in message


def test_character_profile_accepts_minimal_stage2_payload() -> None:
    profile = CharacterProfile.model_validate(_make_minimal_stage2_payload())

    assert profile.identity_core.character_id == "char_test"
    assert profile.trait_vector_layer.empathy == 0.7
    assert profile.capability_constraint_layer.social_constraints == ["cannot break rank casually"]
    assert profile.need_hierarchy_layer.base_weights.safety == 0.79
    assert profile.temperament_response_layer.baseline_temperament.caution == 0.66
    assert profile.long_term_personality_drift_layer.drift_policy.require_non_transient_evidence is True
    assert profile.runtime_defaults.default_control_mode == "agent_full_auto"


def test_character_profile_accepts_runtime_default_control_mode() -> None:
    payload = _make_minimal_stage2_payload()
    payload["runtime_defaults"] = {"default_control_mode": "player_priority_assisted"}

    profile = CharacterProfile.model_validate(payload)

    assert profile.runtime_defaults.default_control_mode == "player_priority_assisted"


@pytest.mark.parametrize(
    ("field_name", "value"),
    [("empathy", 1.1), ("courage", -0.1)],
)
def test_character_profile_rejects_out_of_range_trait_scalars(field_name: str, value: float) -> None:
    payload = _make_minimal_stage2_payload()
    payload["trait_vector_layer"][field_name] = value  # type: ignore[index]

    with pytest.raises(ValidationError) as exc_info:
        CharacterProfile.model_validate(payload)

    assert field_name in str(exc_info.value)


@pytest.mark.parametrize(
    ("layer_name", "field_name", "value"),
    [
        ("base_weights", "safety", 1.1),
        ("deprivation_sensitivity", "belonging", -0.1),
    ],
)
def test_character_profile_rejects_out_of_range_need_scalars(
    layer_name: str, field_name: str, value: float
) -> None:
    payload = _make_minimal_stage2_payload()
    payload["need_hierarchy_layer"][layer_name][field_name] = value  # type: ignore[index]

    with pytest.raises(ValidationError) as exc_info:
        CharacterProfile.model_validate(payload)

    message = str(exc_info.value)
    assert "need_hierarchy_layer" in message
    assert field_name in message


def test_character_profile_rejects_out_of_range_temperament_scalars() -> None:
    payload = _make_minimal_stage2_payload()
    payload["temperament_response_layer"]["baseline_temperament"]["caution"] = 1.1  # type: ignore[index]

    with pytest.raises(ValidationError) as exc_info:
        CharacterProfile.model_validate(payload)

    message = str(exc_info.value)
    assert "baseline_temperament" in message
    assert "caution" in message


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("minimum_cross_scene_count", 0),
        ("minimum_confirming_events", -1),
        ("minimum_time_span", "short_arc"),
    ],
)
def test_character_profile_rejects_invalid_drift_policy_values(
    field_name: str, value: object
) -> None:
    payload = _make_minimal_stage2_payload()
    payload["long_term_personality_drift_layer"] = {
        "stable_shifts": [],
        "reinforced_patterns": [],
        "weakened_patterns": [],
        "need_reweights": {},
        "trust_reweights": {},
        "expression_reweights": {},
        "drift_policy": {
            "minimum_cross_scene_count": 3,
            "minimum_confirming_events": 6,
            "minimum_time_span": "long_arc",
            "require_non_transient_evidence": True,
        },
    }
    payload["long_term_personality_drift_layer"]["drift_policy"][field_name] = value  # type: ignore[index]

    with pytest.raises(ValidationError) as exc_info:
        CharacterProfile.model_validate(payload)

    message = str(exc_info.value)
    assert "drift_policy" in message
    assert field_name in message


def test_character_profile_rejects_unknown_top_level_key() -> None:
    payload = _make_minimal_stage2_payload()
    payload["unexpected_top_level"] = {"debug": True}

    with pytest.raises(ValidationError) as exc_info:
        CharacterProfile.model_validate(payload)

    assert "unexpected_top_level" in str(exc_info.value)


@pytest.mark.parametrize(
    ("layer_name", "extra_key", "extra_value"),
    [
        ("identity_core", "nickname_override", "Shadow Name"),
        ("style_expression_bias_layer", "untracked_visual_hint", "tilts head dramatically"),
        ("temperament_response_layer", "untracked_reaction_bias", "dramatic"),
    ],
)
def test_character_profile_rejects_unknown_nested_keys(
    layer_name: str, extra_key: str, extra_value: object
) -> None:
    payload = _make_minimal_stage2_payload()
    payload[layer_name][extra_key] = extra_value  # type: ignore[index]

    with pytest.raises(ValidationError) as exc_info:
        CharacterProfile.model_validate(payload)

    message = str(exc_info.value)
    assert layer_name in message
    assert extra_key in message


def test_character_profile_rejects_unknown_runtime_default_control_mode() -> None:
    payload = _make_minimal_stage2_payload()
    payload["runtime_defaults"] = {"default_control_mode": "manual_override"}

    with pytest.raises(ValidationError) as exc_info:
        CharacterProfile.model_validate(payload)

    assert "default_control_mode" in str(exc_info.value)


@pytest.mark.parametrize("profile_name", ["char_a.yaml", "char_b.yaml", "char_c.yaml"])
def test_character_profile_examples_validate(profile_name: str) -> None:
    payload = _load_profile(profile_name)

    profile = CharacterProfile.model_validate(payload)

    assert profile.identity_core.character_id
    assert profile.identity_core.canonical_name
    assert profile.trait_vector_layer.courage >= 0.0
    assert profile.capability_constraint_layer.physical_constraints
    assert profile.style_expression_bias_layer.gesture_bias
    assert profile.conversation_personality_layer.social_openness >= 0.0
    if profile_name == "char_c.yaml":
        assert profile.runtime_defaults.default_control_mode == "player_priority_assisted"
    else:
        assert profile.runtime_defaults.default_control_mode == "agent_full_auto"
