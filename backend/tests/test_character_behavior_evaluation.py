from app.character_agent.services.character_behavior_evaluation import CharacterBehaviorEvaluationService
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.models.character_perceived import CharacterPerceivedEvent


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
