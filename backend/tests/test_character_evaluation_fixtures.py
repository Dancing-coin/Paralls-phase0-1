from pathlib import Path

import yaml

from app.character_agent.profile import CharacterDossierLoader, CharacterProfileRegistry


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "character_evaluation"
FORMAL_PROFILE_ROOT = Path(__file__).resolve().parents[1].parent / "assets" / "characters" / "profiles"
FORMAL_DOSSIER_ROOT = Path(__file__).resolve().parents[1].parent / "assets" / "characters" / "dossiers"


def test_char_d_authored_fixture_is_explicitly_isolated_from_formal_discovery():
    profile = yaml.safe_load((FIXTURE_ROOT / "char_d_authored" / "profile.yaml").read_text(encoding="utf-8"))
    dossier = yaml.safe_load((FIXTURE_ROOT / "char_d_authored" / "dossier.yaml").read_text(encoding="utf-8"))

    assert profile["actor_id"] == "char_d"
    assert dossier["actor_id"] == "char_d"
    assert profile["schema_mapping"]["runtime_admission"] is False
    assert dossier["admission"] == {"default_roster": False, "godot_actor": False, "active_control": False}
    assert "char_d" not in CharacterProfileRegistry.from_directory(FORMAL_PROFILE_ROOT).actor_ids()
    try:
        CharacterDossierLoader(FORMAL_DOSSIER_ROOT).load("char_d")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("char_d must not be present in formal dossier discovery")


def test_four_role_fixture_has_pins_and_no_final_quality_claim():
    manifest = yaml.safe_load((FIXTURE_ROOT / "four_role_lock_event" / "manifest.yaml").read_text(encoding="utf-8"))
    actions = yaml.safe_load((FIXTURE_ROOT / "four_role_lock_event" / "acceptable_actions.yaml").read_text(encoding="utf-8"))

    assert manifest["actors"] == ["char_a", "char_b", "char_c", "char_d"]
    assert manifest["isolation"]["active_control"] is False
    assert manifest["policy_revision"] == "policy:unfrozen"
    assert actions["status"] == "pending_source_review"
    assert all(action["target_refs"] for action in actions["actions"])
