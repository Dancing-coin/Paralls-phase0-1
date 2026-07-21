from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.character_agent.profile import CharacterDossierLoader
from test_character_dossier_models import (
    _minimal_character_profile_payload,
    _minimal_dossier_payload,
)


DOSSIER_DIR = Path(__file__).resolve().parents[1].parent / "assets" / "characters" / "dossiers"


def _write_yaml(path: Path, payload: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)


def test_character_dossier_loader_reads_wrapped_dossier_yaml(tmp_path: Path) -> None:
    payload = {"character_dossier": _minimal_dossier_payload()}
    _write_yaml(tmp_path / "char_test.yaml", payload)

    dossier = CharacterDossierLoader(tmp_path).load("char_test")

    assert dossier.actor_id == "char_test"
    assert dossier.character_profile.identity_core.character_id == "char_test"
    assert dossier.identity_profile.canonical_name == "Test Character"
    assert dossier.embodiment_profile.motor_baseline.sprint_capacity == "low"


def test_character_dossier_loader_adapts_legacy_profile_yaml(tmp_path: Path) -> None:
    _write_yaml(tmp_path / "char_test.yaml", _minimal_character_profile_payload())

    dossier = CharacterDossierLoader(tmp_path).load("char_test")

    assert dossier.dossier_id == "dossier:char_test"
    assert dossier.schema_version == "character_dossier.v1"
    assert dossier.identity_profile.actor_id == "char_test"
    assert dossier.identity_profile.canonical_name == "Test Character"
    assert dossier.identity_profile.role_identities.occupational_role == "archive attendant"
    assert dossier.character_profile.identity_core.aliases == ["Tester"]


def test_character_dossier_loader_rejects_requested_actor_mismatch(tmp_path: Path) -> None:
    payload = _minimal_dossier_payload()
    payload["actor_id"] = "other_actor"
    _write_yaml(tmp_path / "char_test.yaml", {"character_dossier": payload})

    with pytest.raises(ValueError, match="Dossier actor_id mismatch"):
        CharacterDossierLoader(tmp_path).load("char_test")


def test_character_dossier_loader_preserves_nested_character_profile(tmp_path: Path) -> None:
    payload = _minimal_dossier_payload()
    _write_yaml(tmp_path / "char_test.yaml", payload)

    dossier = CharacterDossierLoader(tmp_path).load("char_test")

    assert dossier.character_profile.identity_core.canonical_name == "Test Character"
    assert dossier.character_profile.virtue_value_layer.red_lines == [
        "casually expose private records"
    ]


def test_character_dossier_loader_reads_example_char_a_dossier_fixture() -> None:
    dossier = CharacterDossierLoader(DOSSIER_DIR).load("char_a")

    assert dossier.actor_id == "char_a"
    assert dossier.character_profile.identity_core.canonical_name == "Lin Yue"
    assert dossier.identity_profile.role_identities.scene_role == "grounded_social_anchor"
    assert dossier.embodiment_profile.motor_baseline.sprint_capacity == "low"
    assert dossier.relationship_seed_profile.relationships[0].evidence_seeds
    assert dossier.capability_seed_profile.skill_seeds[0].skill_id == "social.mediation"


def test_character_dossier_loader_reads_example_char_b_dossier_fixture() -> None:
    dossier = CharacterDossierLoader(DOSSIER_DIR).load("char_b")

    assert dossier.actor_id == "char_b"
    assert dossier.character_profile.identity_core.character_id == "char_b"
    assert dossier.character_profile.identity_core.canonical_name == "Qiao Ren"
    assert dossier.identity_profile.role_identities.scene_role == "authoritative_boundary_enforcer"
    assert dossier.authority_profile.responsibilities
    assert dossier.capability_seed_profile.skill_seeds


def test_char_c_dossier_is_out_of_scope_player_shell_boundary() -> None:
    # char_c remains a player shell in this slice, so this plan does not require
    # or validate a full authored dossier for it.
    assert not (DOSSIER_DIR / "char_c.yaml").exists()
