from app.character_agent.skills.models import ActionDefinition, SkillActionBinding, SkillDefinition
from app.character_agent.skills.registry import CharacterSkillRegistry


def test_registry_composes_core_and_scenario_definitions() -> None:
    core = CharacterSkillRegistry(
        skills=[
            SkillDefinition(skill_id="first_aid", display_name="First Aid", domains=["medical"]),
        ],
        actions=[
            ActionDefinition(
                action_id="stabilize_injured_actor",
                kind="composite",
                settlement_categories=["cognitive", "physical", "social", "tool"],
            ),
        ],
        bindings=[
            SkillActionBinding(
                binding_id="first_aid_to_stabilize",
                skill_id="first_aid",
                action_id="stabilize_injured_actor",
            )
        ],
    )
    scenario = CharacterSkillRegistry(
        skills=[
            SkillDefinition(skill_id="healing_magic", display_name="Healing Magic", domains=["ritual"]),
        ],
        actions=[],
        bindings=[
            SkillActionBinding(
                binding_id="healing_magic_to_stabilize",
                skill_id="healing_magic",
                action_id="stabilize_injured_actor",
            )
        ],
    )

    composed = CharacterSkillRegistry.compose(core, scenario)

    assert composed.skill("first_aid").display_name == "First Aid"
    assert composed.skill("healing_magic").display_name == "Healing Magic"
    assert len(composed.bindings_for_action("stabilize_injured_actor")) == 2


def test_registry_returns_empty_lists_for_unknown_actions() -> None:
    registry = CharacterSkillRegistry()

    assert registry.bindings_for_action("unknown_action") == []


def test_registry_replaces_duplicate_ids_with_later_layer() -> None:
    core = CharacterSkillRegistry(
        skills=[SkillDefinition(skill_id="persuasion", display_name="Persuasion")],
    )
    scenario = CharacterSkillRegistry(
        skills=[SkillDefinition(skill_id="persuasion", display_name="Court Persuasion")],
    )

    composed = CharacterSkillRegistry.compose(core, scenario)

    assert composed.skill("persuasion").display_name == "Court Persuasion"
