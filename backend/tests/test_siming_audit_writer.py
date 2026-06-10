from app.models.siming_event import SimingAuditCorrection, SimingAuditRecord
from app.services.siming_audit_writer import SimingAuditWriter


def make_audit(audit_id: str = "audit_evt_visual_1") -> SimingAuditRecord:
    return SimingAuditRecord(
        audit_id=audit_id,
        room_id="room_demo",
        correlation_id="visual_fact:100",
        causation_id="evt_visual_1",
        source_event_id="evt_visual_1",
        status="no_action",
        reason="no eligible intervention",
    )


def test_audit_writer_records_no_action_and_queries_by_correlation() -> None:
    writer = SimingAuditWriter()
    writer.record(make_audit())

    records = writer.find_by_correlation(room_id="room_demo", correlation_id="visual_fact:100")

    assert len(records) == 1
    assert records[0].status == "no_action"


def test_audit_writer_suppresses_duplicate_audit_ids() -> None:
    writer = SimingAuditWriter()
    writer.record(make_audit())
    writer.record(make_audit())

    records = writer.find_by_correlation(room_id="room_demo", correlation_id="visual_fact:100")

    assert len(records) == 1
    assert writer.duplicate_count == 1


def test_audit_writer_appends_late_result_correction_without_overwriting_final_record() -> None:
    writer = SimingAuditWriter()
    writer.record(make_audit())
    writer.append_correction(
        "audit_evt_visual_1",
        SimingAuditCorrection(
            correction_id="correction_1",
            status="late_result_correction",
            reason="downstream result arrived after final audit",
            causation_id="esm_result:late",
            producer_ts=150,
        ),
    )

    record = writer.find_by_causation(room_id="room_demo", causation_id="evt_visual_1")[0]

    assert record.status == "no_action"
    assert record.correction_records[0].status == "late_result_correction"
