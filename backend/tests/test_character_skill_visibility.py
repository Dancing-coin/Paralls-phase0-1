import pytest
from pydantic import ValidationError

from app.character_agent.skills.models import CharacterSkillState, SkillDefinition
from app.character_agent.skills.visibility import (
    ObservedSkillBelief,
    ObservedSkillBeliefStore,
    PlayerFacingCapabilityHint,
    build_player_facing_capability_hints,
)


def _skill_state(
    *,
    actor_id: str = "char_a",
    skill_id: str,
    confidence: float = 0.5,
    visibility: dict[str, object] | None = None,
) -> CharacterSkillState:
    return CharacterSkillState(
        actor_id=actor_id,
        skill_id=skill_id,
        source="authored",
        rank="trained",
        proficiency=0.65,
        confidence=confidence,
        visibility=visibility or {},
    )


def _skill_definition(
    *,
    skill_id: str,
    display_name: str,
    learnability: str = "trained",
    visibility_default: dict[str, object] | None = None,
) -> SkillDefinition:
    return SkillDefinition(
        skill_id=skill_id,
        display_name=display_name,
        domains=["general"],
        learnability=learnability,
        visibility_default=visibility_default or {},
    )


def test_observed_skill_belief_requires_evidence_refs_for_nonzero_confidence() -> None:
    with pytest.raises(ValidationError):
        ObservedSkillBelief(
            observer_actor_id="char_b",
            subject_actor_id="char_a",
            skill_id="deception",
            belief_state="suspected",
            confidence=0.42,
            evidence_refs=[],
        )

    belief = ObservedSkillBelief(
        observer_actor_id="char_b",
        subject_actor_id="char_a",
        skill_id="deception",
        belief_state="suspected",
        confidence=0.42,
        evidence_refs=["saw_inconsistent_story"],
    )

    assert belief.confidence == 0.42


def test_observed_skill_belief_store_upserts_separately_from_actual_skill_state() -> None:
    actual_state = _skill_state(
        skill_id="deception",
        visibility={"player_visible": False},
    )
    store = ObservedSkillBeliefStore()
    initial = ObservedSkillBelief(
        observer_actor_id="char_b",
        subject_actor_id="char_a",
        skill_id="deception",
        belief_state="unknown",
        confidence=0.0,
        evidence_refs=[],
    )
    updated = ObservedSkillBelief(
        observer_actor_id="char_b",
        subject_actor_id="char_a",
        skill_id="deception",
        belief_state="suspected",
        confidence=0.51,
        evidence_refs=["heard_contradiction"],
    )

    store.upsert(initial)
    store.upsert(updated)

    matches = store.query(observer_actor_id="char_b", subject_actor_id="char_a", skill_id="deception")
    assert len(matches) == 1
    assert matches[0].belief_state == "suspected"
    assert matches[0].evidence_refs == ["heard_contradiction"]

    matches[0].evidence_refs.append("mutated_after_query")
    reread = store.query(observer_actor_id="char_b", subject_actor_id="char_a", skill_id="deception")
    assert reread[0].evidence_refs == ["heard_contradiction"]

    assert actual_state.skill_id == "deception"
    assert actual_state.visibility == {"player_visible": False}
    assert actual_state.evidence_refs == []


def test_player_facing_hints_hide_private_skills_from_state_visibility() -> None:
    hints = build_player_facing_capability_hints(
        subject_actor_id="char_a",
        skill_states=[
            _skill_state(skill_id="first_aid", visibility={"player_visible": True}),
            _skill_state(
                skill_id="deception",
                visibility={"player_visible": False, "visibility_state": "private"},
            ),
        ],
        skill_definitions=[
            _skill_definition(skill_id="first_aid", display_name="First Aid"),
            _skill_definition(skill_id="deception", display_name="Deception"),
        ],
    )

    assert hints == [
        PlayerFacingCapabilityHint(
            subject_actor_id="char_a",
            skill_id="first_aid",
            display_name="First Aid",
            confidence=0.5,
            visibility_state="visible",
        )
    ]


def test_player_facing_hints_hide_private_visibility_state_without_player_visible_override() -> None:
    hints = build_player_facing_capability_hints(
        subject_actor_id="char_a",
        skill_states=[
            _skill_state(
                skill_id="deception",
                visibility={"visibility_state": "private"},
            ),
        ],
        skill_definitions=[
            _skill_definition(skill_id="deception", display_name="Deception"),
        ],
    )

    assert hints == []


def test_player_facing_hints_hide_private_definition_visibility_without_player_visible_override() -> None:
    hints = build_player_facing_capability_hints(
        subject_actor_id="char_a",
        skill_states=[
            _skill_state(skill_id="deception"),
        ],
        skill_definitions=[
            _skill_definition(
                skill_id="deception",
                display_name="Deception",
                visibility_default={"visibility_state": "private"},
            ),
        ],
    )

    assert hints == []


def test_player_facing_hints_respect_definition_defaults_for_locked_or_hidden_skills() -> None:
    hints = build_player_facing_capability_hints(
        subject_actor_id="char_a",
        skill_states=[
            _skill_state(skill_id="streetwise"),
            _skill_state(skill_id="forbidden_ritual"),
            _skill_state(skill_id="silent_reading"),
        ],
        skill_definitions=[
            _skill_definition(skill_id="streetwise", display_name="Streetwise"),
            _skill_definition(
                skill_id="forbidden_ritual",
                display_name="Forbidden Ritual",
                learnability="locked",
            ),
            _skill_definition(
                skill_id="silent_reading",
                display_name="Silent Reading",
                visibility_default={"player_visible": False},
            ),
        ],
    )

    assert [hint.skill_id for hint in hints] == ["streetwise"]
    assert hints[0].display_name == "Streetwise"
