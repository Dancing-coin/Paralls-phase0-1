import pytest
from pydantic import ValidationError

from app.character_agent import models as character_models
from app.character_agent.models.mind_frame import (
    CharacterMindFrame,
    CharacterMindFrameTrigger,
    CognitionWorkspace,
    L2InterpretationView,
    L3PlanningView,
    L4ExecutionView,
    MentalFactorProjectionCard,
    MindDeltaLedger,
    MindFrameLayer,
    MindFrameProvenance,
    WritebackView,
)


def _card(
    factor_type: str,
    summary: str,
    *,
    layer: str = "memory_evidence",
) -> MentalFactorProjectionCard:
    return MentalFactorProjectionCard(
        factor_type=factor_type,
        layer=layer,
        scope="actor_private",
        horizon="scene",
        confidence=0.8,
        freshness="current",
        summary=summary,
        source_refs=[f"{factor_type}:source"],
        risk_notes=[],
    )


def test_projection_card_is_typed_traceable_and_bounded() -> None:
    card = _card("relationship", "A trusts B but carries tension.")

    assert card.factor_type == "relationship"
    assert card.scope == "actor_private"
    assert card.confidence == 0.8
    assert card.source_refs == ["relationship:source"]


def test_projection_card_rejects_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        MentalFactorProjectionCard(
            factor_type="relationship",
            layer="memory_evidence",
            scope="actor_private",
            confidence=1.5,
            summary="bad confidence",
        )


def test_mind_frame_keeps_layers_separate() -> None:
    frame = CharacterMindFrame(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:123",
        producer_ts=123,
        trigger=CharacterMindFrameTrigger(
            event_id="event:456",
            event_type="character_perceived_event",
        ),
        enduring_truth=MindFrameLayer(
            cards=[_card("effective_profile", "profile summary", layer="enduring_truth")]
        ),
        memory_evidence=MindFrameLayer(
            cards=[_card("relationship", "relationship summary", layer="memory_evidence")]
        ),
        runtime_state=MindFrameLayer(
            cards=[_card("need_pressure", "need summary", layer="runtime_state")]
        ),
        affordances=MindFrameLayer(
            cards=[_card("skill_affordance", "skill summary", layer="affordance")]
        ),
        provenance=MindFrameProvenance(
            source_refs=["profile:char_a", "memory:event:1"],
        ),
    )

    assert frame.enduring_truth.cards[0].factor_type == "effective_profile"
    assert frame.memory_evidence.cards[0].factor_type == "relationship"
    assert frame.runtime_state.cards[0].factor_type == "need_pressure"
    assert frame.affordances.cards[0].factor_type == "skill_affordance"


def test_mind_frame_rejects_mislayered_card() -> None:
    with pytest.raises(ValidationError):
        CharacterMindFrame(
            actor_id="char_a",
            mind_turn_id="mind_turn:char_a:123",
            enduring_truth=MindFrameLayer(
                cards=[_card("need_pressure", "need summary", layer="runtime_state")]
            ),
        )


def test_mind_frame_accepts_perception_context_in_runtime_state() -> None:
    frame = CharacterMindFrame(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:123",
        runtime_state=MindFrameLayer(
            cards=[
                _card(
                    "perception_context",
                    "Current scene observations are active.",
                    layer="runtime_state",
                )
            ]
        ),
    )

    assert frame.runtime_state.cards[0].factor_type == "perception_context"


def test_mind_frame_accepts_personality_bias_in_enduring_truth() -> None:
    frame = CharacterMindFrame(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:123",
        enduring_truth=MindFrameLayer(
            cards=[
                _card(
                    "personality_bias",
                    "Defaults toward caution under public scrutiny.",
                    layer="enduring_truth",
                )
            ]
        ),
    )

    assert frame.enduring_truth.cards[0].factor_type == "personality_bias"


def test_mind_frame_accepts_equipment_affordance_in_affordances() -> None:
    frame = CharacterMindFrame(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:123",
        affordances=MindFrameLayer(
            cards=[
                _card(
                    "equipment_affordance",
                    "Can use the issued badge scanner at this station.",
                    layer="affordance",
                )
            ]
        ),
    )

    assert frame.affordances.cards[0].factor_type == "equipment_affordance"


