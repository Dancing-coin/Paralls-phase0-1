from app.character_agent.skills.models import ActionDefinition, CharacterSkillState, SkillActionBinding, SkillDefinition
from app.character_agent.skills.registry import CharacterSkillRegistry
from app.character_agent.skills.service import CharacterSkillService


def _service() -> CharacterSkillService:
    return CharacterSkillService(
        registry=CharacterSkillRegistry(
            skills=[
                SkillDefinition(skill_id="first_aid", display_name="First Aid", domains=["medical"]),
                SkillDefinition(skill_id="triage", display_name="Triage", domains=["medical"]),
            ],
            actions=[
                ActionDefinition(action_id="stabilize_injured_actor", kind="composite"),
                ActionDefinition(action_id="assess_injury_severity", kind="composite"),
            ],
            bindings=[
                SkillActionBinding(
                    binding_id="first_aid_to_stabilize",
                    skill_id="first_aid",
                    action_id="stabilize_injured_actor",
                ),
                SkillActionBinding(
                    binding_id="triage_to_assess",
                    skill_id="triage",
                    action_id="assess_injury_severity",
                ),
            ],
        )
    )


def test_effective_skill_projection_keeps_authored_and_learned_rows_with_visible_conflict_metadata() -> None:
    service = _service()
    authored = [
        CharacterSkillState(
            actor_id="char_a",
            skill_id="first_aid",
            source="authored",
            rank="basic",
            proficiency=0.4,
            confidence=0.5,
        )
    ]
    learned = [
        CharacterSkillState(
            actor_id="char_a",
            skill_id="first_aid",
            source="learned",
            rank="trained",
            proficiency=0.7,
            confidence=0.8,
        )
    ]

    projection = service.resolve_effective_skill_states(
        actor_id="char_a",
        skill_states=authored,
        learned_skill_states=learned,
    )

    learned[0].rank = "novice"

    assert [state.source for state in projection.states] == ["learned", "authored"]
    assert projection.primary_state_by_skill["first_aid"].source == "learned"
    assert projection.primary_state_by_skill["first_aid"].rank == "trained"
    assert projection.conflicts == [
        {
            "skill_id": "first_aid",
            "selected_source": "learned",
            "selected_rank": "trained",
            "sources": ["learned", "authored"],
            "suppressed_sources": ["authored"],
        }
    ]
    assert projection.overlays_applied == ["learned"]


def test_learned_overlay_can_be_disabled_without_mutating_authored_projection() -> None:
    service = _service()
    authored = [
        CharacterSkillState(
            actor_id="char_a",
            skill_id="first_aid",
            source="authored",
            rank="basic",
            proficiency=0.5,
            confidence=0.5,
        )
    ]
    learned = [
        CharacterSkillState(
            actor_id="char_a",
            skill_id="triage",
            source="learned",
            rank="trained",
            proficiency=0.9,
            confidence=0.8,
        )
    ]

    enabled = service.build_affordance_summary(
        actor_id="char_a",
        skill_states=authored,
        learned_skill_states=learned,
        learned_overlay_enabled=True,
    )
    disabled = service.build_affordance_summary(
        actor_id="char_a",
        skill_states=authored,
        learned_skill_states=learned,
        learned_overlay_enabled=False,
    )

    assert sorted(enabled.available_action_families["medical"]["examples"]) == [
        "assess_injury_severity",
        "stabilize_injured_actor",
    ]
    assert "missing_skills" not in enabled.available_action_families["medical"]
    assert disabled.available_action_families["medical"]["missing_skills"] == ["triage"]
