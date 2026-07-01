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
    }


def test_character_profile_requires_stage2_identity_and_trait_layers() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CharacterProfile.model_validate(
            {
                "identity_core": {
                    "character_id": "char_a",
                    "canonical_name": "A",
                    "aliases": ["A"],
                    "occupation_role": "observer",
                },
                "origin_seed": {},
                "life_memory_backbone": {},
                "conversation_personality_layer": {
                    "social_openness": 0.5,
                    "privacy_sensitivity": 0.5,
                    "talk_initiative": 0.5,
                    "deception_control": 0.5,
                    "trust_threshold_for_private_talk": 0.5,
                },
                "virtue_value_layer": {
                    "value_priorities": ["care", "order"],
                    "red_lines": ["humiliate the vulnerable"],
                    "forbidden_behaviors": ["fabricate authority"],
                },
                "capability_constraint_layer": {
                    "skills": ["listening"],
                    "knowledge_domains": ["room etiquette"],
                    "physical_constraints": ["cannot sprint for long"],
                    "psychological_constraints": ["avoids public confrontation"],
                    "social_constraints": ["cannot overrule sealed protocol alone"],
                },
                "style_expression_bias_layer": {
                    "speech_style": "measured",
                    "silence_pattern": "waits before private topics",
                    "gesture_bias": "contained hand movements",
                    "posture_bias": "upright and reserved",
                },
            }
        )

    assert "trait_vector_layer" in str(exc_info.value)


def test_character_profile_accepts_minimal_stage2_payload() -> None:
    profile = CharacterProfile.model_validate(_make_minimal_stage2_payload())

    assert profile.identity_core.character_id == "char_test"
    assert profile.trait_vector_layer.empathy == 0.7
    assert profile.capability_constraint_layer.social_constraints == ["cannot break rank casually"]
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
