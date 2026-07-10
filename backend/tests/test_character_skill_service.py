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


def _registry_with_second_medical_skill() -> CharacterSkillRegistry:
    return CharacterSkillRegistry(
        skills=[
            SkillDefinition(skill_id="first_aid", display_name="First Aid", domains=["medical"]),
            SkillDefinition(skill_id="triage", display_name="Triage", domains=["medical"]),
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
            ),
            ActionDefinition(
                action_id="assess_injury_severity",
                kind="composite",
                settlement_categories=["cognitive", "social"],
                primitive_sequence_templates={
                    "triage_to_assess": ["observe_injuries", "check_responsiveness"],
                },
            ),
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
                binding_id="triage_to_assess",
                skill_id="triage",
                action_id="assess_injury_severity",
                skill_path_tags=["medical", "assessment"],
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


def test_service_ignores_other_actor_skill_states_when_summarizing_and_evaluating() -> None:
    service = CharacterSkillService(registry=_registry())
    mixed_states = [
        *service.initial_skill_states(
            actor_id="char_a",
            profile={"capability_constraint_layer": {"skills": ["first_aid"]}},
        ),
        *service.initial_skill_states(
            actor_id="char_b",
            profile={"capability_constraint_layer": {"skills": ["healing_magic"]}},
        ),
    ]

    summary = service.build_affordance_summary(
        actor_id="char_a",
        skill_states=mixed_states,
    )
    result = service.evaluate_action(
        actor_id="char_a",
        action_id="stabilize_injured_actor",
        skill_states=mixed_states,
        preferred_strategy_tags=["special"],
    )

    assert "special" in summary.blocked_action_families
    assert "special" not in summary.available_action_families
    assert result.selected_path["binding_id"] == "first_aid_to_stabilize"
    assert result.blocked_paths[0]["binding_id"] == "healing_magic_to_stabilize"


def test_service_merges_examples_for_shared_affordance_domain() -> None:
    service = CharacterSkillService(registry=_registry_with_second_medical_skill())
    states = service.initial_skill_states(
        actor_id="char_a",
        profile={"capability_constraint_layer": {"skills": ["first_aid", "triage"]}},
    )

    summary = service.build_affordance_summary(
        actor_id="char_a",
        skill_states=states,
    )

    assert summary.available_action_families["medical"]["level"] == "basic"
    assert sorted(summary.available_action_families["medical"]["examples"]) == [
        "assess_injury_severity",
        "stabilize_injured_actor",
    ]


def test_service_expands_primitive_plan_for_selected_skill_path() -> None:
    service = CharacterSkillService(registry=_registry())

    plan = service.expand_primitive_plan(
        action_id="stabilize_injured_actor",
        skill_path_id="first_aid_to_stabilize",
    )

    assert plan.composite_action_id == "stabilize_injured_actor"
    assert plan.primitive_actions == ["approach_target", "kneel_near_target", "apply_pressure"]
