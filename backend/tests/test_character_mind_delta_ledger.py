from app.character_agent.mind.delta_ledger import MindDeltaLedgerBuilder
from app.character_agent.models.cognition_delta import (
    CharacterBeliefDelta,
    CharacterDynamicStateDelta,
    CharacterHigherOrderDelta,
    CharacterSocialDelta,
)
from app.character_agent.models.mind_frame import MindDeltaLedger
from app.models.character_agent_runtime import CharacterIntentDecision, CharacterInterpretation


def test_delta_ledger_builder_wraps_l2_l3_l4_settlement_and_evidence_separately() -> None:
    interpretation = CharacterInterpretation(
        actor_id="char_a",
        interpreted_summary="B may be protecting a child.",
        interpretation_type="social_signal",
        salience_score=0.8,
        risk_level="medium",
        opportunity_level="low",
        ambiguity_level="medium",
        belief_deltas=[
            CharacterBeliefDelta(
                proposition_key="b_motive",
                proposition="B's motive may be urgent aid",
                state="suspected",
                confidence=0.7,
            )
        ],
        social_deltas=[
            CharacterSocialDelta(
                entity_id="char_b",
                trust_baseline=0.75,
                suspicion_baseline=0.25,
            )
        ],
        higher_order_deltas=[
            CharacterHigherOrderDelta(
                subject_actor_id="char_b",
                proposition_key="b_motive",
                meta_belief="B may believe the theft is justified",
                confidence=0.6,
            )
        ],
        dynamic_state_delta=CharacterDynamicStateDelta(stress_load=0.4),
    )
    l3_decision = {
        "selected_intent": "speak_private",
        "active_goal_frame": {"primary_goal": "verify_emergency"},
    }
    l4_execution_proposal = {"action_request_bundle": {"requested_actions": []}}
    settlement_result = {"outcome_band": "partial"}
    dialogue_or_action_outcome = {
        "outcome_type": "dialogue_turn",
        "presented_text": "Let's verify what's happening first.",
    }
    evidence_refs = ["event:1"]

    ledger = MindDeltaLedgerBuilder().build(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:1",
        interpretation=interpretation,
        l3_decision=l3_decision,
        l4_execution_proposal=l4_execution_proposal,
        settlement_result=settlement_result,
        dialogue_or_action_outcome=dialogue_or_action_outcome,
        skill_evidence=[{"skill_id": "authority_protocol", "outcome_band": "partial"}],
        drift_candidates=[{"key": "public_disclosure_caution", "direction": "up"}],
        evidence_refs=evidence_refs,
    )

    assert isinstance(ledger, MindDeltaLedger)
    assert ledger.belief_deltas[0]["proposition_key"] == "b_motive"
    assert ledger.social_deltas[0]["entity_id"] == "char_b"
    assert ledger.higher_order_deltas[0]["subject_actor_id"] == "char_b"
    assert ledger.dynamic_state_deltas == {"stress_load": 0.4}
    assert ledger.goal_deltas[0]["selected_intent"] == "speak_private"
    assert ledger.skill_evidence_deltas[0]["skill_id"] == "authority_protocol"
    assert ledger.drift_candidates[0]["key"] == "public_disclosure_caution"
    assert len(ledger.memory_write_candidates) == 1

    envelope = ledger.memory_write_candidates[0]
    assert envelope["event_type"] == "character_mind_turn_summary"
    assert envelope["l3_decision"] == l3_decision
    assert envelope["l4_execution_proposal"] == l4_execution_proposal
    assert envelope["settlement_result"] == settlement_result
    assert envelope["dialogue_or_action_outcome"] == dialogue_or_action_outcome
    assert envelope["evidence_refs"] == evidence_refs


