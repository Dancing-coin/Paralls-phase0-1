from app.character_agent.skills.models import CharacterSkillState, ObservedSkillBelief, SkillDefinition
from app.character_agent.skills.registry import CharacterSkillRegistry
from app.character_agent.skills.visibility import ObservedSkillBeliefStore, SkillVisibilityProjector


def _projector() -> SkillVisibilityProjector:
    return SkillVisibilityProjector(
        registry=CharacterSkillRegistry(
            skills=[
                SkillDefinition(
                    skill_id="first_aid",
                    display_name="First Aid",
                    domains=["medical"],
                ),
                SkillDefinition(
                    skill_id="deception",
                    display_name="Deception",
                    domains=["social"],
                ),
                SkillDefinition(
                    skill_id="command_presence",
                    display_name="Command Presence",
                    domains=["authority"],
                ),
            ]
        )
    )


def test_observed_skill_belief_store_keeps_beliefs_separate_from_actual_state_and_returns_copies() -> None:
    store = ObservedSkillBeliefStore()
    recorded = store.record(
        ObservedSkillBelief(
            observer_actor_id="char_b",
            subject_actor_id="char_a",
            skill_id="deception",
            belief_state="suspected",
            confidence=0.42,
            evidence_refs=["saw_inconsistent_story"],
        )
    )

    recorded.evidence_refs.append("mutated")
    beliefs = store.query(observer_actor_id="char_b", subject_actor_id="char_a")

    assert len(beliefs) == 1
    assert beliefs[0].subject_actor_id == "char_a"
    assert beliefs[0].skill_id == "deception"
    assert beliefs[0].evidence_refs == ["saw_inconsistent_story"]


def test_player_facing_hints_hide_private_and_locked_skills() -> None:
    hints = _projector().player_hints(
        actor_id="char_a",
        viewer_id="player",
        skill_states=[
            CharacterSkillState(
                actor_id="char_a",
                skill_id="first_aid",
                source="authored",
                rank="trained",
                confidence=0.7,
                visibility={"player_visible": True},
            ),
            CharacterSkillState(
                actor_id="char_a",
                skill_id="deception",
                source="learned",
                rank="trained",
                confidence=0.8,
                visibility={"tags": ["private"]},
            ),
            CharacterSkillState(
                actor_id="char_a",
                skill_id="command_presence",
                source="authority",
                rank="blocked",
                confidence=0.3,
                visibility={"player_visible": True},
            ),
        ],
    )

    assert [(hint.skill_id, hint.display_name) for hint in hints] == [("first_aid", "First Aid")]
    assert hints[0].hint_level == "trained"
    assert hints[0].domains == ["medical"]


def test_player_facing_hints_respect_explicit_player_allowlist() -> None:
    states = [
        CharacterSkillState(
            actor_id="char_a",
            skill_id="first_aid",
            source="authored",
            rank="basic",
            confidence=0.5,
            visibility={"visible_to_players": ["player_debug"]},
        )
    ]

    projector = _projector()

    assert projector.player_hints(actor_id="char_a", viewer_id="player", skill_states=states) == []
    assert [hint.skill_id for hint in projector.player_hints(actor_id="char_a", viewer_id="player_debug", skill_states=states)] == [
        "first_aid"
    ]
