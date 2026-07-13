from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.character_agent.skills.models import CharacterSkillState, LearnedSkillLayer, SkillDefinition
from app.character_agent.skills.registry import CharacterSkillRegistry
from app.character_agent.skills.service import CharacterSkillService


def _registry() -> CharacterSkillRegistry:
    return CharacterSkillRegistry(
        skills=[
            SkillDefinition(skill_id="first_aid", display_name="First Aid", domains=["medical"]),
            SkillDefinition(skill_id="triage", display_name="Triage", domains=["medical"]),
        ]
    )


def test_effective_skill_states_keep_authored_and_learned_rows_separate() -> None:
    service = CharacterSkillService(registry=_registry())
    profile = {
        "capability_constraint_layer": {
            "skills": ["first_aid"],
            "knowledge_domains": ["medical"],
        }
    }
    profile_before = deepcopy(profile)

    learned_overlay = LearnedSkillLayer(
        enabled=True,
        skill_states=[
            CharacterSkillState(
                actor_id="char_a",
                skill_id="first_aid",
                source="learned",
                rank="trained",
                proficiency=0.82,
                confidence=0.73,
                visibility={"player_visible": False},
            )
        ],
    )

    states = service.effective_skill_states(
        actor_id="char_a",
        profile=profile,
        learned_overlay=learned_overlay,
    )

    assert [(state.skill_id, state.source, state.rank) for state in states] == [
        ("first_aid", "authored", "basic"),
        ("first_aid", "learned", "trained"),
    ]
    assert states[0].visibility["conflict"] == {
        "skill_id": "first_aid",
        "sources": ["authored", "learned"],
        "current_source": "authored",
        "ranks_by_source": {"authored": "basic", "learned": "trained"},
    }
    assert states[1].visibility["conflict"] == {
        "skill_id": "first_aid",
        "sources": ["authored", "learned"],
        "current_source": "learned",
        "ranks_by_source": {"authored": "basic", "learned": "trained"},
    }
    assert profile == profile_before


def test_effective_skill_states_can_disable_learned_overlay() -> None:
    service = CharacterSkillService(registry=_registry())

    states = service.effective_skill_states(
        actor_id="char_a",
        profile={"capability_constraint_layer": {"skills": ["first_aid"]}},
        learned_overlay=LearnedSkillLayer(
            enabled=False,
            skill_states=[
                CharacterSkillState(
                    actor_id="char_a",
                    skill_id="first_aid",
                    source="learned",
                    rank="expert",
                    proficiency=0.9,
                    confidence=0.9,
                )
            ],
        ),
    )

    assert [(state.skill_id, state.source, state.rank) for state in states] == [
        ("first_aid", "authored", "basic")
    ]
    assert "conflict" not in states[0].visibility


def test_learned_overlay_rejects_non_learned_skill_rows() -> None:
    with pytest.raises(ValidationError, match="learned overlay skill_states must use source='learned'"):
        LearnedSkillLayer(
            enabled=True,
            skill_states=[
                CharacterSkillState(
                    actor_id="char_a",
                    skill_id="first_aid",
                    source="equipment",
                    rank="expert",
                    proficiency=0.95,
                    confidence=0.9,
                )
            ],
        )


def test_effective_skill_states_preserve_runtime_sources_without_merging_into_learned() -> None:
    service = CharacterSkillService(registry=_registry())

    states = service.effective_skill_states(
        actor_id="char_a",
        profile={"capability_constraint_layer": {"skills": ["first_aid"]}},
        learned_overlay=LearnedSkillLayer(
            enabled=True,
            skill_states=[
                CharacterSkillState(
                    actor_id="char_a",
                    skill_id="first_aid",
                    source="learned",
                    rank="trained",
                    proficiency=0.8,
                    confidence=0.7,
                )
            ],
        ),
        runtime_states=[
            CharacterSkillState(
                actor_id="char_a",
                skill_id="first_aid",
                source="scripted",
                rank="blocked",
                proficiency=0.0,
                confidence=0.0,
            ),
            CharacterSkillState(
                actor_id="char_b",
                skill_id="first_aid",
                source="temporary",
                rank="expert",
                proficiency=1.0,
                confidence=1.0,
            ),
            CharacterSkillState(
                actor_id="char_a",
                skill_id="first_aid",
                source="equipment",
                rank="expert",
                proficiency=0.95,
                confidence=0.9,
            ),
        ],
    )

    assert [(state.source, state.rank) for state in states] == [
        ("authored", "basic"),
        ("learned", "trained"),
        ("equipment", "expert"),
        ("scripted", "blocked"),
    ]
    assert all(state.actor_id == "char_a" for state in states)
    assert [state.source for state in states[1:]] == ["learned", "equipment", "scripted"]
    assert states[1].source == "learned"
