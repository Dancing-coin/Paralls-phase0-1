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
from app.gameplay.resource_template_admission import ResourceTemplateAdmission, ResourceTemplateAdmissionError


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
    assert profile.personality_layer is not None
    assert profile.personality_layer.big_five.agreeableness == 0.78


def test_character_profile_registry_lists_sorted_actor_ids_and_gets_profile() -> None:
    registry = CharacterProfileRegistry.from_directory(PROFILE_DIR)

    assert registry.actor_ids() == ["char_a", "char_b", "char_c"]
    assert registry.get("char_b").identity_core.occupation_role == "security steward"


def test_character_profile_registry_accepts_string_directory_path() -> None:
    registry = CharacterProfileRegistry.from_directory(str(PROFILE_DIR))

    assert registry.actor_ids() == ["char_a", "char_b", "char_c"]


def test_character_profile_registry_exposes_versioned_resource_source() -> None:
    registry = CharacterProfileRegistry.from_directory(PROFILE_DIR)

    source = registry.resource_template_source(
        "character:char_a", world_ref="world:main", timeline_ref="timeline:main"
    )

    assert source.template_ref == "character-template:char_a"
    assert source.template_revision == "character-template:char_a@1"
    assert source.relation_kind == "independent"
    assert source.relation_policy_ref == "resource-relation:independent@1"
    assert source.actor_scope == ("char_a",)
    assert source.world_scope == ("world:main", "world:bakery", "world:bakery-district")
    assert source.timeline_scope == ("timeline:main", "population:world:bakery", "population:world:bakery-district", "timeline:world")
    assert source.read_principals == ("resource-template-consumer",)
    assert {entry.resource_id for entry in source.resources} == {
        "core.stamina", "core.mana", "core.action_points"
    }
    stamina = next(entry for entry in source.resources if entry.resource_id == "core.stamina")
    assert (stamina.maximum, stamina.initial, stamina.recovery_amount) == (100, 100, 5)


def test_resource_source_rejects_scope_not_published_by_template() -> None:
    registry = CharacterProfileRegistry.from_directory(PROFILE_DIR)
    with pytest.raises(ValueError, match="resource_template_scope_not_published"):
        registry.resource_template_source("char_a", world_ref="world:forged", timeline_ref="timeline:main")
    with pytest.raises(ValueError, match="resource_template_scope_not_published"):
        registry.resource_template_source("char_a", world_ref="world:main", timeline_ref="timeline:forged")


def test_character_profile_resource_source_freezes_and_rejects_changed_binding() -> None:
    registry = CharacterProfileRegistry.from_directory(PROFILE_DIR)
    source = registry.resource_template_source(
        "char_b", world_ref="world:main", timeline_ref="timeline:main"
    )
    frozen = ResourceTemplateAdmission().admit(
        source,
        actor_ref="char_b",
        world_ref="world:main",
        timeline_ref="timeline:main",
        now_world_tick=5,
        caller_principal="resource-template-consumer",
        binding_revision="binding:character-profile@1",
    )
    with pytest.raises(ResourceTemplateAdmissionError, match="source_changed"):
        ResourceTemplateAdmission().revalidate(
            frozen,
            source.model_copy(update={"template_revision": "character-template:char_b@2"}),
            now_world_tick=5,
            binding_revision="binding:character-profile@1",
        )


def test_character_profile_without_resource_template_fails_closed(tmp_path: Path) -> None:
    payload = _read_profile_payload("char_a")
    payload.pop("resource_template", None)
    with (tmp_path / "char_a.yaml").open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)
    registry = CharacterProfileRegistry.from_directory(tmp_path)
    with pytest.raises(KeyError, match="resource_template:char_a"):
        registry.resource_template_source("char_a", world_ref="world:main", timeline_ref="timeline:main")


def test_legacy_three_resource_profile_decodes_as_independent_without_mutating_file(tmp_path: Path) -> None:
    payload = _read_profile_payload("char_a")
    template = payload["resource_template"]
    template.pop("relation_kind")
    template.pop("relation_policy_ref")
    path = tmp_path / "char_a.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    legacy_bytes = path.read_bytes()
    registry = CharacterProfileRegistry.from_directory(tmp_path)
    source = registry.resource_template_source("char_a", world_ref="world:main", timeline_ref="timeline:main")
    assert source.relation_kind == "independent"
    assert source.relation_policy_ref == "resource-relation:independent@1"
    assert path.read_bytes() == legacy_bytes
    assert source.template_revision == template["template_revision"]


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
