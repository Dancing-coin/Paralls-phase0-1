from app.character_agent.mind.delta_ledger import MindDeltaLedgerBuilder
from app.character_agent.models.cognition_delta import (
    CharacterBeliefDelta,
    CharacterDynamicStateDelta,
)
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.models.character_agent_runtime import CharacterInterpretation


def test_runtime_applies_ledger_writeback_through_existing_store_boundaries() -> None:
    runtime = CharacterAgentRuntime()
    interpretation = CharacterInterpretation(
        actor_id="char_a",
        interpreted_summary="B may need help.",
        interpretation_type="social_signal",
        salience_score=0.8,
        risk_level="medium",
        opportunity_level="low",
        ambiguity_level="medium",
        belief_deltas=[
            CharacterBeliefDelta(
                proposition_key="b_needs_help",
                proposition="B may need help",
                state="suspected",
                confidence=0.8,
            )
        ],
        dynamic_state_delta=CharacterDynamicStateDelta(stress_load=0.5),
    )
    ledger = MindDeltaLedgerBuilder().build(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:1",
        interpretation=interpretation,
        l3_decision={"selected_intent": "speak_private"},
        evidence_refs=["event:source"],
    )

    runtime.apply_mind_delta_ledger(
        actor_id="char_a",
        producer_ts=123,
        ledger=ledger,
    )

    timeline = runtime.get_session_timeline("char_a")
    event_types = [entry["event_type"] for entry in timeline]

    assert "knowledge_belief_event" in event_types
    assert "dynamic_state_event" in event_types
    assert "character_mind_turn_summary_event" in event_types
    assert runtime.get_dynamic_state("char_a")["stress_load"] == 0.5


def test_ledger_writeback_does_not_mutate_authored_profile_or_treat_social_graph_as_truth() -> None:
    runtime = CharacterAgentRuntime()
    before_profile = runtime._effective_profile_payload("char_a")
    ledger = MindDeltaLedgerBuilder().build(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:2",
        interpretation=None,
        relationship_update_candidates=[
            {"entity_id": "char_b", "trust_baseline": 0.7, "source_refs": ["event:source"]}
        ],
        drift_candidates=[{"key": "caution", "direction": "up"}],
        evidence_refs=["event:source"],
    )

    runtime.apply_mind_delta_ledger(
        actor_id="char_a",
        producer_ts=124,
        ledger=ledger,
    )

    after_profile = runtime._effective_profile_payload("char_a")
    timeline = runtime.get_session_timeline("char_a")

    assert before_profile == after_profile
    assert any(entry["event_type"] == "social_cognition_event" for entry in timeline)
    assert any(entry["event_type"] == "character_drift_candidate_event" for entry in timeline)


def test_ledger_writeback_filters_invalid_social_and_higher_order_entries_before_writeback() -> None:
    runtime = CharacterAgentRuntime()
    ledger = MindDeltaLedgerBuilder().build(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:3",
        interpretation=None,
        relationship_update_candidates=[
            {"entity_id": "", "trust_baseline": 0.2},
            {"entity_id": "char_b", "trust_baseline": 0.7, "shared_secret_refs": ["secret:1"]},
        ],
        evidence_refs=["event:source"],
    )
    ledger.social_deltas = [
        {"entity_id": "", "trust_baseline": 0.1},
        {"entity_id": "char_c", "trust_baseline": 0.6},
    ]
    ledger.higher_order_deltas = [
        {
            "subject_actor_id": "",
            "proposition_key": "invalid_subject",
            "meta_belief": "missing subject",
            "confidence": 0.4,
        },
        {
            "subject_actor_id": "char_b",
            "proposition_key": "",
            "meta_belief": "missing proposition",
            "confidence": 0.5,
        },
        {
            "subject_actor_id": "char_c",
            "proposition_key": "knows_secret",
            "meta_belief": "char_c knows more",
            "confidence": 0.8,
        },
    ]

    runtime.apply_mind_delta_ledger(
        actor_id="char_a",
        producer_ts=125,
        ledger=ledger,
    )

    timeline = runtime.get_session_timeline("char_a")
    social_payloads = [
        entry["payload"]
        for entry in timeline
        if entry["event_type"] == "social_cognition_event"
    ]
    higher_order_payloads = [
        entry["payload"]
        for entry in timeline
        if entry["event_type"] == "higher_order_belief_event"
    ]

    assert [payload["entity_id"] for payload in social_payloads] == ["char_c", "char_b"]
    assert [payload["event_index"] for payload in social_payloads] == [1, 2]
    assert all(payload["entity_id"] != "" for payload in social_payloads)

    assert len(higher_order_payloads) == 1
    assert higher_order_payloads[0]["subject_actor_id"] == "char_c"
    assert higher_order_payloads[0]["proposition_key"] == "knows_secret"
    assert higher_order_payloads[0]["meta_belief"] == "char_c knows more"
    assert higher_order_payloads[0]["event_index"] == 1


