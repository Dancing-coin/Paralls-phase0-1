from app.character_agent.mind.affordances import CharacterMindAffordanceAdapter
from app.character_agent.mind.frame_builder import CharacterMindFrameBuilder
from app.character_agent.mind.view_builder import LayerContextViewBuilder
from app.character_agent.models.mind_frame import CognitionWorkspace


def test_affordance_adapter_summarizes_profile_skills_without_exposing_registry() -> None:
    summary = CharacterMindAffordanceAdapter().build_summary(
        effective_profile={
            "capability_constraint_layer": {
                "skills": ["authority_protocol", "persuasion"],
                "limits": ["cannot_falsify_authority_report"],
            }
        },
        supplied_skill_affordance_summary={
            "available_action_families": {"social_deescalation": {"level": "trained"}},
            "registry": {"internal": "must_not_leak"},
        },
        supplied_action_affordance_summary={"available_actions": ["speak_private"]},
        environment_affordance_summary={"nearby_objects": ["medicine_kit"]},
        equipment_affordance_summary={"held_items": ["lamp"]},
        physical_feasibility_summary={"mobility": "steady"},
    )

    assert summary["skill_affordance"]["profile_skill_ids"] == [
        "authority_protocol",
        "persuasion",
    ]
    assert "registry" not in summary["skill_affordance"]
    assert summary["action_affordance"]["available_actions"] == ["speak_private"]
    assert summary["environment_affordance"]["nearby_objects"] == ["medicine_kit"]
    assert summary["physical_feasibility"]["mobility"] == "steady"


def test_affordance_adapter_emits_empty_profile_capability_lists_when_missing() -> None:
    summary = CharacterMindAffordanceAdapter().build_summary(
        effective_profile={"capability_constraint_layer": {}},
        supplied_skill_affordance_summary={
            "available_action_families": {"authority": {"level": "strong"}}
        },
    )

    assert summary["skill_affordance"]["profile_skill_ids"] == []
    assert summary["skill_affordance"]["profile_limits"] == []


def test_frame_builder_places_all_affordance_cards_in_affordance_layer() -> None:
    frame = CharacterMindFrameBuilder().build_frame(
        actor_id="char_a",
        producer_ts=1,
        effective_profile={
            "capability_constraint_layer": {
                "skills": ["authority_protocol"],
                "limits": ["cannot_falsify_authority_report"],
            }
        },
        skill_affordance_summary={
            "available_action_families": {"authority": {"level": "strong"}}
        },
        action_affordance_summary={"available_actions": ["speak_private"]},
        environment_affordance_summary={"nearby_objects": ["medicine_kit"]},
        equipment_affordance_summary={"held_items": ["lamp"]},
        physical_feasibility_summary={"mobility": "steady"},
    )

    cards_by_type = {card.factor_type: card for card in frame.affordances.cards}

    assert sorted(cards_by_type) == [
        "action_affordance",
        "environment_affordance",
        "equipment_affordance",
        "physical_feasibility",
        "skill_affordance",
    ]
    assert all(card.layer == "affordance" for card in frame.affordances.cards)
    assert cards_by_type["skill_affordance"].payload["profile_skill_ids"] == [
        "authority_protocol"
    ]
    assert cards_by_type["skill_affordance"].source_refs == ["skill_affordance:summary"]


def test_l3_and_l4_views_consume_affordance_summaries_without_settlement_authority() -> None:
    frame = CharacterMindFrameBuilder().build_frame(
        actor_id="char_a",
        producer_ts=1,
        skill_affordance_summary={
            "available_action_families": {"authority": {"level": "strong"}}
        },
        action_affordance_summary={"available_actions": ["speak_private"]},
        physical_feasibility_summary={"mobility": "steady"},
    )
    builder = LayerContextViewBuilder()

    l3_view = builder.build_l3_view(
        frame,
        interpretation_summary={"risk_level": "medium"},
        workspace=CognitionWorkspace(hard_constraints=["cannot_falsify_authority_report"]),
    )
    l4_view = builder.build_l4_view(
        frame,
        selected_intent="speak_private",
        selected_skill_path={"binding_id": "authority_to_speak_private"},
        target_refs={"actor": "char_b"},
    )

    assert (
        l3_view.skill_affordance_summary["available_action_families"]["authority"]["level"]
        == "strong"
    )
    assert l3_view.action_affordance_summary["available_actions"] == ["speak_private"]
    assert l4_view.physical_feasibility_summary["mobility"] == "steady"
    assert "settlement_result" not in l3_view.model_dump()
    assert "settlement_result" not in l4_view.model_dump()