def test_cognition_workspace_is_turn_local_not_memory() -> None:
    workspace = CognitionWorkspace(
        active_anchors=["B once saved A"],
        dominant_drivers=["preserve_order"],
        active_conflicts=["order_vs_loyalty"],
        decision_biases=["avoid_direct_deception"],
        hard_constraints=["cannot_falsify_authority_report"],
        candidate_questions=["Is the emergency real?"],
    )

    assert workspace.active_anchors == ["B once saved A"]
    assert "order_vs_loyalty" in workspace.active_conflicts


def test_layer_views_have_distinct_payloads() -> None:
    l2_view = L2InterpretationView(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:123",
        perception_context={"focus_target": "char_b"},
        effective_profile_summary={"summary": "order-valuing"},
        memory_activation_summary={"count": 2},
        cognitive_anchor_summary={"anchors": ["B saved A"]},
        relationship_context_summary={"target": "char_b", "trust_band": "high"},
        need_pressure_summary={"dominant_need": "esteem"},
        affective_body_summary={"stress_load": 0.4},
        goal_context_summary={"primary_goal": "preserve_order"},
        unresolved_tension_summary={"count": 1},
        supervision_summary={"mode": "none"},
    )
    l3_view = L3PlanningView(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:123",
        interpretation_summary={"risk_level": "medium"},
        cognition_workspace=CognitionWorkspace(active_conflicts=["order_vs_loyalty"]),
        goal_context_summary={"primary_goal": "preserve_order"},
        need_pressure_summary={"dominant_need": "esteem"},
        affective_body_summary={"stress_load": 0.4},
        skill_affordance_summary={"available_action_families": {}},
        action_affordance_summary={"available_actions": []},
        relationship_affordance_summary={"trust_band": "high"},
        hard_constraints=["cannot_falsify_authority_report"],
        unresolved_tension_summary={"count": 1},
        supervision_summary={"mode": "none"},
    )
    l4_view = L4ExecutionView(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:123",
        selected_intent="speak_private",
        target_refs={"actor": "char_b"},
        affective_body_summary={"stress_load": 0.4},
        presentation_constraints=["low_voice"],
        realization_hints=["controlled_posture"],
        physical_feasibility_summary={"status": "advisory"},
    )

    assert l2_view.relationship_context_summary["trust_band"] == "high"
    assert l3_view.cognition_workspace.active_conflicts == ["order_vs_loyalty"]
    assert l4_view.selected_intent == "speak_private"


def test_delta_ledger_keeps_writeback_candidates_separate() -> None:
    ledger = MindDeltaLedger(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:123",
        belief_deltas=[{"proposition_key": "b_motive", "state": "suspected"}],
        social_deltas=[{"entity_id": "char_b", "trust_baseline": 0.7}],
        dynamic_state_deltas={"stress_load": 0.4},
        goal_deltas=[{"goal": "verify_emergency"}],
        skill_evidence_deltas=[{"skill_id": "persuasion", "outcome_band": "partial"}],
        memory_write_candidates=[{"event_type": "character_interpretation_event"}],
        relationship_update_candidates=[{"entity_id": "char_b", "unresolved_tension": 0.2}],
        drift_candidates=[{"key": "conflict_style", "direction": "avoidance_up"}],
    )

    assert ledger.skill_evidence_deltas[0]["skill_id"] == "persuasion"
    assert ledger.relationship_update_candidates[0]["entity_id"] == "char_b"


def test_writeback_view_wraps_settlement_and_delta_context() -> None:
    view = WritebackView(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:123",
        l2_deltas={"belief_deltas": []},
        l3_decision={"selected_intent": "speak_private"},
        l4_execution_proposal={"action_request_bundle": {"requested_actions": []}},
        settlement_result={"outcome_band": "partial"},
        evidence_refs=["event:1"],
    )

    assert view.l3_decision["selected_intent"] == "speak_private"
    assert view.evidence_refs == ["event:1"]


def test_models_module_re_exports_mind_frame_contracts() -> None:
    assert character_models.CharacterMindFrame is CharacterMindFrame
    assert character_models.MentalFactorProjectionCard is MentalFactorProjectionCard


def test_strict_models_reject_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        MentalFactorProjectionCard(
            factor_type="relationship",
            layer="memory_evidence",
            summary="unexpected field",
            unexpected=True,
        )