def test_ledger_writeback_rejects_unsupported_actor_without_appending_events() -> None:
    runtime = CharacterAgentRuntime()
    ledger = MindDeltaLedgerBuilder().build(
        actor_id="char_unknown",
        mind_turn_id="mind_turn:char_unknown:1",
        interpretation=None,
    )

    try:
        runtime.apply_mind_delta_ledger(
            actor_id="char_unknown",
            producer_ts=126,
            ledger=ledger,
        )
    except ValueError as exc:
        assert str(exc) == "unsupported actor_id: char_unknown"
    else:
        raise AssertionError("expected ValueError for unsupported actor")

    assert runtime.get_session_timeline("char_unknown") == []


def test_ledger_writeback_rejects_mismatched_ledger_actor_without_appending_events() -> None:
    runtime = CharacterAgentRuntime()
    ledger = MindDeltaLedgerBuilder().build(
        actor_id="char_b",
        mind_turn_id="mind_turn:char_b:1",
        interpretation=None,
    )

    try:
        runtime.apply_mind_delta_ledger(
            actor_id="char_a",
            producer_ts=127,
            ledger=ledger,
        )
    except ValueError as exc:
        assert str(exc) == "ledger actor_id mismatch"
    else:
        raise AssertionError("expected ValueError for mismatched ledger actor")

    assert runtime.get_session_timeline("char_a") == []


def test_ledger_writeback_skips_non_dict_candidates_and_keeps_candidate_payloads_isolated() -> None:
    runtime = CharacterAgentRuntime()
    ledger = MindDeltaLedgerBuilder().build(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:4",
        interpretation=None,
        evidence_refs=["event:source"],
    )
    ledger.memory_write_candidates = [
        {"event_type": "character_mind_turn_summary", "marker": {"value": 1}},
        "skip-me",
    ]
    ledger.skill_evidence_deltas = [
        {"skill_id": "authority_protocol", "marker": {"value": 2}},
        123,
    ]
    ledger.drift_candidates = [
        {"key": "caution", "marker": {"value": 3}},
        ["skip-me"],
    ]

    runtime.apply_mind_delta_ledger(
        actor_id="char_a",
        producer_ts=128,
        ledger=ledger,
    )

    ledger.memory_write_candidates[0]["marker"]["value"] = 99
    ledger.skill_evidence_deltas[0]["marker"]["value"] = 99
    ledger.drift_candidates[0]["marker"]["value"] = 99

    timeline = runtime.get_session_timeline("char_a")
    summary_payloads = [
        entry["payload"]
        for entry in timeline
        if entry["event_type"] == "character_mind_turn_summary_event"
    ]
    skill_payloads = [
        entry["payload"]
        for entry in timeline
        if entry["event_type"] == "character_skill_evidence_candidate_event"
    ]
    drift_payloads = [
        entry["payload"]
        for entry in timeline
        if entry["event_type"] == "character_drift_candidate_event"
    ]

    assert len(summary_payloads) == 1
    assert len(skill_payloads) == 1
    assert len(drift_payloads) == 1
    assert summary_payloads[0]["marker"]["value"] == 1
    assert skill_payloads[0]["marker"]["value"] == 2
    assert drift_payloads[0]["marker"]["value"] == 3


def test_ledger_writeback_ignores_unsupported_dynamic_state_keys_and_keeps_valid_fields() -> None:
    runtime = CharacterAgentRuntime()
    ledger = MindDeltaLedgerBuilder().build(
        actor_id="char_a",
        mind_turn_id="mind_turn:char_a:5",
        interpretation=None,
        evidence_refs=["event:source"],
    )
    ledger.dynamic_state_deltas = {
        "stress_load": 0.5,
        "unsupported_key": "ignore-me",
    }

    runtime.apply_mind_delta_ledger(
        actor_id="char_a",
        producer_ts=129,
        ledger=ledger,
    )

    dynamic_state = runtime.get_dynamic_state("char_a")
    timeline = runtime.get_session_timeline("char_a")
    dynamic_events = [
        entry["payload"]
        for entry in timeline
        if entry["event_type"] == "dynamic_state_event"
    ]

    assert dynamic_state["stress_load"] == 0.5
    assert "unsupported_key" not in dynamic_state
    assert len(dynamic_events) == 1
    assert dynamic_events[0]["stress_load"] == 0.5
    assert "unsupported_key" not in dynamic_events[0]
