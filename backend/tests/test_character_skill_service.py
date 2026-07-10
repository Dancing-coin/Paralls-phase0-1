from app.character_agent.skills.models import ActionDefinition, SkillActionBinding, SkillDefinition
from app.character_agent.skills.registry import CharacterSkillRegistry
from app.character_agent.skills.service import CharacterSkillService


def _registry() -> CharacterSkillRegistry:
    return CharacterSkillRegistry(
        skills=[
            SkillDefinition(skill_id="first_aid", display_name="First Aid", domains=["medical"]),
            SkillDefinition(skill_id="healing_magic", display_name="Healing Magic", domains=["special"]),
        ],
        actions=[
            ActionDefinition(
                action_id="stabilize_injured_actor",
                kind="composite",
                settlement_categories=["cognitive", "physical", "social", "tool"],
                primitive_sequence_templates={
                    "first_aid_to_stabilize": ["approach_target", "kneel_near_target", "apply_pressure"],
                    "healing_magic_to_stabilize": ["raise_hand", "channel_effect"],
                },
            )
        ],
        bindings=[
            SkillActionBinding(
                binding_id="first_aid_to_stabilize",
                skill_id="first_aid",
                action_id="stabilize_injured_actor",
                skill_path_tags=["medical", "nonviolent"],
                eligibility={"required_rank": "basic"},
            ),
            SkillActionBinding(
                binding_id="healing_magic_to_stabilize",
                skill_id="healing_magic",
                action_id="stabilize_injured_actor",
                skill_path_tags=["special"],
                eligibility={"required_rank": "basic"},
            ),
        ],
    )


def test_service_projects_profile_capabilities_to_initial_skill_state() -> None:
    service = CharacterSkillService(registry=_registry())
    states = service.initial_skill_states(
        actor_id="char_a",
        profile={
            "capability_constraint_layer": {
                "skills": ["first_aid"],
                "knowledge_domains": ["medical"],
                "physical_constraints": [],
                "psychological_constraints": [],
                "social_constraints": [],
            }
        },
    )

    assert states[0].actor_id == "char_a"
    assert states[0].skill_id == "first_aid"
    assert states[0].source == "authored"
    assert states[0].rank == "basic"


def test_service_builds_affordance_summary_without_full_registry_payload() -> None:
    service = CharacterSkillService(registry=_registry())

    summary = service.build_affordance_summary(
        actor_id="char_a",
        skill_states=service.initial_skill_states(
            actor_id="char_a",
            profile={"capability_constraint_layer": {"skills": ["first_aid"]}},
        ),
    )

    assert "medical" in summary.available_action_families
    assert summary.available_action_families["medical"]["level"] == "basic"
    assert "stabilize_injured_actor" in summary.available_action_families["medical"]["examples"]
    assert "special" in summary.blocked_action_families


def test_service_evaluates_viable_and_blocked_skill_paths() -> None:
    service = CharacterSkillService(registry=_registry())
    states = service.initial_skill_states(
        actor_id="char_a",
        profile={"capability_constraint_layer": {"skills": ["first_aid"]}},
    )

    result = service.evaluate_action(
        actor_id="char_a",
        action_id="stabilize_injured_actor",
        skill_states=states,
        preferred_strategy_tags=["nonviolent"],
    )

    assert result.selected_path["binding_id"] == "first_aid_to_stabilize"
    assert result.viable_paths[0]["eligibility_status"] == "eligible"
    assert result.blocked_paths[0]["binding_id"] == "healing_magic_to_stabilize"
    assert result.blocked_paths[0]["missing_requirements"] == ["healing_magic.basic"]


def test_service_expands_primitive_plan_for_selected_skill_path() -> None:
    service = CharacterSkillService(registry=_registry())

    plan = service.expand_primitive_plan(
        action_id="stabilize_injured_actor",
        skill_path_id="first_aid_to_stabilize",
    )

    assert plan.composite_action_id == "stabilize_injured_actor"
    assert plan.primitive_actions == ["approach_target", "kneel_near_target", "apply_pressure"]