def test_delta_ledger_builder_copies_interpretation_deltas_independently() -> None:
    belief_delta = CharacterBeliefDelta(
        proposition_key="b_motive",
        proposition="B's motive may be urgent aid",
        state="suspected",
        confidence=0.7,
    )
    social_delta = CharacterSocialDelta(
        entity_id="char_b",
        trust_baseline=0.75,
        suspicion_baseline=0.25,
        shared_secret_refs=["secret:1"],
    )
    higher_order_delta = CharacterHigherOrderDelta(
        subject_actor_id="char_b",
        proposition_key="b_motive",
        meta_belief="B may believe the theft is justified",
        confidence=0.6,
    )
    dynamic_state_delta = CharacterDynamicStateDelta(
        stress_load=0.4,
        curiosity=0.3,
    )
    interpretation = CharacterInterpretation(
        actor_id="char_a",
        interpreted_summary="B may be protecting a child.",
        interpretation_type="social_signal",
        salience_score=0.8,
        risk_level="medium",
        opportunity_level="low",
        ambiguity_level="medium",
        belief_deltas=[belief_delta],
        social_deltas=[social_delta],
        higher_order_deltas=[higher_order_delta],
        dynamic_state_delta=dynamic_state_delta,
    )

    ledger = MindDeltaLedgerBuilder().build(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:copy-check",
        interpretation=interpretation,
        evidence_refs=["event:copy-check"],
    )

    belief_delta.proposition = "mutated belief"
    belief_delta.state = "confirmed"
    belief_delta.confidence = 0.1
    social_delta.trust_baseline = 0.1
    social_delta.shared_secret_refs.append("secret:mutated")
    higher_order_delta.meta_belief = "mutated meta belief"
    higher_order_delta.confidence = 0.2
    dynamic_state_delta.stress_load = 0.9
    dynamic_state_delta.curiosity = 0.8

    assert ledger.belief_deltas == [
        {
            "proposition_key": "b_motive",
            "proposition": "B's motive may be urgent aid",
            "state": "suspected",
            "confidence": 0.7,
        }
    ]
    assert ledger.social_deltas == [
        {
            "entity_id": "char_b",
            "trust_baseline": 0.75,
            "suspicion_baseline": 0.25,
            "intimacy": 0.0,
            "dependency": 0.0,
            "unresolved_tension": 0.0,
            "shared_secret_refs": ["secret:1"],
        }
    ]
    assert ledger.higher_order_deltas == [
        {
            "subject_actor_id": "char_b",
            "proposition_key": "b_motive",
            "meta_belief": "B may believe the theft is justified",
            "confidence": 0.6,
        }
    ]
    assert ledger.dynamic_state_deltas == {
        "stress_load": 0.4,
        "curiosity": 0.3,
    }


def test_delta_ledger_builder_does_not_persist_or_mutate_inputs() -> None:
    l3_decision = {"selected_intent": "observe_target", "notes": ["keep distance"]}
    l4_execution_proposal = {"action_request_bundle": {"requested_actions": ["observe"]}}
    settlement_result = {"outcome_band": "pending", "reasons": ["awaiting confirmation"]}
    dialogue_or_action_outcome = {"delivered_lines": ["Hold position."], "status": "queued"}
    need_tension_delta = {"dominant_need": "safety", "supporting_needs": ["order"]}
    skill_evidence = [{"skill_id": "authority_protocol", "tags": ["partial"]}]
    relationship_update_candidates = [{"entity_id": "char_b", "risk_flags": ["uncertain"]}]
    drift_candidates = [{"key": "public_disclosure_caution", "history": ["up"]}]
    evidence_refs = ["event:2"]

    ledger = MindDeltaLedgerBuilder().build(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:2",
        interpretation=None,
        l3_decision=l3_decision,
        l4_execution_proposal=l4_execution_proposal,
        settlement_result=settlement_result,
        dialogue_or_action_outcome=dialogue_or_action_outcome,
        need_tension_delta=need_tension_delta,
        skill_evidence=skill_evidence,
        relationship_update_candidates=relationship_update_candidates,
        drift_candidates=drift_candidates,
        evidence_refs=evidence_refs,
    )
    l3_decision["selected_intent"] = "mutated"
    l3_decision["notes"].append("mutated")
    l4_execution_proposal["action_request_bundle"]["requested_actions"].append("mutated")
    settlement_result["reasons"].append("mutated")
    dialogue_or_action_outcome["delivered_lines"].append("mutated")
    need_tension_delta["supporting_needs"].append("mutated")
    skill_evidence[0]["tags"].append("mutated")
    relationship_update_candidates[0]["risk_flags"].append("mutated")
    drift_candidates[0]["history"].append("mutated")
    evidence_refs.append("mutated")

    assert ledger.goal_deltas[0]["selected_intent"] == "observe_target"
    assert ledger.goal_deltas[0]["notes"] == ["keep distance"]
    assert ledger.need_tension_deltas == {
        "dominant_need": "safety",
        "supporting_needs": ["order"],
    }
    assert ledger.skill_evidence_deltas == [{"skill_id": "authority_protocol", "tags": ["partial"]}]
    assert ledger.relationship_update_candidates == [
        {"entity_id": "char_b", "risk_flags": ["uncertain"]}
    ]
    assert ledger.drift_candidates == [{"key": "public_disclosure_caution", "history": ["up"]}]
    assert len(ledger.memory_write_candidates) == 1
    assert ledger.memory_write_candidates[0] == {
        "event_type": "character_mind_turn_summary",
        "l3_decision": {"selected_intent": "observe_target", "notes": ["keep distance"]},
        "l4_execution_proposal": {
            "action_request_bundle": {"requested_actions": ["observe"]}
        },
        "settlement_result": {
            "outcome_band": "pending",
            "reasons": ["awaiting confirmation"],
        },
        "dialogue_or_action_outcome": {
            "delivered_lines": ["Hold position."],
            "status": "queued",
        },
        "evidence_refs": ["event:2"],
    }


