import pytest

from app.character_agent.services.character_behavior_evaluation import CharacterBehaviorEvaluationService
from app.character_agent.models.turn_context import CharacterTurnContext
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.models.character_perceived import CharacterPerceivedEvent


def _settled_turn_for_evaluation() -> CharacterTurnContext:
    turn = CharacterTurnContext.begin(
        actor_id="char_b",
        source_event_ref="visual:door",
        producer_ts=10,
        causation_id="cause:door",
        correlation_id="corr:door",
        input_revision_vector={"l1_input": 10},
        memory_revision_vector={"memory": 1},
        policy_revision="policy:character-runtime:v1",
        snapshot_revision=10,
        branch_id="branch:main",
    )
    for stage, payload in (
        ("context", {"l1_snapshot": {"target": "door"}}),
        ("interpretation", {"interpreted_summary": "the archive door is closed"}),
        ("goal", {"goal_id": "open_archive_door", "transition": "active"}),
        ("intent", {"selected_intent": "open_door"}),
        ("execution", {"execution_ref": "execution:door"}),
    ):
        turn, _ = turn.stage_event(
            stage,
            stage_ref=f"stage:{stage}",
            idempotency_key=f"key:{stage}",
            producer_ts=10,
            payload=payload,
        )
    return turn


def test_evaluation_marks_unprovable_social_effect_unknown_not_neutral() -> None:
    result = CharacterBehaviorEvaluationService().evaluate(
        turn=_settled_turn_for_evaluation(),
        settlement_event={
            "event_id": "settlement:door",
            "event_type": "character_agent_settlement_result",
            "producer_ts": 11,
            "payload": {
                "settlement_status": "accepted",
                "result_type": "object_state_result",
                "change_summary": "archive door opened",
                "authority_event_ref": "authority:door:accepted",
                "authority_owner_ref": "esm:world",
            },
        },
        timeline=[],
    )

    assert result.execution_quality_score == 1.0
    assert result.social_consequence_score is None
    assert "social_consequence" in result.unknown_dimensions
    assert result.evidence_refs


def test_candidate_policy_is_not_suppressed_by_high_compatibility_score() -> None:
    result = CharacterBehaviorEvaluationService().evaluate(
        turn=_settled_turn_for_evaluation(),
        settlement_event={
            "event_id": "settlement:cost",
            "producer_ts": 11,
            "payload": {
                "settlement_status": "accepted",
                "result_type": "object_state_result",
                "change_summary": "door opened with constraint cost",
                "action_settlement_result": {
                    "outcome_band": "clean_success",
                    "failure_domains": ["world_constraint"],
                },
            },
        },
        timeline=[],
    )

    assert result.behavior_score >= 0.75
    assert result.candidate_policy is not None
    assert result.candidate_policy["policy_type"] == "recovery"


def test_cross_turn_role_evidence_does_not_leak_into_current_evaluation() -> None:
    turn = _settled_turn_for_evaluation()
    result = CharacterBehaviorEvaluationService().evaluate(
        turn=turn,
        settlement_event={
            "event_id": "settlement:current",
            "producer_ts": 11,
            "payload": {
                "turn_id": turn.turn_id,
                "correlation_id": turn.correlation_id,
                "settlement_status": "accepted",
                "result_type": "object_state_result",
                "change_summary": "door opened",
            },
        },
        timeline=[
            {
                "event_id": "prior:role",
                "event_type": "role_evidence",
                "producer_ts": 9,
                "payload": {
                    "turn_id": "turn:other",
                    "correlation_id": "corr:other",
                    "role_consistency": 0.1,
                },
            }
        ],
    )

    assert result.role_consistency_score is None
    assert "role_consistency" in result.unknown_dimensions
    assert "prior:role" not in result.evidence_refs


def test_behavior_evaluator_links_context_to_settlement_and_emits_recovery_candidate() -> None:
    service = CharacterBehaviorEvaluationService()
    timeline = [
        {
            "event_id": "l2:1",
            "event_type": "l2_reasoning_request",
            "producer_ts": 10,
            "payload": {
                "context": {
                    "memory_recall": {
                        "context_hash": "hash:1",
                        "selected_memory_refs": ["event:event:letter"],
                        "token_budget": 1200,
                        "estimated_tokens": 42,
                        "truncated": False,
                    }
                }
            },
        },
        {
            "event_id": "interpretation:1",
            "event_type": "character_interpretation_event",
            "producer_ts": 10,
            "payload": {"interpreted_summary": "the letter is missing", "attention_target": "obj_letter"},
        },
        {
            "event_id": "execution:1",
            "event_type": "character_agent_execution_request",
            "producer_ts": 10,
            "payload": {"selected_intent": "inspect", "action_request_bundle": {}},
        },
    ]
    result = service.evaluate(
        actor_id="char_b",
        timeline=timeline,
        settlement_event={
            "event_id": "settlement:1",
            "event_type": "character_agent_settlement_result",
            "producer_ts": 11,
            "payload": {
                "settlement_status": "rejected",
                "result_type": "constraint_state_result",
                "action_settlement_result": {
                    "outcome_band": "blocked",
                    "failure_domains": ["world_constraint"],
                },
            },
        },
    )

    assert result["context_hash"] == "hash:1"
    assert result["selected_memory_refs"] == ["event:event:letter"]
    assert result["behavior_score"] == 0.2
    assert result["candidate_policy"]["policy_type"] == "recovery"
    assert "settlement:1" in result["source_refs"]


