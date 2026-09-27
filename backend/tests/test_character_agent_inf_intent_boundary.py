from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.character_agent.execution.l4_executor import CharacterAgentL4Executor
from app.character_agent.models.turn_context import CharacterTurnContext
from app.models.character_agent_runtime import (
    CharacterIntentDecision,
    CharacterInterpretation,
    CharacterPrivateWorldSnapshot,
)
from app.models.siming_character_bridge import (
    CharacterSemanticIntentProposal,
    SimingCharacterCompatibilityInput,
)


def _snapshot() -> CharacterPrivateWorldSnapshot:
    return CharacterPrivateWorldSnapshot(
        actor_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=1400,
        updated_at=1400,
        attention_targets=["char_a"],
        recent_constraint_results=["constraint:stamina_low"],
        salience_tags=["evidence:target_visible"],
    )


def _interpretation() -> CharacterInterpretation:
    return CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="char_a may be speaking nearby",
        interpretation_type="social_signal",
        salience_score=0.88,
        ambiguity_level="medium",
        risk_level="low",
        opportunity_level="medium",
        attention_target="char_a",
        goal_hints=[],
    )


def _decision() -> CharacterIntentDecision:
    return CharacterIntentDecision(
        actor_id="char_b",
        selected_intent="speak_public",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale="char_a may be speaking nearby",
        primary_goal="protect_target",
        supporting_goals=["keep_contact"],
        blockers=["stamina_low"],
        goal_sources=["memory:goal:1"],
    )


def _decision_for_intent(intent: str) -> CharacterIntentDecision:
    return _decision().model_copy(update={"selected_intent": intent})


def _turn() -> CharacterTurnContext:
    return CharacterTurnContext.begin(
        actor_id="char_b",
        source_event_ref="event:perception:1",
        producer_ts=1400,
        causation_id="cause:1",
        correlation_id="corr:1",
        input_revision_vector={"session:char_b": 3},
        memory_revision_vector={"memory:char_b": 4},
        policy_revision="policy:char_b:1",
        snapshot_revision=5,
        branch_id="branch:main",
    )


def test_l4_intent_proposal_is_semantic_and_preserves_provenance() -> None:
    proposal = CharacterAgentL4Executor().build_intent_proposal(
        snapshot=_snapshot(),
        interpretation=_interpretation(),
        decision=_decision(),
        turn_context=_turn(),
    )

    assert proposal.semantic_action_id == "action:speak"
    assert proposal.locomotion_relation == "coexist"
    assert "upper_body" in proposal.claims
    assert "goal:protect_target" in proposal.context_tags
    assert "constraint:stamina_low" in proposal.context_tags
    assert "evidence:target_visible" in proposal.context_tags
    assert proposal.source_id == "character_agent_l4"
    assert proposal.causation_id == "cause:1"
    assert proposal.correlation_id == "corr:1"
    assert proposal.expected_revision_vector == {"session:char_b": 3}
    assert "clip_ref" not in proposal.model_dump()


@pytest.mark.parametrize(
    ("selected_intent", "semantic_action_id", "claims", "locomotion_relation"),
    [
        (
            "short_punch",
            "action:melee.short_punch",
            {"upper_body", "right_arm"},
            "coexist",
        ),
        (
            "unarmed_punch",
            "action:melee.unarmed_punch",
            {"right_arm", "left_arm"},
            "replace_locomotion",
        ),
        (
            "sword_slash",
            "action:melee.sword_slash",
            {"right_arm", "weapon_slot:sword", "weapon_hit_volume:sword"},
            "replace_locomotion",
        ),
    ],
)
def test_l4_melee_proposals_use_female_jk_semantic_contract(
    selected_intent: str,
    semantic_action_id: str,
    claims: set[str],
    locomotion_relation: str,
) -> None:
    proposal = CharacterAgentL4Executor().build_intent_proposal(
        snapshot=_snapshot(),
        interpretation=_interpretation(),
        decision=_decision_for_intent(selected_intent),
        turn_context=_turn(),
    )

    assert proposal.semantic_action_id == semantic_action_id
    assert set(proposal.claims) == claims
    assert proposal.locomotion_relation == locomotion_relation
    assert all(raw not in proposal.model_dump_json() for raw in ("boxing", "short punch", "sword attack"))