def test_delta_ledger_builder_keeps_goal_and_memory_envelope_l3_payloads_independent() -> None:
    ledger = MindDeltaLedgerBuilder().build(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:alias-check",
        interpretation=None,
        l3_decision={
            "selected_intent": "observe_target",
            "active_goal_frame": {"primary_goal": "verify_emergency"},
        },
        evidence_refs=["event:alias-check"],
    )

    ledger.goal_deltas[0]["active_goal_frame"]["primary_goal"] = "mutated_from_goal_branch"
    assert ledger.memory_write_candidates[0]["l3_decision"] == {
        "selected_intent": "observe_target",
        "active_goal_frame": {"primary_goal": "verify_emergency"},
    }

    ledger.memory_write_candidates[0]["l3_decision"]["selected_intent"] = "mutated_from_memory_branch"
    assert ledger.goal_deltas[0]["selected_intent"] == "observe_target"


def test_delta_ledger_builder_accepts_l3_intent_decision_model() -> None:
    decision = CharacterIntentDecision(
        actor_id="char_a",
        selected_intent="speak_private",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale="Need private clarification.",
        primary_goal="verify_emergency",
    )

    ledger = MindDeltaLedgerBuilder().build(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:3",
        l3_decision=decision,
    )

    assert ledger.goal_deltas[0]["selected_intent"] == "speak_private"
    assert ledger.memory_write_candidates[0]["l3_decision"]["selected_intent"] == "speak_private"


def test_delta_ledger_builder_preserves_candidate_refs_without_injecting_new_ones() -> None:
    skill_evidence = [
        {
            "skill_id": "authority_protocol",
            "evidence_refs": ["skill:event:1"],
            "source_refs": ["skill:source:1"],
        }
    ]
    relationship_update_candidates = [
        {
            "entity_id": "char_b",
            "evidence_refs": ["relationship:event:1"],
            "source_refs": ["relationship:source:1"],
        }
    ]
    drift_candidates = [
        {
            "key": "public_disclosure_caution",
            "evidence_refs": ["drift:event:1"],
            "source_refs": ["drift:source:1"],
        }
    ]

    ledger = MindDeltaLedgerBuilder().build(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:provenance-check",
        interpretation=None,
        skill_evidence=skill_evidence,
        relationship_update_candidates=relationship_update_candidates,
        drift_candidates=drift_candidates,
        evidence_refs=["event:top-level"],
    )

    skill_evidence[0]["evidence_refs"].append("mutated")
    skill_evidence[0]["source_refs"].append("mutated")
    relationship_update_candidates[0]["evidence_refs"].append("mutated")
    relationship_update_candidates[0]["source_refs"].append("mutated")
    drift_candidates[0]["evidence_refs"].append("mutated")
    drift_candidates[0]["source_refs"].append("mutated")

    assert ledger.skill_evidence_deltas == [
        {
            "skill_id": "authority_protocol",
            "evidence_refs": ["skill:event:1"],
            "source_refs": ["skill:source:1"],
        }
    ]
    assert ledger.relationship_update_candidates == [
        {
            "entity_id": "char_b",
            "evidence_refs": ["relationship:event:1"],
            "source_refs": ["relationship:source:1"],
        }
    ]
    assert ledger.drift_candidates == [
        {
            "key": "public_disclosure_caution",
            "evidence_refs": ["drift:event:1"],
            "source_refs": ["drift:source:1"],
        }
    ]
