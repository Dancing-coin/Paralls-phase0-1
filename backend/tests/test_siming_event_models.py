from app.models.authority_event import AuthorityEvent
from app.models.siming_event import SimingAuditRecord, SimingInput, SimingOutput, SimingTickResult

from tests.test_authority_event import valid_event_dict


def test_siming_input_preserves_source_authority_event() -> None:
    event = AuthorityEvent.model_validate(valid_event_dict())
    siming_input = SimingInput(input_type="visual_fact_event", source_event=event)

    assert siming_input.source_event.event_id == "evt_visual_1"
    assert siming_input.input_type == "visual_fact_event"


def test_siming_output_can_represent_dispatch_intent() -> None:
    output = SimingOutput(
        output_type="dispatch_intent",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="evt_visual_1",
        correlation_id="visual_fact:100",
        producer_ts=101,
        selected_path="visual_fact_path",
        intervention_band="fact_reveal",
        payload={"established_fact_id": "evt_visual_1"},
    )

    assert output.selected_path == "visual_fact_path"
    assert output.payload["established_fact_id"] == "evt_visual_1"


def test_siming_tick_result_groups_outputs_and_audit_records() -> None:
    audit = SimingAuditRecord(
        audit_id="audit_evt_visual_1",
        room_id="room_demo",
        correlation_id="visual_fact:100",
        causation_id="evt_visual_1",
        source_event_id="evt_visual_1",
        status="no_action",
        reason="no eligible intervention",
    )
    result = SimingTickResult(outputs=[], audit_records=[audit])

    assert result.audit_records[0].status == "no_action"
