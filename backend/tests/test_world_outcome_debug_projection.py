from app.services.world_outcome_debug_projection import WorldOutcomeDebugProjection


def test_world_outcome_debug_projection_structures_successful_settlement() -> None:
    projection = WorldOutcomeDebugProjection()

    event = projection.project(
        message_type="world_result",
        payload={
            "producer_ts": 500,
            "causation_id": "interact:500",
            "correlation_id": "scene-500",
            "actor_id": "char_c",
            "target_object_id": "obj_letter",
            "result_type": "object_state_result",
            "source_action_request_type": "inspect",
            "settlement_status": "accepted",
            "change_summary": "obj_letter changed from hidden to visible",
            "stable_state_summary": "interaction accepted",
        },
    )

    assert event.request_type == "inspect"
    assert event.target_ref == "obj_letter"
    assert event.settlement_status == "accepted"
    assert event.world_change_summary == "obj_letter changed from hidden to visible"
    assert "interaction accepted" in event.dramatic_consequence_summary


def test_world_outcome_debug_projection_structures_rejected_constraint() -> None:
    projection = WorldOutcomeDebugProjection()

    event = projection.project(
        message_type="world_result",
        payload={
            "producer_ts": 501,
            "causation_id": "interact:501",
            "correlation_id": "scene-501",
            "actor_id": "char_c",
            "target_object_id": "obj_letter",
            "result_type": "constraint_state_result",
            "source_action_request_type": "inspect",
            "constraint_summary": "out_of_range",
            "settlement_status": "rejected",
        },
    )

    assert event.request_type == "inspect"
    assert event.settlement_status == "rejected"
    assert event.constraint_summary == "out_of_range"
    assert "rejected" in event.dramatic_consequence_summary
