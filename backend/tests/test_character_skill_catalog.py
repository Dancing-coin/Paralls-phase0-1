from app.character_agent.skills.catalog import create_core_skill_registry, create_runtime_skill_registry
from app.character_agent.skills.models import SkillActionBinding, SkillDefinition
from app.character_agent.skills.registry import CharacterSkillRegistry
from app.character_agent.skills.service import CharacterSkillService


def test_core_catalog_provides_observation_social_and_procedure_bindings() -> None:
    registry = create_core_skill_registry()

    skill_ids = {skill.skill_id for skill in registry.skills()}
    action_ids = {action.action_id for action in registry.actions()}
    binding_ids = {binding.binding_id for binding in registry.bindings()}

    assert {
        "observation",
        "mediation",
        "procedural recall",
        "threat assessment",
        "command presence",
        "perimeter discipline",
    } <= skill_ids
    assert {
        "survey_scene",
        "defuse_social_tension",
        "follow_room_protocol",
        "assess_visible_threat",
        "enforce_access_boundary",
        "secure_perimeter",
    } <= action_ids
    assert {
        "observation_to_survey_scene",
        "mediation_to_defuse_social_tension",
        "procedural_recall_to_follow_room_protocol",
        "threat_assessment_to_assess_visible_threat",
        "command_presence_to_enforce_access_boundary",
        "perimeter_discipline_to_secure_perimeter",
    } <= binding_ids


def test_unknown_authored_profile_skills_do_not_crash_projection_or_evaluation() -> None:
    service = CharacterSkillService(registry=create_core_skill_registry())

    states = service.initial_skill_states(
        actor_id="char_a",
        profile={
            "capability_constraint_layer": {
                "skills": ["observation", "unknown_profile_skill"],
            }
        },
    )
    result = service.evaluate_action(
        actor_id="char_a",
        action_id="survey_scene",
        skill_states=states,
    )

    assert [state.skill_id for state in states] == ["observation"]
    assert result.selected_path["binding_id"] == "observation_to_survey_scene"
    assert result.blocked_paths == []


def test_char_b_authored_skills_project_into_shadow_affordance_families() -> None:
    service = CharacterSkillService(registry=create_core_skill_registry())

    states = service.initial_skill_states(
        actor_id="char_b",
        profile={
            "capability_constraint_layer": {
                "skills": [
                    "threat assessment",
                    "command presence",
                    "perimeter discipline",
                ],
            }
        },
    )
    summary = service.build_affordance_summary(actor_id="char_b", skill_states=states)

    assert {state.skill_id for state in states} == {
        "threat assessment",
        "command presence",
        "perimeter discipline",
    }
    assert "safety_assessment" in summary.available_action_families
    assert "boundary_enforcement" in summary.available_action_families
    assert "access_control" in summary.available_action_families


def test_runtime_catalog_accepts_injected_overlays_and_replaces_duplicates_deterministically() -> None:
    overlay = CharacterSkillRegistry(
        skills=[
            SkillDefinition(
                skill_id="mediation",
                display_name="Crisis Mediation",
                domains=["social"],
                role_tags=["overlay"],
            )
        ],
        bindings=[
            SkillActionBinding(
                binding_id="mediation_to_defuse_social_tension",
                skill_id="mediation",
                action_id="defuse_social_tension",
                skill_path_tags=["social", "overlay"],
                eligibility={"required_rank": "trained"},
            )
        ],
    )

    registry = create_runtime_skill_registry(overlay)
    binding = next(
        binding
        for binding in registry.bindings_for_action("defuse_social_tension")
        if binding.binding_id == "mediation_to_defuse_social_tension"
    )

    assert registry.skill("mediation").display_name == "Crisis Mediation"
    assert registry.skill("mediation").role_tags == ["overlay"]
    assert binding.skill_path_tags == ["social", "overlay"]
    assert binding.eligibility["required_rank"] == "trained"
