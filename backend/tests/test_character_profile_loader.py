from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.character_agent.profile import (
    CharacterProfileLoader,
    CharacterProfileRegistry,
    ProfileCapabilitiesView,
    ProfileConversationBiasView,
    ProfileIdentityView,
    ProfileValuesView,
)


PROFILE_DIR = Path(__file__).resolve().parents[1].parent / "assets" / "characters" / "profiles"


def _read_profile_payload(actor_id: str) -> dict[str, object]:
    with (PROFILE_DIR / f"{actor_id}.yaml").open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_character_profile_loader_reads_yaml_profile() -> None:
    loader = CharacterProfileLoader(PROFILE_DIR)

    profile = loader.load("char_a")

    assert profile.identity_core.character_id == "char_a"
    assert profile.identity_core.canonical_name == "Lin Yue"
    assert profile.trait_vector_layer.empathy == 0.82


def test_character_profile_registry_lists_sorted_actor_ids_and_gets_profile() -> None:
    registry = CharacterProfileRegistry.from_directory(PROFILE_DIR)

    assert registry.actor_ids() == ["char_a", "char_b", "char_c"]
    assert registry.get("char_b").identity_core.occupation_role == "security steward"


def test_character_profile_registry_accepts_string_directory_path() -> None:
    registry = CharacterProfileRegistry.from_directory(str(PROFILE_DIR))

    assert registry.actor_ids() == ["char_a", "char_b", "char_c"]


def test_character_profile_loader_rejects_mismatched_actor_id(tmp_path: Path) -> None:
    payload = _read_profile_payload("char_a")
    payload["identity_core"]["character_id"] = "char_b"  # type: ignore[index]

    with (tmp_path / "char_a.yaml").open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)

    loader = CharacterProfileLoader(tmp_path)

    with pytest.raises(ValueError) as exc_info:
        loader.load("char_a")

    message = str(exc_info.value)
    assert "Profile actor_id mismatch" in message
    assert "char_a" in message
    assert "char_b" in message


def test_profile_identity_view_projects_key_fields_as_read_only_data() -> None:
    profile = CharacterProfileLoader(PROFILE_DIR).load("char_a")

    view = ProfileIdentityView.from_profile(profile)

    assert view.actor_id == "char_a"
    assert view.canonical_name == "Lin Yue"
    assert view.aliases == ("Yue", "Archivist Lin")
    assert view.occupation_role == "archive attendant"


def test_profile_values_capabilities_and_conversation_views_project_expected_fields() -> None:
    profile = CharacterProfileLoader(PROFILE_DIR).load("char_b")

    values_view = ProfileValuesView.from_profile(profile)
    capabilities_view = ProfileCapabilitiesView.from_profile(profile)
    conversation_view = ProfileConversationBiasView.from_profile(profile)

    assert values_view.value_priorities == ("duty", "safety", "clarity")
    assert capabilities_view.skills == ("threat assessment", "command presence", "perimeter discipline")
    assert capabilities_view.social_constraints == (
        "cannot ignore recorded safety violations once witnessed",
    )
    assert conversation_view.social_openness == 0.34
    assert conversation_view.privacy_sensitivity == 0.71
    assert conversation_view.talk_initiative == 0.52
    assert conversation_view.deception_control == 0.91
    assert conversation_view.trust_threshold_for_private_talk == 0.77


def test_character_profile_loader_exposes_runtime_defaults() -> None:
    profile = CharacterProfileLoader(PROFILE_DIR).load("char_c")

    assert profile.runtime_defaults.default_control_mode == "player_priority_assisted"
