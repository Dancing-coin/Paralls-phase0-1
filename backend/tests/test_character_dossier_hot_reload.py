from __future__ import annotations

from app.character_agent.profile import CharacterDossier, replace_dossier_layer
from test_character_dossier_models import _minimal_dossier_payload


def _dossier() -> CharacterDossier:
    return CharacterDossier.model_validate(_minimal_dossier_payload())


def test_replacing_embodiment_profile_returns_projection_invalidations() -> None:
    result = replace_dossier_layer(
        _dossier(),
        layer_id="embodiment_profile",
        layer_payload={
            "body_schema": {
                "body_type": "slight",
                "height_band": "average",
                "dominant_hand": "right",
            },
            "motor_baseline": {
                "sprint_capacity": "medium",
                "fine_motor_control": "high",
                "load_bearing": "low",
            },
        },
    )

    assert result.layer_id == "embodiment_profile"
    assert result.previous_layer_version == 1
    assert result.next_layer_version == 2
    assert result.invalidates == [
        "embodiment_projection",
        "physical_feasibility_projection",
        "skill_affordance_projection",
    ]
    assert result.dossier.embodiment_profile.motor_baseline.sprint_capacity == "medium"


def test_replacing_identity_profile_invalidates_identity_and_effective_profile() -> None:
    result = replace_dossier_layer(
        _dossier(),
        layer_id="identity_profile",
        layer_payload={
            "actor_id": "char_test",
            "canonical_name": "Renamed Test Character",
            "role_identities": {"occupational_role": "archive_attendant"},
        },
    )

    assert result.invalidates == [
        "identity_projection",
        "effective_profile_projection",
    ]
    assert result.dossier.identity_profile.canonical_name == "Renamed Test Character"


def test_hot_reload_result_declares_runtime_stores_it_does_not_mutate() -> None:
    result = replace_dossier_layer(
        _dossier(),
        layer_id="identity_profile",
        layer_payload={"actor_id": "char_test", "canonical_name": "A"},
    )

    assert result.does_not_mutate == [
        "need_tension_state",
        "dynamic_state",
        "body_runtime_state",
        "current_goal_state",
        "memory_store",
        "relationship_graph",
        "character_skill_state",
    ]


def test_replace_dossier_layer_returns_new_dossier_without_mutating_original() -> None:
    dossier = _dossier()
    before = dossier.model_dump()

    result = replace_dossier_layer(
        dossier,
        layer_id="identity_profile",
        layer_payload={"actor_id": "char_test", "canonical_name": "A"},
    )

    assert result.dossier is not dossier
    assert dossier.model_dump() == before
    assert result.dossier.identity_profile.canonical_name == "A"