def test_semantic_proposal_rejects_low_level_writes_and_raw_clip_selection() -> None:
    with pytest.raises(ValidationError, match="forbidden intent field"):
        SimingCharacterCompatibilityInput(
            message_id="msg:siming:low-level",
            delivery_id="delivery:siming:low-level",
            actor_id="char_a",
            input_type="siming_high_level_message",
            band="impulse",
            producer_ts=1,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            causation_id="cause:low-level",
            correlation_id="corr:low-level",
            semantic_action_id="action:wave",
            transform={"x": 1},
        )

    for raw_clip in ("boxing", "short punch", "sword attack", "boxing.glb", "sword_attack.fbx", "res://clips/boxing"):
        with pytest.raises(ValidationError, match="raw clip"):
            SimingCharacterCompatibilityInput(
                message_id=f"msg:siming:clip:{raw_clip}",
                delivery_id=f"delivery:siming:clip:{raw_clip}",
                actor_id="char_a",
                input_type="siming_high_level_message",
                band="impulse",
                producer_ts=1,
                room_id="room_demo",
                scene_id="scene_demo",
                zone_id="zone_focus",
                causation_id="cause:clip",
                correlation_id="corr:clip",
                semantic_action_id=raw_clip,
            )

    for field_name in ("damage", "hit", "inventory", "projectile", "ammo"):
        with pytest.raises(ValidationError, match="forbidden intent"):
            SimingCharacterCompatibilityInput(
                message_id=f"msg:siming:low-level:{field_name}",
                delivery_id=f"delivery:siming:low-level:{field_name}",
                actor_id="char_a",
                input_type="siming_high_level_message",
                band="impulse",
                producer_ts=1,
                room_id="room_demo",
                scene_id="scene_demo",
                zone_id="zone_focus",
                causation_id="cause:low-level",
                correlation_id="corr:low-level",
                semantic_action_id="action:wave",
                **{field_name: {}},
            )


def test_siming_input_can_only_carry_namespaced_context_and_presentation_metadata() -> None:
    payload = SimingCharacterCompatibilityInput(
        message_id="msg:siming:semantic",
        delivery_id="delivery:siming:semantic",
        actor_id="char_a",
        input_type="siming_high_level_message",
        band="fact_reveal",
        producer_ts=1,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="cause:semantic",
        correlation_id="corr:semantic",
        intent_tags=["goal:protect_target", "evidence:target_visible"],
        context_tags=["constraint:stamina_low"],
        presentation_cues=["presentation:focus_target"],
        reason_codes=["siming:fact_reveal"],
    )

    assert payload.intent_tags == ["goal:protect_target", "evidence:target_visible"]
    assert payload.context_tags == ["constraint:stamina_low"]
    assert payload.presentation_cues == ["presentation:focus_target"]
    assert payload.reason_codes == ["siming:fact_reveal"]


def test_inf_semantic_proposal_preserves_metadata_without_authority_fields() -> None:
    proposal = CharacterSemanticIntentProposal.from_inf_payload(
        {
            "actor_ref": "character:char_a",
            "semantic_action_id": "action:melee.short_punch",
            "intent_tags": ["goal:protect_target"],
            "context_tags": ["evidence:target_visible"],
            "presentation_cues": ["presentation:focus_target"],
            "reason_codes": ["inf:constraint_projection"],
            "source": "inf",
            "confidence": 0.72,
            "expected_revision_vector": {"session:char_a": 9},
            "causation_id": "cause:inf:1",
            "correlation_id": "corr:inf:1",
        }
    )

    assert proposal.semantic_action_id == "action:melee.short_punch"
    assert proposal.intent_tags == ["goal:protect_target"]
    assert proposal.context_tags == ["evidence:target_visible"]
    assert proposal.presentation_cues == ["presentation:focus_target"]
    assert proposal.reason_codes == ["inf:constraint_projection"]
    assert proposal.source == "inf"
    assert proposal.confidence == 0.72
    assert proposal.expected_revision_vector == {"session:char_a": 9}
    assert proposal.causation_id == "cause:inf:1"
    assert proposal.correlation_id == "corr:inf:1"
    assert "transform" not in proposal.model_dump()
    assert "damage" not in proposal.model_dump()


def test_godot_agent_ingress_stays_pending_until_authority_result() -> None:
    root = Path(__file__).resolve().parents[2]
    runtime_state = (root / "scripts" / "character" / "CharacterRuntimeState.gd").read_text(encoding="utf-8")
    adapter = (root / "scripts" / "character" / "AgentControllerAdapter.gd").read_text(encoding="utf-8")

    assert "func stage_agent_intent_proposal" in runtime_state
    assert "func apply_authority_result" in runtime_state
    assert "if not bool(result.get(\"committed\", false))" in runtime_state
    assert "latest_authority_result = result.duplicate(true)" in runtime_state
    assert "CharacterControllerPortRef.submit_intent_proposal" in adapter
    for forbidden_field in ("hit", "inventory", "projectile", "ammo"):
        assert f'"{forbidden_field}"' in adapter
    assert "AnimationPlayer" not in adapter
    assert "global_position =" not in adapter
    assert "velocity =" not in adapter
