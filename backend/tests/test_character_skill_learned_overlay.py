from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.character_agent.skills.models import (
    ActionDefinition,
    CharacterSkillState,
    LearnedSkillLayer,
    SkillActionBinding,
    SkillDefinition,
)
from app.character_agent.skills.registry import CharacterSkillRegistry
from app.character_agent.skills.service import CharacterSkillService


def _registry() -> CharacterSkillRegistry:
    return CharacterSkillRegistry(
        skills=[
            SkillDefinition(skill_id="first_aid", display_name="First Aid", domains=["medical"]),
            SkillDefinition(skill_id="triage", display_name="Triage", domains=["medical"]),
        ]
    )


def _action_registry() -> CharacterSkillRegistry:
    return CharacterSkillRegistry(
        skills=[
            SkillDefinition(skill_id="first_aid", display_name="First Aid", domains=["medical"]),
        ],
        actions=[
            ActionDefinition(
                action_id="stabilize_injured_actor",
                kind="composite",
                settlement_categories=["cognitive", "physical", "social", "tool"],
                primitive_sequence_templates={
                    "first_aid_to_stabilize": ["approach_target", "kneel_near_target", "apply_pressure"],
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
            )
        ],
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
        "rows": [
            {
                "source": "authored",
                "rank": "basic",
                "evidence_refs": [],
                "restrictions": [],
            },
            {
                "source": "learned",
                "rank": "trained",
                "evidence_refs": [],
                "restrictions": [],
            },
        ],
    }
    assert states[1].visibility["conflict"] == {
        "skill_id": "first_aid",
        "sources": ["authored", "learned"],
        "current_source": "learned",
        "rows": [
            {
                "source": "authored",
                "rank": "basic",
                "evidence_refs": [],
                "restrictions": [],
            },
            {
                "source": "learned",
                "rank": "trained",
                "evidence_refs": [],
                "restrictions": [],
            },
        ],
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


def test_evaluate_action_prefers_strongest_usable_skill_row_over_later_blocked_row() -> None:
    service = CharacterSkillService(registry=_action_registry())

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
                    confidence=0.75,
                )
            ],
        ),
        runtime_states=[
            CharacterSkillState(
                actor_id="char_a",
                skill_id="first_aid",
                source="equipment",
                rank="expert",
                proficiency=0.95,
                confidence=0.9,
            ),
            CharacterSkillState(
                actor_id="char_a",
                skill_id="first_aid",
                source="scripted",
                rank="blocked",
                proficiency=0.0,
                confidence=0.0,
                restrictions=["injured_hand"],
            ),
        ],
    )

    result = service.evaluate_action(
        actor_id="char_a",
        action_id="stabilize_injured_actor",
        skill_states=states,
    )

    assert result.selected_path["binding_id"] == "first_aid_to_stabilize"
    assert result.selected_path["current_rank"] == "expert"
    assert result.blocked_paths == []


def test_build_affordance_summary_uses_strongest_effective_skill_row() -> None:
    service = CharacterSkillService(registry=_action_registry())

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
                    proficiency=0.82,
                    confidence=0.73,
                )
            ],
        ),
        runtime_states=[
            CharacterSkillState(
                actor_id="char_a",
                skill_id="first_aid",
                source="temporary",
                rank="master",
                proficiency=1.0,
                confidence=0.95,
            ),
            CharacterSkillState(
                actor_id="char_a",
                skill_id="first_aid",
                source="equipment",
                rank="novice",
                proficiency=0.4,
                confidence=0.4,
            ),
        ],
    )

    summary = service.build_affordance_summary(
        actor_id="char_a",
        skill_states=states,
    )

    assert summary.available_action_families["medical"]["level"] == "master"


def test_effective_skill_states_conflict_metadata_preserves_duplicate_same_source_rows() -> None:
    service = CharacterSkillService(registry=_registry())

    states = service.effective_skill_states(
        actor_id="char_a",
        profile={"capability_constraint_layer": {"skills": ["first_aid"]}},
        runtime_states=[
            CharacterSkillState(
                actor_id="char_a",
                skill_id="first_aid",
                source="equipment",
                rank="novice",
                proficiency=0.3,
                confidence=0.4,
                evidence_refs=["brace"],
                restrictions=["wet_hands"],
            ),
            CharacterSkillState(
                actor_id="char_a",
                skill_id="first_aid",
                source="equipment",
                rank="expert",
                proficiency=0.9,
                confidence=0.85,
                evidence_refs=["med_kit"],
                restrictions=["heavy_gloves"],
            ),
        ],
    )

    authored_state = states[0]
    assert authored_state.visibility["conflict"]["rows"] == [
        {
            "source": "authored",
            "rank": "basic",
            "evidence_refs": [],
            "restrictions": [],
        },
        {
            "source": "equipment",
            "rank": "novice",
            "evidence_refs": ["brace"],
            "restrictions": ["wet_hands"],
        },
        {
            "source": "equipment",
            "rank": "expert",
            "evidence_refs": ["med_kit"],
            "restrictions": ["heavy_gloves"],
        },
    ]