def test_runtime_persists_behavior_evaluation_and_candidate_after_settlement() -> None:
    runtime = CharacterAgentRuntime()
    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_a",
            percept_channel="visual",
            producer_ts=100,
            room_id="room",
            scene_id="scene",
            zone_id="zone",
            perceived_summary="the letter is gone",
            source_candidate_event_id="visual:letter",
            target_object_id="obj_letter",
        )
    )
    runtime.record_settlement_result(
        actor_id="char_a",
        producer_ts=101,
        payload={
            "turn_id": "turn:char_a:letter",
            "branch_id": "branch:main",
            "causation_id": "cause:letter",
            "correlation_id": "corr:letter",
            "settlement_status": "rejected",
            "result_type": "constraint_state_result",
            "constraint_summary": "requires a key",
        },
    )

    timeline = runtime.get_session_timeline("char_a")
    evaluations = [entry for entry in timeline if entry["event_type"] == "character_behavior_evaluation_event"]
    candidates = [entry for entry in timeline if entry["event_type"] == "character_behavior_policy_proposed"]
    accepted = [entry for entry in timeline if entry["event_type"] == "character_behavior_policy_reconciled"]
    settlement = [entry for entry in timeline if entry["event_type"] == "character_agent_settlement_result"][-1]
    assert evaluations
    assert evaluations[-1]["payload"]["settlement_event_id"]
    assert evaluations[-1]["payload"]["behavior_score"] < 0.75
    assert candidates
    assert candidates[-1]["payload"]["record"]["status"] == "candidate"
    assert candidates[-1]["payload"]["record"]["source_revision"] == settlement["event_index"]
    assert accepted[-1]["payload"]["record"]["status"] == "accepted"


def test_runtime_rejects_mismatched_settlement_source_revision() -> None:
    runtime = CharacterAgentRuntime()
    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_revision",
            percept_channel="visual",
            producer_ts=100,
            room_id="room",
            scene_id="scene",
            zone_id="zone",
            perceived_summary="the letter is gone",
            source_candidate_event_id="visual:letter",
            target_object_id="obj_letter",
        )
    )
    runtime.record_settlement_result(
        actor_id="char_revision",
        producer_ts=101,
        payload={
            "turn_id": "turn:char_revision:letter",
            "branch_id": "branch:main",
            "causation_id": "cause:letter",
            "correlation_id": "corr:letter",
            "source_revision": 999,
            "settlement_status": "rejected",
            "result_type": "constraint_state_result",
            "constraint_summary": "requires a key",
        },
    )

    timeline = runtime.get_session_timeline("char_revision")
    assert not [entry for entry in timeline if entry["event_type"] == "character_behavior_policy_proposed"]


def test_runtime_requires_persisted_settlement_event_index_for_policy_source_revision() -> None:
    runtime = CharacterAgentRuntime()
    runtime._record_behavior_evaluation(
        actor_id="char_missing_revision",
        producer_ts=101,
        settlement_event={
            "event_id": "settlement:missing-index",
            "event_type": "character_agent_settlement_result",
            "producer_ts": 101,
            "payload": {
                "turn_id": "turn:char_missing_revision:letter",
                "branch_id": "branch:main",
                "causation_id": "cause:letter",
                "correlation_id": "corr:letter",
                "settlement_status": "rejected",
                "result_type": "constraint_state_result",
                "constraint_summary": "requires a key",
            },
        },
    )

    timeline = runtime.get_session_timeline("char_missing_revision")
    assert not [entry for entry in timeline if entry["event_type"] == "character_behavior_policy_proposed"]


def test_evaluator_marks_unknown_or_incomplete_failure_evidence_unqualified() -> None:
    result = CharacterBehaviorEvaluationService().evaluate(
        actor_id="char_b",
        timeline=[],
        settlement_event={
            "event_id": "settlement:unknown", "producer_ts": 10,
            "payload": {"settlement_status": "rejected"},
        },
    )

    assert result["candidate_policy"]["evidence"]["qualified"] is False
    assert result["candidate_policy"]["evidence"]["complete"] is False


def test_result_id_evidence_ref_resolves_to_exact_settlement_for_policy_gate() -> None:
    runtime = CharacterAgentRuntime()
    settlement = {
        "event_id": "settlement:event:1",
        "payload": {
            "result_id": "result:1",
            "settlement_status": "accepted",
            "result_type": "object_state_result",
            "change_summary": "door opened",
        },
    }
    evidence = {
        "qualified": True,
        "complete": True,
        "confidence": 0.9,
        "evidence_refs": ["result:1", "context:1"],
        "settlement_event_id": "result:1",
        "context_hash": "hash:1",
    }

    assert runtime._behavior_evidence_is_qualified(
        evidence=evidence,
        evidence_refs=["result:1", "context:1"],
        settlement_event=settlement,
        timeline=[
            {
                "event_id": "context:1",
                "payload": {"turn_id": "turn:1", "summary": "context"},
            }
        ],
    ) is True


def test_duplicate_settlement_result_id_conflict_fails_closed() -> None:
    runtime = CharacterAgentRuntime()
    runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_conflict",
            percept_channel="visual",
            producer_ts=100,
            room_id="room",
            scene_id="scene",
            zone_id="zone",
            perceived_summary="letter",
            source_candidate_event_id="visual:conflict",
        )
    )
    first = {
        "result_id": "result:conflict",
        "settlement_status": "rejected",
        "result_type": "constraint_state_result",
        "constraint_summary": "requires a key",
    }
    runtime.record_settlement_result(actor_id="char_conflict", producer_ts=101, payload=first)
    before = runtime.get_session_timeline("char_conflict")
    with pytest.raises(ValueError, match="character_settlement_replay_conflict"):
        runtime.record_settlement_result(
            actor_id="char_conflict",
            producer_ts=101,
            payload={**first, "settlement_status": "accepted", "change_summary": "opened"},
        )
    assert runtime.get_session_timeline("char_conflict") == before
