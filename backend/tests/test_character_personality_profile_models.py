from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.character_agent.profile.models import CharacterProfile
from backend.tests.test_character_profile_models import _make_minimal_stage2_payload


def _personality_layer_payload() -> dict[str, object]:
    return {
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
    }


def test_existing_flat_trait_vector_profile_still_loads_without_personality_layer() -> None:
    profile = CharacterProfile.model_validate(_make_minimal_stage2_payload())

    assert profile.trait_vector_layer is not None
    assert profile.trait_vector_layer.empathy == 0.7
    assert profile.personality_layer is None


def test_profile_with_big_five_and_facets_loads_beside_legacy_traits() -> None:
    payload = _make_minimal_stage2_payload()
    payload["personality_layer"] = _personality_layer_payload()

    profile = CharacterProfile.model_validate(payload)

    assert profile.personality_layer is not None
    assert profile.personality_layer.big_five.agreeableness == 0.78
    assert profile.personality_layer.facets.conscientiousness.deliberation == 0.79
    assert profile.trait_vector_layer is not None


def test_new_personality_layer_profile_does_not_require_legacy_trait_vector() -> None:
    payload = _make_minimal_stage2_payload()
    payload["personality_layer"] = _personality_layer_payload()
    del payload["trait_vector_layer"]

    profile = CharacterProfile.model_validate(payload)

    assert profile.trait_vector_layer is None
    assert profile.personality_layer is not None
    assert profile.personality_layer.facets.agreeableness.compassion == 0.84


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("big_five", "openness"), 1.1),
        (("facets", "neuroticism", "volatility"), -0.1),
    ],
)
def test_personality_layer_rejects_out_of_range_scalars(
    path: tuple[str, ...], value: float
) -> None:
    payload = _make_minimal_stage2_payload()
    personality_layer = _personality_layer_payload()
    cursor: dict[str, object] = personality_layer
    for key in path[:-1]:
        cursor = cursor[key]  # type: ignore[assignment,index]
    cursor[path[-1]] = value
    payload["personality_layer"] = personality_layer

    with pytest.raises(ValidationError) as exc_info:
        CharacterProfile.model_validate(payload)

    message = str(exc_info.value)
    assert "personality_layer" in message
    assert path[-1] in message


def test_character_profile_dump_exposes_stable_personality_layer_shape() -> None:
    payload = _make_minimal_stage2_payload()
    payload["personality_layer"] = _personality_layer_payload()

    dumped = CharacterProfile.model_validate(payload).model_dump()

    assert dumped["personality_layer"] == _personality_layer_payload()
    assert set(dumped["personality_layer"]["big_five"]) == {
        "openness",
        "conscientiousness",
        "extraversion",
        "agreeableness",
        "neuroticism",
    }


def test_profile_payload_is_not_mutated_when_personality_layer_validates() -> None:
    payload = _make_minimal_stage2_payload()
    payload["personality_layer"] = _personality_layer_payload()
    before = deepcopy(payload)

    CharacterProfile.model_validate(payload)

    assert payload == before
