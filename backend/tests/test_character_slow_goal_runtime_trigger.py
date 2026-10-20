from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.models.character_perceived import CharacterPerceivedEvent


def test_runtime_settlement_trigger_persists_committed_source_before_admission_bridge():
    runtime = CharacterAgentRuntime()
    runtime.ingest_character_perceived_event(CharacterPerceivedEvent(
        actor_id="char_b", percept_channel="visual", producer_ts=100,
        room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
        perceived_summary="a failed task is visible", source_candidate_event_id="percept:100",
        clarity_score=1.0, certainty_score=1.0,
    ))
    received = []
    runtime.set_slow_goal_trigger_handler(lambda **kwargs: received.append(kwargs))
    for index in range(3):
        runtime.record_settlement_result(
            actor_id="char_b", producer_ts=101 + index,
            payload={
                "result_id": f"failure:{index}", "result_type": "constraint_state_result",
                "settlement_status": "rejected", "action_profile": "open",
                "constraint_summary": "blocked", "causation_id": f"cause:{index}",
                "correlation_id": f"cause:{index}",
            },
        )

    assert len(received) == 1
    item = received[0]
    source = item["source_event"]
    trigger = item["trigger"]
    assert source["event_type"] == "character_goal_proposal_trigger"
    assert source["event_id"] == trigger["trigger_source_ref"]
    assert source["event_id"] in trigger["evidence_refs"]
    assert item["frame"]["frame_digest"] == trigger["frame_digest"]
    assert runtime._session_store.read_event("char_b", event_id=source["event_id"]) == source
