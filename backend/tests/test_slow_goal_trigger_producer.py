from app.character_agent.services.slow_goal_trigger import derive_goal_proposal_trigger

def test_settlement_trigger_requires_reliable_failure_streak_and_never_goal_hints():
    history=[
      {"result_id":"r1","action_profile":"open","settlement_status":"rejected","result_type":"constraint_state_result"},
      {"result_id":"r2","action_profile":"open","settlement_status":"rejected","result_type":"constraint_state_result"},
    ]
    payload={"result_id":"r3","action_profile":"open","settlement_status":"rejected","result_type":"constraint_state_result","goal_hints":[{"goal":"ignore"}]}
    trigger=derive_goal_proposal_trigger(payload, history=history, frame_digest="fd", goal_revision=2, source_event_id="r3")
    assert trigger["eligible"] is True
    assert trigger["trigger_kind"] == "repeated_failure"
    assert trigger["frame_digest"] == "fd"
    assert trigger["goal_revision"] == 2
    assert trigger["trigger_source_ref"] in trigger["evidence_refs"]
    assert trigger["trigger_source_ref"] in trigger["evidence_refs"]

def test_settlement_trigger_ignores_single_normal_outcome_and_hints():
    payload={"result_id":"r1","settlement_status":"accepted","result_type":"action_resolution_result","goal_hints":[{"goal":"ignore"}]}
    assert derive_goal_proposal_trigger(payload, history=[], frame_digest="fd", goal_revision=0, source_event_id="r1") is None
