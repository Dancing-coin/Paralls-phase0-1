from __future__ import annotations

import pytest

from app.character_agent.profile import CharacterDossier, build_dossier_projection
from test_character_dossier_models import _minimal_dossier_payload


def _dossier_with_author_only_secret() -> CharacterDossier:
    payload = _minimal_dossier_payload()
    private_truth_profile = payload["private_truth_profile"]
    assert isinstance(private_truth_profile, dict)
    secrets = private_truth_profile["secrets"]
    assert isinstance(secrets, list)
    secrets.append(
        {
            "truth_id": "secret:char_test:author_only",
            "content": "author-only truth that must never reach cognition",
            "known_by": ["author"],
            "unknown_to": ["char_test", "public"],
            "allowed_projection": {
                "l2": "hidden",
                "l3": "hidden",
                "player": "hidden",
            },
        }
    )
    return CharacterDossier.model_validate(payload)


def test_l2_dossier_projection_includes_filtered_context_summaries() -> None:
    dossier = _dossier_with_author_only_secret()

    projection = build_dossier_projection(dossier, audience="l2")

    assert projection["actor_id"] == "char_test"
    assert projection["identity"]["canonical_name"] == "Test Character"
    assert projection["authority"]["forbidden_actions"] == ["grant_sealed_access_alone"]
    assert projection["embodiment"]["motor_baseline"]["sprint_capacity"] == "low"
    assert projection["private_truth"]["self_known_secret_count"] == 1
    assert projection["private_truth"]["visible_truth_ids"] == [
        "secret:char_test:omission_fear"
    ]
    assert "character_profile" not in projection
    assert "author-only truth that must never reach cognition" not in str(projection)
    assert "fears one omission could damage trust" not in str(projection)


def test_l3_projection_receives_private_truth_constraints_without_raw_content() -> None:
    dossier = _dossier_with_author_only_secret()

    projection = build_dossier_projection(dossier, audience="l3")

    assert projection["private_truth"]["constraint_secret_count"] == 1
    assert projection["private_truth"]["constraint_truth_ids"] == [
        "secret:char_test:omission_fear"
    ]
    assert "fears one omission could damage trust" not in str(projection)
    assert "author-only truth that must never reach cognition" not in str(projection)


def test_player_projection_hides_player_hidden_secrets() -> None:
    dossier = _dossier_with_author_only_secret()

    projection = build_dossier_projection(dossier, audience="player")

    assert projection["private_truth"]["visible_secret_count"] == 0
    assert "secret:char_test:omission_fear" not in str(projection)
    assert "fears one omission could damage trust" not in str(projection)


def test_l4_projection_is_action_relevant_only() -> None:
    dossier = _dossier_with_author_only_secret()

    projection = build_dossier_projection(dossier, audience="l4")

    assert set(projection) == {
        "actor_id",
        "identity",
        "embodiment",
        "authority",
        "private_truth",
        "relationship_seeds",
        "capability_seeds",
        "source_refs",
    }
    assert projection["private_truth"] == {"hidden": True}
    assert projection["identity"] == {"actor_id": "char_test"}
    assert projection["authority"]["forbidden_actions"] == ["grant_sealed_access_alone"]
    assert "character_profile" not in projection


def test_dossier_projection_rejects_unknown_audience() -> None:
    dossier = _dossier_with_author_only_secret()

    with pytest.raises(ValueError, match="Unsupported dossier projection audience"):
        build_dossier_projection(dossier, audience="omniscient")  # type: ignore[arg-type]
